"""Autoactualización desde GitHub Releases.

La app se instala por usuario en ``%LocalAppData%\\Programs\\IPTVViewer``, así que
puede sustituirse a sí misma sin pedir administrador. El camino elegido es el
instalador de Inno Setup que publica el CI en cada release:

1. se compara la versión local con la última release;
2. se descarga el instalador y se comprueba su SHA-256 contra el ``digest`` que
   publica la API de GitHub;
3. se lanza en modo silencioso y la app se cierra para que Inno Setup pueda
   reemplazar el ejecutable.

Aquí vive solo la lógica: comparar versiones, elegir el asset, verificar el
hash y preparar los argumentos del instalador.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests

#: Endpoint de la última release publicada.
RELEASES_API = "https://api.github.com/repos/killo3967/IPTVViewer/releases/latest"
#: Prefijo del asset que interesa: el instalador, no el exe suelto.
SETUP_PREFIX = "IPTVViewer-Setup-"
#: Banderas del instalador silencioso. ``CLOSEAPPLICATIONS`` cierra esta app si
#: sigue abierta, y ``NORESTART`` evita que Inno reinicie Windows por su cuenta.
SETUP_ARGUMENTS = ("/VERYSILENT", "/SUPPRESSMSGBOXES", "/CLOSEAPPLICATIONS", "/NORESTART")
#: Horas entre comprobaciones automáticas.
CHECK_INTERVAL = timedelta(hours=24)
#: Tamaño de bloque al descargar (el instalador ronda los 100 MB).
CHUNK_SIZE = 256 * 1024

_DIGEST_RE = re.compile(r"^sha256:([0-9a-fA-F]{64})$")


def version_tuple(text: str) -> tuple[int, ...]:
    """Convierte ``1.9.10`` en ``(1, 9, 10)``; ``(0,)`` si no se puede leer."""
    try:
        return tuple(int(part) for part in str(text).strip().split("."))
    except (ValueError, AttributeError):
        return (0,)


def is_newer(candidate: str, current: str) -> bool:
    """``True`` si ``candidate`` es una versión posterior a ``current``."""
    return version_tuple(candidate) > version_tuple(current)


def should_check(
    last_check: str, now: datetime | None = None, interval: timedelta = CHECK_INTERVAL
) -> bool:
    """``True`` si toca comprobar: nunca se hizo o pasó el intervalo."""
    if not last_check:
        return True
    try:
        anterior = datetime.fromisoformat(last_check)
    except ValueError:
        return True
    return (now or datetime.now()) - anterior >= interval


def sha256_of(path: Path) -> str:
    """Hash SHA-256 del fichero, en hexadecimal minúscula."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_digest(path: Path, expected: str) -> bool:
    """Compara el hash del fichero con un ``sha256:...`` de la API.

    Sin digest no hay verificación posible, así que se considera fallo: es
    preferible no instalar nada a ejecutar una descarga sin comprobar.
    """
    encontrado = _DIGEST_RE.match((expected or "").strip())
    if not encontrado:
        return False
    return sha256_of(path) == encontrado.group(1).lower()


@dataclass(frozen=True)
class UpdateInfo:
    """Datos de una actualización disponible."""

    version: str
    notes: str
    asset_name: str
    asset_url: str
    digest: str
    page_url: str

    @property
    def can_self_update(self) -> bool:
        """Solo se actualiza sola si el asset es el instalador y trae hash."""
        return bool(self.asset_url and _DIGEST_RE.match(self.digest or ""))


def parse_release(payload: dict, current_version: str) -> UpdateInfo | None:
    """Extrae la actualización disponible del JSON de la API, si la hay.

    Devuelve ``None`` cuando la release no es más nueva o no trae un asset
    utilizable.
    """
    version = str(payload.get("tag_name", "")).lstrip("v")
    if not version or not is_newer(version, current_version):
        return None

    assets = payload.get("assets") or []
    elegido = next((a for a in assets if str(a.get("name", "")).startswith(SETUP_PREFIX)), None)
    if elegido is None:
        elegido = next((a for a in assets if str(a.get("name", "")).lower().endswith(".exe")), None)
    if elegido is None:
        return None

    return UpdateInfo(
        version=version,
        notes=str(payload.get("body") or ""),
        asset_name=str(elegido.get("name", "")),
        asset_url=str(elegido.get("browser_download_url", "")),
        digest=str(elegido.get("digest") or ""),
        page_url=str(payload.get("html_url", "")),
    )


def setup_arguments() -> list[str]:
    """Banderas con las que el instalador se aplica sin intervención."""
    return list(SETUP_ARGUMENTS)


def download(
    url: str,
    destination: Path,
    expected_digest: str,
    timeout: tuple[float, float] = (10, 120),
    progress=None,
) -> Path:
    """Descarga ``url`` en ``destination`` y verifica el SHA-256.

    Escribe primero en un fichero ``.part`` para no dejar un instalador a medias
    con el nombre bueno. Lanza ``ValueError`` si el hash no coincide.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")

    logging.info("Actualización: descargando %s", destination.name)
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length") or 0)
        recibidos = 0
        with open(partial, "wb") as handle:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                if not chunk:
                    continue
                handle.write(chunk)
                recibidos += len(chunk)
                if progress is not None:
                    progress(recibidos, total)

    if not verify_digest(partial, expected_digest):
        partial.unlink(missing_ok=True)
        raise ValueError("El SHA-256 del instalador no coincide con el publicado")

    partial.replace(destination)
    logging.info("Actualización: descarga verificada (%d bytes)", recibidos)
    return destination
