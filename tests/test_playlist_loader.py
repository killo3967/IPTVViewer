from src.application.services.playlist_loader import PlaylistLoader
from src.domain.entities.channel import Channel
from src.domain.ports.i_playlist_repo import IPlaylistRepository


class FakePlaylistRepository(IPlaylistRepository):
    def __init__(self, channels):
        self.channels = channels
        self.sources = []

    def get_channels(self, source):
        self.sources.append(source)
        return list(self.channels)


def test_load_and_filter_returns_only_channels_from_requested_group():
    repository = FakePlaylistRepository(
        [
            Channel(name="News", url="http://example.test/news", group="News"),
            Channel(name="Sports", url="http://example.test/sports", group="Sports"),
            Channel(name="Movies", url="http://example.test/movies", group="Movies"),
        ]
    )
    loader = PlaylistLoader(repository)

    playlist = loader.load_and_filter("playlist.m3u", group_filter="Sports")

    assert repository.sources == ["playlist.m3u"]
    assert [channel.name for channel in playlist] == ["Sports"]


def test_load_and_filter_with_empty_group_keeps_all_channels_in_order():
    channels = [
        Channel(name="News", url="http://example.test/news", group="News"),
        Channel(name="Sports", url="http://example.test/sports", group="Sports"),
    ]
    loader = PlaylistLoader(FakePlaylistRepository(channels))

    playlist = loader.load_and_filter("playlist.m3u")

    assert playlist.channels == channels
    assert playlist.channels is not channels


def test_load_and_filter_logs_counts(caplog):
    """El log tiene que decir cuántos canales llegaron y cuántos quedan."""
    import logging

    channels = [
        Channel(name="News", url="http://example.test/news", group="News"),
        Channel(name="Sports", url="http://example.test/sports", group="Sports"),
    ]
    loader = PlaylistLoader(FakePlaylistRepository(channels))

    with caplog.at_level(logging.INFO):
        loader.load_and_filter("playlist.m3u", group_filter="Sports")

    texto = caplog.text
    assert "2 canales en la descarga" in texto
    assert "1 tras el filtro 'Sports'" in texto


def test_load_and_filter_logs_when_there_is_no_filter(caplog):
    import logging

    loader = PlaylistLoader(FakePlaylistRepository([Channel(name="A", url="http://a.test")]))

    with caplog.at_level(logging.INFO):
        loader.load_and_filter("playlist.m3u")

    assert "1 canales en la descarga, sin filtro" in caplog.text
