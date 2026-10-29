"""Resolución del salto de un stream proxificado.

Con un front-end delante (xTeVe y similares) la lista que llega al reproductor no
lleva la URL del proveedor, sino ``http://<host>:<puerto>/stream/<hash>``. La URL
real solo aparece en el ``302`` con el que el front-end responde, y sin ella no se
puede probar el canal a mano ni reclamar al proveedor con la dirección exacta.

La sonda pide **solo ese primer salto** —``allow_redirects=False``, ``stream=True``,
respuesta cerrada sin leer vídeo— y deja la URL completa en el log. No sigue más
saltos a propósito: la siguiente dirección ya es del panel del proveedor y abrirla
gastaría una de sus conexiones mientras el motor está reproduciendo.

Ojo: al no recortar, el log contiene usuario, contraseña y token del abonado. El
fichero ``logs/`` está en ``.gitignore``; no se debe publicar.
"""

import logging

import requests

from src.infrastructure.utils.log_safe import safe_url

#: Cabecera con la que se sonda: algunos front-end rechazan clientes sin UA.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

#: Tiempo máximo de la sonda, en segundos.
DEFAULT_TIMEOUT = 3.0


def is_proxied_stream(url: str) -> bool:
    """``True`` si la URL apunta a la ruta ``/stream/`` de un front-end."""
    return "/stream/" in (url or "")


def _short_reason(exc: requests.RequestException, timeout: float) -> str:
    """Motivo corto para el log: el error crudo de ``requests`` ocupa dos líneas."""
    if isinstance(exc, requests.exceptions.ReadTimeout):
        return f"sin respuesta en {timeout:g} s"
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return f"sin conexión en {timeout:g} s"
    return str(exc).splitlines()[0][:80]


def _probe(url: str, timeout: float) -> tuple[str | None, str, bool]:
    """Devuelve (Location, detalle, hubo_respuesta) del primer salto.

    El tercer valor evita adivinar por el texto: un error de conexión de
    ``requests`` empieza por ``HTTPConnectionPool...`` y se confundiría con un
    código de estado.
    """
    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=False,
            timeout=timeout,
            stream=True,
        )
    except requests.RequestException as exc:
        return None, _short_reason(exc, timeout), False

    try:
        return response.headers.get("Location"), f"HTTP {response.status_code}", True
    finally:
        response.close()


def describe_stream(url: str, timeout: float = DEFAULT_TIMEOUT) -> str:
    """Línea de log con la URL del front-end y la URL real, completa.

    La primera va saneada (no lleva secretos); la segunda, tal cual la da el
    front-end, con usuario, token y query incluidos, porque es la que se pega en
    VLC o en ``ffprobe`` para comprobar el canal.
    """
    location, detalle, respondio = _probe(url, timeout)
    origen = safe_url(url)
    if location:
        return f"{origen} → {location}"
    if respondio:
        return f"{origen} → sin redirección ({detalle})"
    return f"{origen} → sin datos ({detalle})"


def log_stream_target(url: str, timeout: float = DEFAULT_TIMEOUT) -> None:
    """Resuelve el salto y lo escribe en el log (pensado para un hilo aparte)."""
    logging.info("Stream: %s", describe_stream(url, timeout))
