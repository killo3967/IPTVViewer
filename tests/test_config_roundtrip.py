"""Pruebas herméticas de round-trip de configuración (REQ-8).

Usan ``tmp_path`` y el parámetro ``config_path`` de ``load_config``/``save_config``
para no tocar nunca el ``config.ini`` real.
"""
import configparser

from main import load_config, save_config


def _write_ini(path, settings: dict):
    parser = configparser.ConfigParser()
    parser["SETTINGS"] = settings
    with open(path, "w", encoding="utf-8") as f:
        parser.write(f)


def test_new_keys_survive_round_trip(tmp_path):
    path = tmp_path / "config.ini"
    config = {
        "sources": {0: {"name": "Lista 1", "m3u": "http://x/m3u", "filter": "SPAIN", "epg": ""}},
        "active": 0,
        "hw_acceleration": False,
        "player_engine": "vlc",
        "vlc_config": {},
        "mpv_config": {},
        "proxy_config": {},
        "view_mode": "compact",
        "splitter_state": "AAAA+/==",
        "pip_geometry": "1280,40,480,270",
    }

    save_config(config, path)
    loaded = load_config(path)

    assert loaded["view_mode"] == "compact"
    assert loaded["splitter_state"] == "AAAA+/=="
    assert loaded["pip_geometry"] == "1280,40,480,270"


def test_legacy_config_without_new_keys_loads_defaults(tmp_path):
    path = tmp_path / "config.ini"
    _write_ini(path, {"player_engine": "vlc", "hw_acceleration": "False", "active": "0"})

    loaded = load_config(path)

    assert loaded["view_mode"] == "normal"
    assert loaded["splitter_state"] == ""
    assert loaded["pip_geometry"] == ""


def test_invalid_persisted_view_mode_is_normalized(tmp_path):
    path = tmp_path / "config.ini"
    _write_ini(path, {"view_mode": "cinema"})

    loaded = load_config(path)

    assert loaded["view_mode"] == "normal"


def test_splitter_state_with_base64_alphabet_survives(tmp_path):
    path = tmp_path / "config.ini"
    config = {
        "sources": {},
        "active": 0,
        "hw_acceleration": False,
        "player_engine": "vlc",
        "vlc_config": {},
        "mpv_config": {},
        "proxy_config": {},
        "splitter_state": "A+/7/w==",
    }

    save_config(config, path)
    loaded = load_config(path)

    assert loaded["splitter_state"] == "A+/7/w=="
