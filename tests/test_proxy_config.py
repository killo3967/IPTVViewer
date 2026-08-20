from src.infrastructure.utils.proxy import get_standardized_proxy_config


def test_get_standardized_proxy_config_disables_empty_or_disabled_proxy():
    assert get_standardized_proxy_config({}) == {"enabled": False}
    assert get_standardized_proxy_config({"enabled": False, "type": "http"}) == {
        "enabled": False
    }


def test_get_standardized_proxy_config_converts_tor_to_local_socks5_without_credentials():
    proxy_config = {
        "enabled": True,
        "type": "tor",
        "server": "remote.example.test",
        "port": 9150,
        "username": "user",
        "password": "secret",
    }

    normalized = get_standardized_proxy_config(proxy_config)

    assert normalized == {
        "enabled": True,
        "type": "socks5",
        "server": "127.0.0.1",
        "port": 9150,
        "username": "",
        "password": "",
    }
    assert proxy_config["type"] == "tor"
    assert proxy_config["server"] == "remote.example.test"


def test_get_standardized_proxy_config_preserves_non_tor_enabled_proxy_copy():
    proxy_config = {
        "enabled": True,
        "type": "HTTP",
        "server": "proxy.example.test",
        "port": 8080,
        "username": "user",
        "password": "secret",
    }

    normalized = get_standardized_proxy_config(proxy_config)

    assert normalized == proxy_config
    assert normalized is not proxy_config
