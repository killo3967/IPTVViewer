import builtins
import importlib
import sys
import types
from typing import Any

import pytest


class _FakeMpvInstance:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def property_observer(self, _name):
        def decorator(func):
            return func

        return decorator


def _import_mpv_adapter(monkeypatch):
    fake_mpv = types.ModuleType("mpv")
    captured: dict[str, Any] = {}

    def build_player(**kwargs):
        player = _FakeMpvInstance(**kwargs)
        captured["player"] = player
        captured["kwargs"] = kwargs
        return player

    fake_mpv.MPV = build_player  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mpv", fake_mpv)
    sys.modules.pop("src.infrastructure.adapters.mpv_player_adapter", None)
    module = importlib.import_module("src.infrastructure.adapters.mpv_player_adapter")
    return module, captured


class _FakeVlcModule(types.ModuleType):
    class EventType:
        MediaPlayerEndReached = object()
        MediaPlayerEncounteredError = object()

    class _FakeEvents:
        def event_attach(self, *_args, **_kwargs):
            return None

    class _FakePlayer:
        def event_manager(self):
            return _FakeVlcModule._FakeEvents()

        def audio_set_volume(self, *_args, **_kwargs):
            return None

        def set_media(self, *_args, **_kwargs):
            return None

        def play(self):
            return None

        def stop(self):
            return None

        def release(self):
            return None

    class _FakeInstance:
        def media_player_new(self):
            return _FakeVlcModule._FakePlayer()

        def media_new(self, *_args, **_kwargs):
            return types.SimpleNamespace(add_option=lambda *_a, **_k: None)

        def release(self):
            return None

    def Instance(self, *_args, **_kwargs):
        return self._FakeInstance()


def _import_vlc_adapter(monkeypatch):
    fake_vlc = _FakeVlcModule("vlc")
    monkeypatch.setitem(sys.modules, "vlc", fake_vlc)
    sys.modules.pop("src.infrastructure.adapters.vlc_player_adapter", None)
    module = importlib.import_module("src.infrastructure.adapters.vlc_player_adapter")
    return module


def test_mpv_log_handler_ignores_os_error(monkeypatch):
    module, captured = _import_mpv_adapter(monkeypatch)
    adapter = module.MpvPlayerAdapter(mpv_config={"file_logging": True})

    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("disk full")))

    captured["kwargs"]["log_handler"]("info", "mpv", "hello")

    assert adapter._player is captured["player"]


def test_mpv_log_handler_propagates_unexpected_errors(monkeypatch):
    module, captured = _import_mpv_adapter(monkeypatch)
    module.MpvPlayerAdapter(mpv_config={"file_logging": True})

    monkeypatch.setattr(builtins, "open", lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad open")))

    with pytest.raises(ValueError, match="bad open"):
        captured["kwargs"]["log_handler"]("info", "mpv", "hello")


def test_mpv_release_ignores_expected_terminate_errors(monkeypatch):
    module, _captured = _import_mpv_adapter(monkeypatch)
    adapter = module.MpvPlayerAdapter.__new__(module.MpvPlayerAdapter)

    class FakePlayer:
        def terminate(self):
            raise OSError("already gone")

    adapter._player = FakePlayer()

    adapter.release()

    assert adapter._player is None


def test_mpv_release_propagates_unexpected_terminate_errors(monkeypatch):
    module, _captured = _import_mpv_adapter(monkeypatch)
    adapter = module.MpvPlayerAdapter.__new__(module.MpvPlayerAdapter)

    class FakePlayer:
        def terminate(self):
            raise ValueError("bad terminate")

    adapter._player = FakePlayer()

    with pytest.raises(ValueError, match="bad terminate"):
        adapter.release()


def test_vlc_release_ignores_expected_player_errors(monkeypatch):
    module = _import_vlc_adapter(monkeypatch)
    adapter = module.VlcPlayerAdapter.__new__(module.VlcPlayerAdapter)

    class FakePlayer:
        def stop(self):
            raise OSError("already stopped")

        def release(self):
            raise OSError("already released")

    adapter._player = FakePlayer()
    adapter._instance = None

    adapter.release()

    assert adapter._player is None


def test_vlc_release_ignores_expected_instance_errors(monkeypatch):
    module = _import_vlc_adapter(monkeypatch)
    adapter = module.VlcPlayerAdapter.__new__(module.VlcPlayerAdapter)

    class FakeInstance:
        def release(self):
            raise OSError("already released")

    adapter._player = None
    adapter._instance = FakeInstance()

    adapter.release()

    assert adapter._instance is None


def test_vlc_release_propagates_unexpected_player_errors(monkeypatch):
    module = _import_vlc_adapter(monkeypatch)
    adapter = module.VlcPlayerAdapter.__new__(module.VlcPlayerAdapter)

    class FakePlayer:
        def stop(self):
            raise ValueError("bad stop")

        def release(self):
            return None

    adapter._player = FakePlayer()
    adapter._instance = None

    with pytest.raises(ValueError, match="bad stop"):
        adapter.release()


def test_vlc_release_propagates_unexpected_instance_errors(monkeypatch):
    module = _import_vlc_adapter(monkeypatch)
    adapter = module.VlcPlayerAdapter.__new__(module.VlcPlayerAdapter)

    class FakeInstance:
        def release(self):
            raise ValueError("bad instance release")

    adapter._player = None
    adapter._instance = FakeInstance()

    with pytest.raises(ValueError, match="bad instance release"):
        adapter.release()
