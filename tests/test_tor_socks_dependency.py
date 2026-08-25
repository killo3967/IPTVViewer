"""Regresión BUG-01: los proxies SOCKS5 de Tor requieren PySocks.

Cuando el proxy Tor está activo, ``setup_proxy`` exporta
``socks5h://127.0.0.1:<port>`` en HTTP_PROXY/HTTPS_PROXY/ALL_PROXY y las
descargas con ``requests`` (listas M3U remotas, EPG XMLTV) detectan esos
proxies automáticamente. urllib3 solo soporta esquemas socks5/socks5h si
PySocks está instalado; si falta, lanza "Missing dependencies for SOCKS
support." y toda descarga a través de Tor falla.
"""

import re
from pathlib import Path

from urllib3.contrib.socks import SOCKSProxyManager
from urllib3.util import parse_url

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_socks_module_available_for_tor_proxy():
    """PySocks debe estar instalado: es el módulo que urllib3 importa para
    resolver proxies SOCKS5/SOCKS5H."""
    import socks

    assert hasattr(socks, "SOCKS5")


def test_urllib3_builds_socks_proxy_manager_without_missing_dependencies():
    """urllib3 debe poder construir el gestor del proxy socks5h que
    ``setup_proxy`` genera para Tor sin lanzar
    'Missing dependencies for SOCKS support.'"""
    proxy_url = "socks5h://127.0.0.1:9050"

    parsed = parse_url(proxy_url)
    manager = SOCKSProxyManager(proxy_url)

    assert parsed.scheme == "socks5h"
    assert manager is not None


def test_pyinstaller_spec_packages_socks_module():
    """El empaquetado debe incluir el módulo ``socks`` (PySocks), que urllib3
    importa dinámicamente y PyInstaller no detecta de forma automática."""
    spec_path = _PROJECT_ROOT / "IPTVViewer.spec"
    spec_text = spec_path.read_text(encoding="utf-8")

    assert "'socks'" in spec_text or '"socks"' in spec_text
    # El módulo se declara en hiddenimports, no como dato/binario
    hiddenimports_block = re.search(
        r"hiddenimports\s*=\s*\[(.*?)\]", spec_text, re.DOTALL
    )
    assert hiddenimports_block is not None
    assert "socks" in hiddenimports_block.group(1)
