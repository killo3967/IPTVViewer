"""Pruebas de la sonda del salto del stream (xteve y similares)."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.infrastructure.utils import stream_probe
from src.infrastructure.utils.stream_probe import (
    describe_stream,
    is_proxied_stream,
    log_stream_target,
)

XTEVE = "http://killo3967.duckdns.org:34400/stream/d6751076c8de7a5e947c8bbf7f090d1f"
PANEL = ("http://c56e0feea4ed97461a71b01f7fc98fa9.dev48536.top:25461/"
         "rEBgMzhyOQ/1211299111/3846?h=106dad268&i=132511")


class _FakeResponse:
    def __init__(self, status_code=302, location=None):
        self.status_code = status_code
        self.headers = {"Location": location} if location else {}

    def close(self):
        pass


def test_is_proxied_stream_detects_the_front_end_route():
    assert is_proxied_stream(XTEVE) is True
    assert is_proxied_stream("http://panel.test:25461/user/pass/7") is False
    assert is_proxied_stream("") is False


def test_describe_stream_shows_the_provider_url_complete(monkeypatch):
    """La URL del panel se apunta entera: sin recortar es como se prueba a mano."""
    monkeypatch.setattr(stream_probe.requests, "get", lambda *a, **k: _FakeResponse(302, PANEL))

    texto = describe_stream(XTEVE)

    assert texto == f"{XTEVE} → {PANEL}"


def test_describe_stream_keeps_user_password_and_query_of_the_real_url(monkeypatch):
    """Sin el usuario, el ``h=`` y el id, la URL no sirve para comprobar el canal."""
    monkeypatch.setattr(stream_probe.requests, "get", lambda *a, **k: _FakeResponse(302, PANEL))

    texto = describe_stream(XTEVE)

    assert "rEBgMzhyOQ" in texto
    assert "1211299111" in texto
    assert "h=106dad268&i=132511" in texto


def test_describe_stream_reports_a_direct_stream(monkeypatch):
    monkeypatch.setattr(stream_probe.requests, "get", lambda *a, **k: _FakeResponse(200))

    assert describe_stream(XTEVE) == f"{XTEVE} → sin redirección (HTTP 200)"


def test_describe_stream_reports_a_network_failure(monkeypatch):
    import requests

    def explota(*args, **kwargs):
        raise requests.ConnectTimeout("no responde")

    monkeypatch.setattr(stream_probe.requests, "get", explota)

    texto = describe_stream(XTEVE, timeout=2.5)
    assert texto == f"{XTEVE} → sin datos (sin conexión en 2.5 s)"


def test_describe_stream_shortens_a_connection_error(monkeypatch):
    import requests

    def explota(*args, **kwargs):
        raise requests.ConnectionError(
            "HTTPConnectionPool(host='x', port=1): Max retries exceeded with url: /a\n"
            "Caused by: NewConnectionError"
        )

    monkeypatch.setattr(stream_probe.requests, "get", explota)

    texto = describe_stream(XTEVE)
    assert "sin datos" in texto
    assert "\n" not in texto
    assert "Max retries exceeded" in texto


def test_probe_never_follows_redirects_nor_downloads_video(monkeypatch):
    visto = {}

    def falso_get(url, **kwargs):
        visto.update(kwargs)
        return _FakeResponse(302, PANEL)

    monkeypatch.setattr(stream_probe.requests, "get", falso_get)
    stream_probe._probe(XTEVE, 3.0)

    assert visto["allow_redirects"] is False
    assert visto["stream"] is True


def test_log_stream_target_writes_the_line(monkeypatch, caplog):
    import logging

    monkeypatch.setattr(stream_probe.requests, "get", lambda *a, **k: _FakeResponse(302, PANEL))

    with caplog.at_level(logging.INFO):
        log_stream_target(XTEVE)

    assert "Stream: http://killo3967.duckdns.org:34400" in caplog.text
    assert "dev48536.top" in caplog.text
