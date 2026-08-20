from src.infrastructure.adapters.file_m3u_repository import FileM3URepository


def test_get_channels_parses_extinf_attributes_and_skips_comment_lines(tmp_path):
    playlist_path = tmp_path / "sample.m3u"
    playlist_path.write_text(
        "\n".join(
            [
                "#EXTM3U",
                '#EXTINF:-1 tvg-id="news.id" tvg-name="News 24" tvg-logo="http://logos/news.png" group-title="News",News 24',
                "#KODIPROP:inputstream.adaptive.manifest_type=hls",
                "http://stream.example.test/news.m3u8",
                '#EXTINF:-1 tvg-id="music.id",Music Channel',
                "",
                "http://stream.example.test/music.m3u8",
            ]
        ),
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
