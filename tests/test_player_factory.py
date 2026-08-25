"""Regresión: la fábrica de adaptadores normaliza el proxy (tor -> socks5 local).

Ambos motores deben recibir el proxy ya normalizado (type=socks5, server=127.0.0.1)
para que VLC aplique --socks y mpv reciba la config correcta.
"""

from src.infrastructure.adapters.player_factory import build_player_adapter


class _FakeVlc:
    def __init__(self, vlc_config=None, proxy_config=None):
        self.vlc_config = vlc_config
        self.proxy_config = proxy_config


class _FakeMpv:
    def __init__(self, mpv_config=None, proxy_config=None):
        self.mpv_config = mpv_config
        self.proxy_config = proxy_config


def test_build_player_adapter_creates_vlc_with_normalized_proxy():
    proxy = {
        "enabled": True,
        "type": "tor",
        "server": "remote.example",
        "port": 9150,
    }

    adapter = build_player_adapter("vlc", {"a": 1}, {}, proxy, _FakeVlc, _FakeMpv)

    assert isinstance(adapter, _FakeVlc)
    assert adapter.vlc_config == {"a": 1}
    assert adapter.proxy_config == {
        "enabled": True,
        "type": "socks5",
        "server": "127.0.0.1",
        "port": 9150,
        "username": "",
        "password": "",
    }


def test_build_player_adapter_creates_mpv_with_normalized_proxy():
    proxy = {"enabled": True, "type": "tor", "port": 9050}

    adapter = build_player_adapter("mpv", {}, {"b": 2}, proxy, _FakeVlc, _FakeMpv)

    assert isinstance(adapter, _FakeMpv)
    assert adapter.mpv_config == {"b": 2}
    assert adapter.proxy_config["type"] == "socks5"
    assert adapter.proxy_config["server"] == "127.0.0.1"


def test_build_player_adapter_creates_vlc_with_disabled_proxy():
    proxy = {"enabled": False}

    adapter = build_player_adapter("vlc", {}, {}, proxy, _FakeVlc, _FakeMpv)

    assert adapter.proxy_config == {"enabled": False}
