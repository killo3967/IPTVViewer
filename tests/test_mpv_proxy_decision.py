"""Regresión: mpv/FFmpeg no soporta proxies SOCKS (Tor).

El adaptador mpv no puede aplicar un proxy SOCKS (Tor) porque FFmpeg no tiene
soporte SOCKS. La decisión debe clasificar el proxy y avisar en lugar de
pretender que funciona "vía entorno".
"""

from src.infrastructure.adapters.mpv_player_adapter import _mpv_proxy_decision


def test_mpv_proxy_decision_disabled_without_proxy():
    assert _mpv_proxy_decision(None) == "disabled"
    assert _mpv_proxy_decision({}) == "disabled"
    assert _mpv_proxy_decision({"enabled": False}) == "disabled"


def test_mpv_proxy_decision_disabled_without_server():
    assert _mpv_proxy_decision({"enabled": True, "type": "socks5"}) == "disabled"


def test_mpv_proxy_decision_socks_unsupported_for_tor():
    assert (
        _mpv_proxy_decision({"enabled": True, "type": "tor", "server": "127.0.0.1"})
        == "socks_unsupported"
    )


def test_mpv_proxy_decision_socks_unsupported_for_socks5():
    assert (
        _mpv_proxy_decision({"enabled": True, "type": "socks5", "server": "127.0.0.1"})
        == "socks_unsupported"
    )


def test_mpv_proxy_decision_http_via_env():
    assert (
        _mpv_proxy_decision({"enabled": True, "type": "http", "server": "proxy.example"})
        == "http_via_env"
    )
