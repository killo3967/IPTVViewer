"""URLs aptas para el log.

Las listas y los streams del proveedor llevan usuario, contraseña y token dentro
de la ruta o de la query. El log se comparte cuando se pide ayuda, así que se
recorta a lo que identifica el servidor y el recurso: esquema, host, puerto y como
mucho los dos últimos segmentos de la ruta, sin query ni credenciales.
"""

from urllib.parse import urlsplit

#: Segmentos finales de la ruta que se conservan.
MAX_SEGMENTS = 2


def safe_url(url: str, segments: int = MAX_SEGMENTS) -> str:
    """Devuelve ``url`` sin credenciales, sin query y con la ruta recortada.

    ``segments`` permite quedarse con menos segmentos finales: en las URLs del
    panel el penúltimo es la contraseña del abonado, así que para un destino de
    stream se usa ``segments=1``.
    """
    if not url:
        return ""

    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return "<url ilegible>"

    if not parts.scheme or not parts.hostname:
        return url

    host = parts.hostname if port is None else f"{parts.hostname}:{port}"
    total = [segment for segment in parts.path.split("/") if segment]
    keep = max(0, segments)
    if keep == 0:
        path = ""
    elif len(total) > keep:
        path = "/…/" + "/".join(total[-keep:])
    else:
        path = "/" + "/".join(total)

    return f"{parts.scheme}://{host}{path}"
