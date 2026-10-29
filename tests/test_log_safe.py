"""Pruebas de ``safe_url``: el log no puede filtrar credenciales del proveedor."""

from src.infrastructure.utils.log_safe import safe_url


def test_keeps_short_list_urls_intact():
    url = "http://killo3967.duckdns.org:34400/m3u/xteve.m3u"
    assert safe_url(url) == url


def test_drops_credentials_and_query_of_a_stream():
    url = "http://user:secret@panel.example:25461/live/user/secret/3797.m3u8?token=abc"
    assert safe_url(url) == "http://panel.example:25461/…/secret/3797.m3u8"


def test_drops_userinfo_even_when_url_is_short():
    assert safe_url("http://user:pass@example.test/m3u/x.m3u") == (
        "http://example.test/m3u/x.m3u"
    )


def test_keeps_the_two_last_segments_of_a_long_path():
    url = "http://host:25461/u1/1211299111/3797"
    assert safe_url(url) == "http://host:25461/…/1211299111/3797"


def test_handles_empty_and_broken_values():
    assert safe_url("") == ""
    assert safe_url("http://[::1") == "<url ilegible>"
    assert safe_url("m3u/lista.m3u") == "m3u/lista.m3u"


def test_keeps_https_and_default_port_out_of_the_text():
    assert safe_url("https://example.test/a/b/c") == "https://example.test/…/b/c"
