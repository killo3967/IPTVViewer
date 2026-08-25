"""Regresión: verificación autoritativa de que la salida pasa por Tor.

`_fetch_tor_verification` consulta https://check.torproject.org/api/ip, que
responde {"IsTor": true|false, "IP": "..."}. A diferencia de ip-api/ipify
(que solo dan la IP), este endpoint confirma si la IP es un nodo de salida
Tor conocido.
"""

import requests

from src.infrastructure.ui.components import proxy_config_dialog as proxy_dialog_module


class _DummyJsonResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_fetch_tor_verification_returns_is_tor_true_and_ip():
    def fake_get(url, **_kwargs):
        assert url == "https://check.torproject.org/api/ip"
        return _DummyJsonResponse({"IsTor": True, "IP": "185.220.101.34"})

    result = proxy_dialog_module._fetch_tor_verification(
        fake_get, "socks5h://127.0.0.1:9050"
    )

    assert result == (True, "185.220.101.34")


def test_fetch_tor_verification_returns_is_tor_false_and_ip():
    def fake_get(*_args, **_kwargs):
        return _DummyJsonResponse({"IsTor": False, "IP": "203.0.113.9"})

    result = proxy_dialog_module._fetch_tor_verification(
        fake_get, "socks5h://127.0.0.1:9050"
    )

    assert result == (False, "203.0.113.9")


def test_fetch_tor_verification_returns_none_on_request_error():
    def fake_get(*_args, **_kwargs):
        raise requests.RequestException("unreachable")

    assert (
        proxy_dialog_module._fetch_tor_verification(
            fake_get, "socks5h://127.0.0.1:9050"
        )
        is None
    )


def test_fetch_tor_verification_returns_none_on_missing_fields():
    def fake_get(*_args, **_kwargs):
        return _DummyJsonResponse({"foo": "bar"})

    assert (
        proxy_dialog_module._fetch_tor_verification(
            fake_get, "socks5h://127.0.0.1:9050"
        )
        is None
    )


def test_fetch_tor_verification_returns_none_on_non_dict_payload():
    def fake_get(*_args, **_kwargs):
        return _DummyJsonResponse(None)

    assert (
        proxy_dialog_module._fetch_tor_verification(
            fake_get, "socks5h://127.0.0.1:9050"
        )
        is None
    )
