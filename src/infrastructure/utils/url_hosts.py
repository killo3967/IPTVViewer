"""Reescritura del host de bucle local en las URLs de una lista remota.

Un backend que genera la lista (xteve, Jellyfin, un panel propio) escribe a
veces sus propias URLs de imagen con el host con el que se le llamó. Si esa
llamada fue ``http://localhost:34400``, la URL resultante es inservible para
cualquier otro equipo: ``localhost`` designa siempre a la máquina que hace la
petición, no a la que sirve la lista.

La corrección es determinista y se limita al bucle local. Una IP privada
(``172.26.64.1``) o un nombre DNS mal puestos pueden ser válidos en otras
redes, así que no se tocan: eso se corrige en el origen.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

#: Nombres de host que designan al propio equipo que hace la petición.
#: ``urlsplit`` devuelve el IPv6 sin corchetes, por eso están las dos formas.
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "[::1]", "0.0.0.0"})


def is_loopback_host(host: str | None) -> bool:
    """``True`` si ``host`` designa al propio equipo (``localhost``, ``127.0.0.1``…)."""
    if not host:
        return False
    name = host.strip().rstrip(".").lower()
    if name in LOOPBACK_HOSTS:
        return True
    return name.endswith(".localhost")


def source_authority(source_url: str | None) -> str:
    """Devuelve ``host:puerto`` de la lista, o ``""`` si la fuente es local.

    También devuelve ``""`` cuando la fuente no es ``http(s)``: con un archivo
    local no hay host de referencia al que reescribir.
    """
    parts = urlsplit(source_url or "")
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return ""

    host = parts.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        port = parts.port
    except ValueError:
        return ""
    return f"{host}:{port}" if port else host


def normalize_loopback_host(url: str | None, source_url: str | None) -> str | None:
    """Sustituye el host de bucle local de ``url`` por el de la lista.

    Solo cambia la autoridad (host y puerto, tomados de ``source_url``): la
    ruta, la query, el fragmento y las credenciales se conservan carácter a
    carácter, así que no hay re-codificaciones de espacios ni de ``%20``.

    Devuelve ``url`` intacta si no hay nada que corregir o si la lista es un
    archivo local.
    """
    if not url:
        return url

    parts = urlsplit(url.strip())
    if not is_loopback_host(parts.hostname):
        return url

    authority = source_authority(source_url)
    if not authority:
        return url

    userinfo = ""
    if "@" in parts.netloc:
        userinfo = parts.netloc.rsplit("@", 1)[0] + "@"

    return urlunsplit(
        (parts.scheme or "http", userinfo + authority, parts.path, parts.query, parts.fragment)
    )
