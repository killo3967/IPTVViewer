"""Política de reintentos del adaptador VLC: backoff, tope y cancelación."""

from typing import ClassVar

import pytest

from src.infrastructure.adapters import vlc_player_adapter as mod


class _FakeMedia:
    def add_option(self, *_args, **_kwargs):
        return None


class _FakePlayer:
    def __init__(self):
        self.play_calls = 0
        self.stop_calls = 0

    def set_media(self, media):
        self.media = media

    def play(self):
        self.play_calls += 1

    def stop(self):
        self.stop_calls += 1


class _FakeInstance:
    def media_new(self, url):
        self.last_url = url
        return _FakeMedia()


class _FakeTimer:
    """Timer de mentira: registra el retardo y se dispara a mano."""

    instances: ClassVar[list["_FakeTimer"]] = []

    def __init__(self, delay, function, args=()):
        self.delay = delay
        self.function = function
        self.args = args
        self.cancelled = False
        self.started = False
        _FakeTimer.instances.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        self.function(*self.args)


@pytest.fixture
def adapter(monkeypatch):
    _FakeTimer.instances = []
    monkeypatch.setattr(mod.threading, "Timer", _FakeTimer)
    instance = mod.VlcPlayerAdapter.__new__(mod.VlcPlayerAdapter)
    instance._player = _FakePlayer()
    instance._instance = _FakeInstance()
    instance._current_url = None
    instance._retry_count = 0
    instance._retry_timer = None
    instance._retry_token = 0
    instance.on_retry_exhausted = None
    instance._config = {"network_caching": 1000, "hw_acceleration": False}
    return instance


def test_errors_use_exponential_backoff_capped_at_ten_seconds(adapter):
    adapter.play("http://canal")
    for _ in range(mod.VlcPlayerAdapter.RETRY_MAX_ATTEMPTS):
        adapter._on_error_encountered(None)

    assert [timer.delay for timer in _FakeTimer.instances] == [1.0, 2.0, 4.0, 8.0, 10.0, 10.0]


def test_eof_retry_uses_short_delay(adapter):
    adapter.play("http://canal")

    adapter._on_end_reached(None)

    assert _FakeTimer.instances[-1].delay == pytest.approx(mod.VlcPlayerAdapter.EOF_BASE_DELAY)


def test_retries_exhausted_notifies_once_and_stops(adapter):
    notified = []
    adapter.on_retry_exhausted = lambda: notified.append(True)
    adapter.play("http://canal")

    for _ in range(mod.VlcPlayerAdapter.RETRY_MAX_ATTEMPTS + 1):
        adapter._on_error_encountered(None)

    assert notified == [True]
    assert len(_FakeTimer.instances) == mod.VlcPlayerAdapter.RETRY_MAX_ATTEMPTS
    assert adapter._retry_count == 0
    assert adapter._retry_timer is None


def test_retry_plays_the_same_channel_when_still_current(adapter):
    adapter.play("http://uno")
    adapter._on_error_encountered(None)
    timer = _FakeTimer.instances[-1]
    plays_before = adapter._player.play_calls

    timer.fire()

    assert adapter._player.play_calls == plays_before + 1


def test_stale_retry_does_not_reopen_previous_channel(adapter):
    adapter.play("http://uno")
    adapter._on_error_encountered(None)
    stale_timer = _FakeTimer.instances[-1]

    adapter.play("http://dos")
    plays_before = adapter._player.play_calls
    stale_timer.fire()

    assert adapter._player.play_calls == plays_before


def test_play_resets_attempts_and_cancels_pending_retry(adapter):
    adapter.play("http://uno")
    for _ in range(3):
        adapter._on_error_encountered(None)
    pending = adapter._retry_timer
    assert adapter._retry_count == 3

    adapter.play("http://dos")

    assert adapter._retry_count == 0
    assert pending is not None and pending.cancelled is True
    assert adapter._retry_timer is None


def test_stop_cancels_pending_retry(adapter):
    adapter.play("http://uno")
    adapter._on_error_encountered(None)
    pending = adapter._retry_timer

    adapter.stop()

    assert pending is not None and pending.cancelled is True
    assert adapter._retry_count == 0
    assert adapter._player.stop_calls == 1


def test_playing_event_resets_attempts_and_cancels_retry(adapter):
    adapter.play("http://uno")
    for _ in range(2):
        adapter._on_error_encountered(None)
    pending = adapter._retry_timer

    adapter._on_playing(None)

    assert adapter._retry_count == 0
    assert pending is not None and pending.cancelled is True
    assert adapter._retry_timer is None


def test_retry_exhausted_callback_error_does_not_escape(adapter):
    def boom():
        raise RuntimeError("ui rota")

    adapter.on_retry_exhausted = boom
    adapter.play("http://canal")

    for _ in range(mod.VlcPlayerAdapter.RETRY_MAX_ATTEMPTS + 1):
        adapter._on_error_encountered(None)
