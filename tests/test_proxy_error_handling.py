import builtins
import time
import types

import pytest
import requests

from src.infrastructure.ui.components import proxy_config_dialog as proxy_dialog_module
from src.infrastructure.utils import proxy as proxy_module


class _FakeManager:
    def __init__(self):
        self.stop_calls = 0

    def stop(self):
        self.stop_calls += 1


class _DummyJsonResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _DummyTextResponse:
    def __init__(self, text):
        self.text = text


class _SocketRaisesOnConnect:
    def settimeout(self, _timeout):
        return None

    def connect(self, _address):
        raise OSError("unreachable")

    def close(self):
        return None


class _SocketRaisesUnexpectedly:
    def settimeout(self, _timeout):
        return None

    def connect(self, _address):
        return None

    def close(self):
        raise ValueError("buggy socket")


class _ListenSocket:
    def __init__(self, exc):
        self._exc = exc

    def close(self):
        raise self._exc


class _Server:
    def __init__(self, exc):
        self.listen_socket = _ListenSocket(exc)


@pytest.fixture(autouse=True)
def _stub_sleep(monkeypatch):
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)


def test_torpy_proxy_stop_ignores_os_error_when_closing_socket():
    manager = proxy_module.TorpyProxyManager()
    manager.running = True
    manager.server = _Server(OSError("already closed"))

    manager.stop()

    assert manager.running is False
    assert manager.server is None
    assert manager.tor is None


def test_torpy_proxy_stop_propagates_unexpected_socket_close_error():
    manager = proxy_module.TorpyProxyManager()
    manager.running = True
    manager.server = _Server(ValueError("unexpected"))

    with pytest.raises(ValueError, match="unexpected"):
        manager.stop()


def test_setup_proxy_ignores_missing_qt_dependency(monkeypatch):
    manager = _FakeManager()
    monkeypatch.setattr(
        proxy_module.TorpyProxyManager,
        "get_instance",
        classmethod(lambda cls: manager),
    )

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "PyQt6.QtNetwork":
            raise ImportError("Qt network unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    proxy_module.setup_proxy({})

    assert manager.stop_calls == 1


def test_setup_proxy_propagates_unexpected_qt_proxy_errors(monkeypatch):
    manager = _FakeManager()
    monkeypatch.setattr(
        proxy_module.TorpyProxyManager,
        "get_instance",
        classmethod(lambda cls: manager),
    )

    class FakeQNetworkProxy:
        class ProxyType:
            NoProxy = object()
            HttpProxy = object()
            Socks4Proxy = object()
            Socks5Proxy = object()

        def __init__(self, *_args, **_kwargs):
            pass

        def setType(self, *_args, **_kwargs):
            return None

        def setHostName(self, *_args, **_kwargs):
            return None

        def setPort(self, *_args, **_kwargs):
            return None

        def setUser(self, *_args, **_kwargs):
            return None

        def setPassword(self, *_args, **_kwargs):
            return None

        @staticmethod
        def setApplicationProxy(_proxy):
            raise ValueError("bad proxy state")

    fake_module = types.SimpleNamespace(QNetworkProxy=FakeQNetworkProxy)
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "PyQt6.QtNetwork":
            return fake_module
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(ValueError, match="bad proxy state"):
        proxy_module.setup_proxy(
            {"enabled": True, "type": "http", "server": "proxy.example", "port": 8080}
        )


def test_fetch_tor_info_swallows_request_failures():
    def fake_get(*_args, **_kwargs):
        raise requests.RequestException("tor info unavailable")

    assert (
        proxy_dialog_module._fetch_tor_info(
            fake_get, "socks5h://127.0.0.1:9050"
        )
        is None
    )


def test_fetch_tor_info_propagates_unexpected_errors():
    def fake_get(*_args, **_kwargs):
        raise TypeError("bad callback")

    with pytest.raises(TypeError, match="bad callback"):
        proxy_dialog_module._fetch_tor_info(fake_get, "socks5h://127.0.0.1:9050")


def test_is_local_port_open_returns_false_for_socket_errors():
    assert (
        proxy_dialog_module._is_local_port_open(
            lambda *_args, **_kwargs: _SocketRaisesOnConnect(),
            "127.0.0.1",
            9050,
        )
        is False
    )


def test_is_local_port_open_propagates_unexpected_socket_errors():
    with pytest.raises(ValueError, match="buggy socket"):
        proxy_dialog_module._is_local_port_open(
            lambda *_args, **_kwargs: _SocketRaisesUnexpectedly(),
            "127.0.0.1",
            9050,
        )


def test_fetch_proxy_test_ip_falls_back_after_request_error():
    urls = []

    def fake_get(url, **_kwargs):
        urls.append(url)
        if len(urls) == 1:
            raise requests.RequestException("primary down")
        return _DummyTextResponse("203.0.113.7\n")

    ip = proxy_dialog_module._fetch_proxy_test_ip(fake_get, {"http": "proxy"}, 20)

    assert ip == "203.0.113.7"
    assert urls == ["http://api.ipify.org?format=json", "http://ident.me"]


def test_fetch_proxy_test_ip_falls_back_after_invalid_json():
    urls = []

    def fake_get(url, **_kwargs):
        urls.append(url)
        if len(urls) == 1:
            return _DummyJsonResponse(payload=None)
        return _DummyTextResponse("198.51.100.25")

    ip = proxy_dialog_module._fetch_proxy_test_ip(fake_get, {"http": "proxy"}, 20)

    assert ip == "198.51.100.25"
    assert urls == ["http://api.ipify.org?format=json", "http://ident.me"]


def test_fetch_proxy_test_ip_propagates_unexpected_errors():
    def fake_get(*_args, **_kwargs):
        raise TypeError("bad getter")

    with pytest.raises(TypeError, match="bad getter"):
        proxy_dialog_module._fetch_proxy_test_ip(fake_get, {"http": "proxy"}, 20)
