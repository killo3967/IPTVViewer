"""Bootstrap de libmpv-2.dll: la descarga en runtime cuando el motor es mpv.

El exe ya no empaqueta las DLLs: la app descarga ``libmpv-2.dll`` en runtime
y la guarda junto al ejecutable. Hay dos variantes: genérica x86-64 (sin AVX2,
en ``bin/libmpv-2.dll``) y v3/AVX2 (en ``bin-v3/libmpv-2.dll``). Versión
pineada: release ``20260814`` de ``shinchiro/mpv-winbuild-cmake``, con fallback
en el espejo de SourceForge (``mpv-player-windows``, carpeta ``libmpv``) por si
GitHub poda el release.

El módulo es puro (sin PyQt): la UI solo consume ``ensure_libmpv_dll`` con un
callback de progreso. ``import mpv`` carga la DLL al importar el módulo, así
que ``ensure_libmpv_dll`` debe ejecutarse ANTES de ``import mpv_player_adapter``.
"""

import logging
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import py7zr
import requests

MPV_DLL_FILENAME = "libmpv-2.dll"
# Variante genérica x86-64 (sin AVX2): bin/libmpv-2.dll
MPV_ARCHIVE_URL = (
    "https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/20260814/"
    "mpv-dev-x86_64-20260814-git-7b8915bc1d.7z"
)
MPV_FALLBACK_URL = (
    "https://sourceforge.net/projects/mpv-player-windows/files/libmpv/"
    "mpv-dev-x86_64-20260809-git-dd5d17d328.7z/download"
)
MPV_ARCHIVE_URLS = (MPV_ARCHIVE_URL, MPV_FALLBACK_URL)

# Variante v3 (AVX2): bin-v3/libmpv-2.dll
MPV_V3_ARCHIVE_URL = (
    "https://github.com/shinchiro/mpv-winbuild-cmake/releases/download/20260814/"
    "mpv-dev-x86_64-v3-20260814-git-7b8915bc1d.7z"
)
MPV_V3_FALLBACK_URL = (
    "https://sourceforge.net/projects/mpv-player-windows/files/libmpv/"
    "mpv-dev-x86_64-v3-20260809-git-dd5d17d328.7z/download"
)
MPV_V3_ARCHIVE_URLS = (MPV_V3_ARCHIVE_URL, MPV_V3_FALLBACK_URL)

_CHUNK_SIZE = 256 * 1024
_DOWNLOAD_TIMEOUT = 120

_logger = logging.getLogger(__name__)


class MpvDllBootstrapError(RuntimeError):
    """La descarga o extracción de libmpv-2.dll falló."""


def libmpv_dll_path(bin_dir: Path) -> Path:
    """Ruta final de la DLL dentro de ``bin_dir``."""
    return bin_dir / MPV_DLL_FILENAME


def _root_dir() -> Path:
    """Raíz de la app: dir del exe congelado, o raíz del proyecto en desarrollo."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent.parent


def default_bin_dir() -> Path:
    """Directorio estándar para ``libmpv-2.dll`` (variante genérica, sin AVX2)."""
    return _root_dir() / 'bin'


def default_bin_v3_dir() -> Path:
    """Directorio para ``libmpv-2.dll`` variante v3 (AVX2)."""
    return _root_dir() / 'bin-v3'


def is_libmpv_available(bin_dir: Path) -> bool:
    """True si ``bin_dir/libmpv-2.dll`` existe y no está vacía."""
    dll = libmpv_dll_path(bin_dir)
    try:
        return dll.is_file() and dll.stat().st_size > 0
    except OSError:
        return False


def is_libmpv_v3_available() -> bool:
    """True si ``bin-v3/libmpv-2.dll`` (variante v3) existe y no está vacía."""
    return is_libmpv_available(default_bin_v3_dir())


def ensure_libmpv_dll(
    bin_dir: Path,
    progress: Callable[[int, int], None] | None = None,
    urls: tuple[str, ...] = MPV_ARCHIVE_URLS,
) -> Path:
    """Garantiza ``bin_dir/libmpv-2.dll`` descargándola desde ``urls`` si falta.

    ``progress(downloaded, total)`` se invoca con bytes durante la descarga
    (solo cuando el servidor reporta ``Content-Length``). Lanza
    ``MpvDllBootstrapError`` si la descarga o la extracción fallan.
    """
    dll_path = libmpv_dll_path(bin_dir)
    if is_libmpv_available(bin_dir):
        _logger.debug("MPV: %s ya disponible en %s", MPV_DLL_FILENAME, dll_path)
        return dll_path

    bin_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="mpv_bootstrap_"))
    tmp_archive = tmp_dir / "libmpv.7z"
    try:
        _download_archive(tmp_archive, progress, urls)
        _extract_dll(tmp_archive, tmp_dir)
        shutil.move(str(tmp_dir / MPV_DLL_FILENAME), str(dll_path))
        _logger.info("MPV: %s instalada en %s", MPV_DLL_FILENAME, dll_path)
        return dll_path
    except MpvDllBootstrapError:
        raise
    except Exception as e:
        raise MpvDllBootstrapError(
            f"No se pudo instalar {MPV_DLL_FILENAME}: {e}"
        ) from e
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def ensure_libmpv_v3_dll(
    bin_dir: Path | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Garantiza ``bin-v3/libmpv-2.dll`` (variante v3/AVX2) descargándola si falta."""
    return ensure_libmpv_dll(
        bin_dir if bin_dir is not None else default_bin_v3_dir(),
        progress,
        MPV_V3_ARCHIVE_URLS,
    )


def _download_archive(
    tmp_archive: Path,
    progress: Callable[[int, int], None] | None,
    urls: tuple[str, ...],
) -> None:
    """Descarga el .7z a ``tmp_archive`` con fallback entre fuentes.

    Intenta cada URL de ``urls`` en orden. Si una falla (error de red o HTTP),
    prueba la siguiente; cada intento trunca el archivo temporal. Lanza
    ``MpvDllBootstrapError`` si todas las fuentes fallan.
    """
    errors: list[str] = []
    for url in urls:
        try:
            session = requests.Session()
            session.trust_env = False  # descarga directa, sin pasar por el proxy configurado
            with session.get(url, stream=True, timeout=_DOWNLOAD_TIMEOUT) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", "0") or 0)
                downloaded = 0
                with open(tmp_archive, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress is not None and total > 0:
                            progress(downloaded, total)
            return
        except requests.RequestException as e:
            errors.append(f"{url}: {e}")
    raise MpvDllBootstrapError(
        f"Fallo al descargar {MPV_DLL_FILENAME} desde todas las fuentes: "
        + " | ".join(errors)
    )


def _extract_dll(tmp_archive: Path, dest_dir: Path) -> None:
    """Extrae solo ``libmpv-2.dll`` del .7z y valida que salió completa."""
    try:
        with py7zr.SevenZipFile(tmp_archive) as archive:
            archive.extract(path=dest_dir, targets=[MPV_DLL_FILENAME])
    except MpvDllBootstrapError:
        raise
    except Exception as e:
        raise MpvDllBootstrapError(
            f"Fallo al extraer {MPV_DLL_FILENAME} del archivo 7z: {e}"
        ) from e
    extracted = dest_dir / MPV_DLL_FILENAME
    if not extracted.is_file() or extracted.stat().st_size == 0:
        raise MpvDllBootstrapError(
            f"El archivo 7z descargado no contiene {MPV_DLL_FILENAME}."
        )
