from src.infrastructure.adapters.file_m3u_repository import FileM3URepository


def test_get_channels_parses_extinf_attributes_and_skips_comment_lines(tmp_path):
    playlist_path = tmp_path / "sample.m3u"
    playlist_path.write_text(
        "#EXTM3U\n"
        '#EXTINF:-1 tvg-id="news.id" tvg-name="News 24" tvg-logo="http://logos/news.png" group-title="News",News 24\n'
        "#KODIPROP:inputstream.adaptive.manifest_type=hls\n"
        "http://stream.example.test/news.m3u8\n"
        '#EXTINF:-1 tvg-id="music.id",Music Channel\n'
        "\n"
        "http://stream.example.test/music.m3u8",
        encoding="utf-8",
    )

    channels = FileM3URepository().get_channels(str(playlist_path))

    assert len(channels) == 2
    news = channels[0]
    assert news.name == "News 24"
    assert news.url == "http://stream.example.test/news.m3u8"
    assert news.group == "News"
    assert news.logo_url == "http://logos/news.png"
    assert news.tvg_id == "news.id"

    music = channels[1]
    assert music.name == "Music Channel"
    assert music.url == "http://stream.example.test/music.m3u8"
    assert music.group == ""
    assert music.logo_url == ""
    assert music.tvg_id == "music.id"


def test_get_channels_returns_empty_list_for_missing_file(tmp_path):
    missing_path = tmp_path / "missing.m3u"

    channels = FileM3URepository().get_channels(str(missing_path))

    assert channels == []


class _FakeResponse:
    def __init__(self, status_code=200, text="#EXTM3U\n", url="http://server.test/m3u/lista.m3u"):
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_remote_download_is_logged_with_status_size_and_time(monkeypatch, caplog):
    """El log debe decir si se llegó al servidor y cuánto pescó."""
    import logging

    from src.infrastructure.adapters import file_m3u_repository as modulo

    texto = (
        "#EXTM3U\n"
        '#EXTINF:-1 tvg-id="1",LA 1\n'
        "http://server.test/stream/1\n"
        "#EXTINF:-1 tvg-id=\"2\",LA 2\n"
        "http://server.test/stream/2\n"
    )
    monkeypatch.setattr(
        modulo.requests, "get", lambda *a, **k: _FakeResponse(200, texto)
    )

    with caplog.at_level(logging.INFO):
        canales = modulo.FileM3URepository().get_channels("http://server.test/m3u/lista.m3u")

    assert len(canales) == 2
    assert "M3U: GET http://server.test/m3u/lista.m3u -> HTTP 200" in caplog.text
    assert "M3U: 2 canales parseados" in caplog.text


def test_remote_failure_is_logged_with_reason_not_credentials(monkeypatch, caplog):
    import logging

    from src.infrastructure.adapters import file_m3u_repository as modulo

    monkeypatch.setattr(
        modulo.requests, "get", lambda *a, **k: _FakeResponse(401, "token requerido")
    )

    with caplog.at_level(logging.INFO):
        canales = modulo.FileM3URepository().get_channels(
            "http://server.test:34400/m3u/lista.m3u?token=secreto"
        )

    assert canales == []
    assert "HTTP 401" in caplog.text
    assert "secreto" not in caplog.text
    assert "M3U: 0 canales parseados" in caplog.text


def test_remote_playlist_rewrites_loopback_logo_hosts():
    """Un backend graba la URL de su imagen con el host con el que se le llamó."""
    repo = FileM3URepository()
    lines = [
        "#EXTM3U",
        '#EXTINF:-1 tvg-id="1" tvg-logo="http://localhost:34400/data_images/AMC.png" group-title="SPAIN",AMC',
        "http://198.51.100.20:34400/stream/aaa",
        '#EXTINF:-1 tvg-id="2" tvg-logo="https://raw.githubusercontent.com/x/y.png",Otra',
        "http://198.51.100.20:34400/stream/bbb",
    ]
    repo._get_content = lambda source: lines  # type: ignore[method-assign]

    channels = repo.get_channels("http://198.51.100.20:34400/m3u/xteve.m3u")

    assert channels[0].logo_url == "http://198.51.100.20:34400/data_images/AMC.png"
    assert channels[1].logo_url == "https://raw.githubusercontent.com/x/y.png"
    # Solo se toca el logo: la URL del stream se respeta tal cual.
    assert channels[0].url == "http://198.51.100.20:34400/stream/aaa"


def test_local_playlist_keeps_loopback_logo_hosts(tmp_path):
    playlist_path = tmp_path / "local.m3u"
    playlist_path.write_text(
        "#EXTM3U\n"
        '#EXTINF:-1 tvg-id="1" tvg-logo="http://localhost:34400/data_images/AMC.png",AMC\n'
        "http://localhost:34400/stream/aaa",
        encoding="utf-8",
    )

    channels = FileM3URepository().get_channels(str(playlist_path))

    assert channels[0].logo_url == "http://localhost:34400/data_images/AMC.png"
