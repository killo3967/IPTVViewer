"""Bootstrap de VLC: detección, entorno y descarga portátil (motor vlc).

Cuando el motor activo es ``vlc`` pero libvlc.dll no está disponible (ni
instalado en el sistema, ni señalado por el usuario, ni portátil), la app no
puede reproducir. Este módulo puro (sin PyQt) ofrece: detección de libvlc.dll
en las rutas conocidas, configuración del entorno para python-vlc
(``PYTHON_VLC_LIB_PATH``/``PYTHON_VLC_MODULE_PATH``) y descarga+extracción de
la build portátil pineada (3.0.21). La UI solo consume estas funciones con un
callback de progreso. Versión pineada: 3.0.21.
"""

import logging
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

import py7zr
import requests

VLC_VERSION = "3.0.21"
VLC_EXE_URL = (
    f"https://get.videolan.org/vlc/{VLC_VERSION}/win64/vlc-{VLC_VERSION}-win64.exe"
)
VLC_7Z_URL = (
    f"https://get.videolan.org/vlc/{VLC_VERSION}/win64/vlc-{VLC_VERSION}-win64.7z"
)
VLC_SUBDIR = f"vlc-{VLC_VERSION}"

_CHUNK_SIZE = 256 * 1024
_DOWNLOAD_TIMEOUT = 120

_logger = logging.getLogger(__name__)


class VlcBootstrapError(RuntimeError):
    """La descarga, extracción o configuración de VLC falló."""


def default_vlc_dir() -> Path:
    """Directorio estándar del VLC portátil gestionado por la app.

    En el exe congelado es ``<dir del exe>/vlc``; en desarrollo es la raíz del
    proyecto (``<raiz>/vlc``).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent / "vlc"
    return Path(__file__).resolve().parent.parent.parent.parent / "vlc"


def _candidate_libvlc_paths() -> list[Path]:
    """Rutas candidatas a ``libvlc.dll``, en orden de prioridad."""
    candidates: list[Path] = []
    env_path = os.environ.get("PYTHON_VLC_LIB_PATH")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(default_vlc_dir() / VLC_SUBDIR / "libvlc.dll")
    for var in ("ProgramFiles", "ProgramFiles(x86)"):
        base = os.environ.get(var)
        if base:
            candidates.append(Path(base) / "VideoLAN" / "VLC" / "libvlc.dll")
    return candidates


def is_vlc_available() -> bool:
    """True si hay una ``libvlc.dll`` usable en alguna de las rutas conocidas."""
    return detect_vlc_lib() is not None


def detect_vlc_lib() -> Path | None:
    """Ruta a ``libvlc.dll`` encontrada, o None si VLC no está disponible.

    Busca, en este orden: env ``PYTHON_VLC_LIB_PATH``, el VLC portátil de la
    app (``default_vlc_dir()/vlc-3.0.21``) y las instalaciones estándar de
    Windows (``%ProgramFiles%``/``%ProgramFiles(x86)%``).
    """
    for dll in _candidate_libvlc_paths():
        try:
            if dll.is_file() and dll.stat().st_size > 0:
                return dll
        except OSError:
            continue
    return None


def configure_vlc_env(vlc_dir: Path) -> None:
    """Configura el entorno para que python-vlc use ``vlc_dir``.

    ``PYTHON_VLC_LIB_PATH`` apunta a ``vlc_dir/libvlc.dll`` y
    ``PYTHON_VLC_MODULE_PATH`` a ``vlc_dir/plugins``. Debe ejecutarse ANTES de
    ``import vlc`` (python-vlc lee estas variables en ``find_lib``).
    """
    os.environ["PYTHON_VLC_LIB_PATH"] = str(vlc_dir / "libvlc.dll")
    os.environ["PYTHON_VLC_MODULE_PATH"] = str(vlc_dir / "plugins")


def install_vlc_portable(
    progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Descarga y extrae el VLC portátil pineado en ``default_vlc_dir()``.

    ``progress(downloaded, total)`` se invoca con bytes durante la descarga
    (solo cuando el servidor reporta ``Content-Length``). Devuelve la carpeta
    ``vlc-3.0.21`` ya extraída. Lanza ``VlcBootstrapError`` ante cualquier
    fallo de descarga o extracción.
    """
    dest_root = default_vlc_dir()
    tmp_dir = Path(tempfile.mkdtemp(prefix="vlc_bootstrap_"))
    tmp_archive = tmp_dir / f"vlc-{VLC_VERSION}-win64.7z"
    try:
        _download_archive(tmp_archive, progress)
        dest_root.mkdir(parents=True, exist_ok=True)
        with py7zr.SevenZipFile(tmp_archive) as archive:
            archive.extract(path=dest_root)
        extracted = dest_root / VLC_SUBDIR
        _validate_extracted(extracted)
        _logger.info("VLC portátil %s instalado en %s", VLC_VERSION, extracted)
        return extracted
    except VlcBootstrapError:
        raise
    except Exception as e:
        raise VlcBootstrapError(f"No se pudo instalar VLC portátil: {e}") from e
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _validate_extracted(extracted: Path) -> None:
    """Valida que la extracción dejó ``vlc-3.0.21/libvlc.dll`` usable."""
    dll = extracted / "libvlc.dll"
    try:
        valid = dll.is_file() and dll.stat().st_size > 0
    except OSError:
        valid = False
    if not valid:
        raise VlcBootstrapError(
            f"El archivo descargado no contiene {VLC_SUBDIR}/libvlc.dll."
        )


def _download_archive(
    tmp_archive: Path, progress: Callable[[int, int], None] | None
) -> None:
    """Descarga el .7z a ``tmp_archive`` reportando progreso por bytes."""
    try:
        with requests.get(VLC_7Z_URL, stream=True, timeout=_DOWNLOAD_TIMEOUT) as resp:
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
    except requests.RequestException as e:
        raise VlcBootstrapError(
            f"Fallo al descargar VLC desde {VLC_7Z_URL}: {e}"
        ) from e
