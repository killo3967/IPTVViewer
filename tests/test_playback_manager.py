from src.application.services.playback_manager import PlaybackManager
from src.domain.entities.channel import Channel
from src.domain.ports.i_player import IPlayer


class FakePlayer(IPlayer):
    def __init__(self):
        self.calls = []

    def play(self, url):
        self.calls.append(f"play:{url}")

    def stop(self):
        self.calls.append("stop")

    def set_output_window(self, window_id):
        self.calls.append(f"set_output_window:{window_id}")

    def set_hw_acceleration(self, enabled):
        self.calls.append(f"set_hw_acceleration:{enabled}")

    def update_engine_options(self, options):
        self.calls.append(f"update_engine_options:{options}")

    def set_muted(self, enabled):
        self.calls.append(f"set_muted:{enabled}")

    def set_volume(self, level):
        self.calls.append(f"set_volume:{level}")

    def release(self):
        self.calls.append("release")


def test_play_channel_stops_previous_playback_before_starting_channel():
    player = FakePlayer()
    manager = PlaybackManager(player)
    channel = Channel(name="News", url="http://example.test/news.m3u8")

    manager.play_channel(channel)

    assert player.calls == ["stop", "play:http://example.test/news.m3u8"]
    assert manager.current_channel == channel


def test_stop_playback_stops_player_and_clears_current_channel():
    player = FakePlayer()
    manager = PlaybackManager(player)
    channel = Channel(name="Sports", url="http://example.test/sports.m3u8")
    manager.play_channel(channel)

    manager.stop_playback()

    assert player.calls[-1] == "stop"
    assert manager.current_channel is None


def test_switch_player_engine_releases_old_player_and_resumes_current_channel():
    old_player = FakePlayer()
    new_player = FakePlayer()
    manager = PlaybackManager(old_player)
    channel = Channel(name="Movies", url="http://example.test/movies.m3u8")
    manager.play_channel(channel)

    manager.switch_player_engine(new_player, window_id=12345)

    assert old_player.calls[-2:] == ["stop", "release"]
    assert new_player.calls == [
        "set_output_window:12345",
        "set_muted:False",
        "set_volume:100",
        "stop",
        "play:http://example.test/movies.m3u8",
    ]
    assert manager.current_channel == channel

def test_set_muted_delegates_to_player():
    player = FakePlayer()
    manager = PlaybackManager(player)

    manager.set_muted(True)

    assert player.calls == ["set_muted:True"]

def test_set_volume_delegates_to_player():
    player = FakePlayer()
    manager = PlaybackManager(player)

    manager.set_volume(70)

    assert player.calls == ["set_volume:70"]

def test_switch_player_engine_reapplies_audio_state():
    old_player = FakePlayer()
    new_player = FakePlayer()
    manager = PlaybackManager(old_player)
    manager.set_muted(True)
    manager.set_volume(40)

    manager.switch_player_engine(new_player, window_id=1)

    assert "set_muted:True" in new_player.calls
    assert "set_volume:40" in new_player.calls
