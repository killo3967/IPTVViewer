"""Pruebas del servicio de modos de vista (Qt-free).

Cubre REQ-1 (enum de modos + serialización) y, en unidades posteriores,
el controlador de estado, el índice de zapping y los helpers de geometría.
"""
from src.application.services.view_mode_controller import (
    ViewMode,
    ViewModeController,
    decode_splitter_state,
    encode_splitter_state,
    geometry_to_str,
    resolve_zap_index,
    str_to_geometry,
)
from src.domain.entities.channel import Channel


def test_view_mode_values_are_serialized_strings():
    assert ViewMode.NORMAL.value == "normal"
    assert ViewMode.COMPACT.value == "compact"
    assert ViewMode.VIDEO.value == "video"


def test_parse_round_trips_known_modes():
    assert ViewMode.parse("normal") is ViewMode.NORMAL
    assert ViewMode.parse("compact") is ViewMode.COMPACT
    assert ViewMode.parse("video") is ViewMode.VIDEO


def test_parse_unknown_persisted_string_falls_back_to_normal():
    assert ViewMode.parse("cinema") is ViewMode.NORMAL


def test_parse_none_falls_back_to_normal():
    assert ViewMode.parse(None) is ViewMode.NORMAL


def test_parse_empty_string_falls_back_to_normal():
    assert ViewMode.parse("") is ViewMode.NORMAL


def test_new_controller_defaults_to_normal():
    controller = ViewModeController()
    assert controller.mode is ViewMode.NORMAL


def test_activate_switches_mode():
    controller = ViewModeController()
    assert controller.activate(ViewMode.COMPACT) is True
    assert controller.mode is ViewMode.COMPACT


def test_reactivating_active_mode_is_noop_without_notification():
    controller = ViewModeController(ViewMode.COMPACT)
    notifications = []
    controller.register_listener(lambda old, new: notifications.append((old, new)))

    assert controller.activate(ViewMode.COMPACT) is False
    assert controller.mode is ViewMode.COMPACT
    assert notifications == []


def test_listeners_receive_old_new_only_on_real_change():
    controller = ViewModeController()
    notifications = []
    controller.register_listener(lambda old, new: notifications.append((old, new)))

    assert controller.activate(ViewMode.VIDEO) is True
    assert notifications == [(ViewMode.NORMAL, ViewMode.VIDEO)]


def _channels():
    return [
        Channel(name="c1", url="http://test/c1"),
        Channel(name="c2", url="http://test/c2"),
        Channel(name="c3", url="http://test/c3"),
    ]


def test_zap_down_resolves_next_channel():
    channels = _channels()
    assert resolve_zap_index(channels, channels[0], +1) == 1


def test_zap_down_at_last_wraps_to_first():
    channels = _channels()
    assert resolve_zap_index(channels, channels[2], +1) == 0


def test_zap_up_at_first_wraps_to_last():
    channels = _channels()
    assert resolve_zap_index(channels, channels[0], -1) == 2


def test_zap_up_resolves_previous_channel():
    channels = _channels()
    assert resolve_zap_index(channels, channels[2], -1) == 1


def test_zap_on_empty_playlist_returns_none():
    assert resolve_zap_index([], Channel(name="c", url="http://test/c"), +1) is None


def test_zap_with_no_current_channel_returns_zero():
    channels = _channels()
    assert resolve_zap_index(channels, None, +1) == 0
    assert resolve_zap_index(channels, None, -1) == 0


def test_zap_with_current_not_in_playlist_returns_zero():
    channels = _channels()
    stale = Channel(name="stale", url="http://test/stale")
    assert resolve_zap_index(channels, stale, +1) == 0


def test_zap_matches_by_url_when_two_channels_share_url():
    channels = _channels()
    twin = Channel(name="c2-copy", url="http://test/c2")
    assert resolve_zap_index(channels, twin, +1) == 2


def test_zap_matches_by_full_equality_when_urls_differ():
    channels = _channels()
    same = Channel(name="c2", url="http://test/c2")
    assert resolve_zap_index(channels, same, +1) == 2


def test_geometry_to_str_formats_xywh():
    assert geometry_to_str(1280, 40, 480, 270) == "1280,40,480,270"


def test_geometry_round_trip():
    assert str_to_geometry(geometry_to_str(1280, 40, 480, 270)) == (1280, 40, 480, 270)


def test_geometry_allows_negative_coordinates():
    assert str_to_geometry("-1920,100,640,360") == (-1920, 100, 640, 360)


def test_geometry_rejects_non_positive_size():
    assert str_to_geometry("10,10,0,100") is None
    assert str_to_geometry("10,10,100,-5") is None


def test_geometry_rejects_wrong_field_count():
    assert str_to_geometry("10,10,100") is None
    assert str_to_geometry("10,10,100,200,300") is None


def test_geometry_rejects_non_integers():
    assert str_to_geometry("a,b,c,d") is None
    assert str_to_geometry("10,10.5,100,200") is None


def test_geometry_rejects_empty_string():
    assert str_to_geometry("") is None


def test_splitter_state_round_trip():
    state = b"\x00\x01QSplitter\xff\x01\x02\x03"
    assert decode_splitter_state(encode_splitter_state(state)) == state


def test_splitter_state_base64_alphabet_survives():
    # "+ / =" aparecen en la codificación base64 real de saveState()
    state = b"\xff\xef\xfb\xff"
    encoded = encode_splitter_state(state)
    assert encoded == "/+/7/w=="
    assert decode_splitter_state(encoded) == state


def test_splitter_state_garbage_decodes_to_none():
    assert decode_splitter_state("not-base64!!!") is None


def test_splitter_state_empty_string_decodes_to_none():
    assert decode_splitter_state("") is None
