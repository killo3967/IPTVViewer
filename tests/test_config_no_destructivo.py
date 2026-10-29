"""save_config no debe borrar lo que no gestiona.

El fichero config.ini puede contener secciones de otras herramientas (por
ejemplo ``[listmanager.target.0]``). Reconstruirlo desde cero las eliminaba en
cada guardado, y desde que la app comprueba actualizaciones a diario el guardado
ocurre también sin que el usuario toque nada.
"""

import configparser

from main import load_config, save_config


def _config_minima() -> dict:
    return {
        "sources": {0: {"name": "Lista 1", "m3u": "http://x/m3u", "filter": "SPAIN", "epg": ""}},
        "active": 0,
        "hw_acceleration": False,
        "player_engine": "vlc",
        "vlc_config": {},
        "mpv_config": {},
        "proxy_config": {},
    }


def _escribir(path, secciones: dict[str, dict[str, str]]) -> None:
    parser = configparser.ConfigParser()
    for nombre, valores in secciones.items():
        parser[nombre] = valores
    with open(path, "w", encoding="utf-8") as fichero:
        parser.write(fichero)


def test_save_config_keeps_sections_from_other_tools(tmp_path):
    """Una sección ajena a la app sobrevive al guardado."""
    path = tmp_path / "config.ini"
    _escribir(path, {
        "SETTINGS": {"active": "0"},
        "source.0": {"name": "Lista 1", "m3u": "http://x/m3u", "filter": "", "epg": ""},
        "listmanager.target.0": {
            "name": "prueba", "source": "0", "rules": "group-title:spain:0",
            "port": "8080", "bind": "127.0.0.1",
        },
    })

    save_config(_config_minima(), path)

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    assert parser.has_section("listmanager.target.0")
    assert parser["listmanager.target.0"]["port"] == "8080"
    assert parser["listmanager.target.0"]["bind"] == "127.0.0.1"


def test_save_config_keeps_unknown_keys_inside_known_sections(tmp_path):
    """Una clave que la app no conoce no se pierde al guardar su sección."""
    path = tmp_path / "config.ini"
    _escribir(path, {"SETTINGS": {"active": "0", "clave_futura": "valor"}})

    save_config(_config_minima(), path)

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    assert parser["SETTINGS"]["clave_futura"] == "valor"
    assert parser["SETTINGS"]["player_engine"] == "vlc"


def test_save_config_removes_sources_that_no_longer_exist(tmp_path):
    """Las secciones source.N sí son de la app: las que sobran se eliminan."""
    path = tmp_path / "config.ini"
    _escribir(path, {
        "SETTINGS": {"active": "0"},
        "source.0": {"name": "Lista 1", "m3u": "http://x/m3u", "filter": "", "epg": ""},
        "source.7": {"name": "Borrada", "m3u": "http://y/m3u", "filter": "", "epg": ""},
    })

    save_config(_config_minima(), path)

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    assert parser.has_section("source.0")
    assert not parser.has_section("source.7")


def test_save_config_still_updates_the_values_it_owns(tmp_path):
    path = tmp_path / "config.ini"
    _escribir(path, {
        "SETTINGS": {"active": "0", "view_mode": "normal", "clave_futura": "valor"},
    })

    config = _config_minima()
    config["view_mode"] = "compact"
    config["splitter_state"] = "AAAA+/=="
    save_config(config, path)

    recargada = load_config(path)
    assert recargada["view_mode"] == "compact"
    assert recargada["splitter_state"] == "AAAA+/=="


def test_save_config_recovers_from_a_corrupt_file(tmp_path):
    """Un fichero ilegible no debe impedir guardar: se reescribe limpio."""
    path = tmp_path / "config.ini"
    path.write_text("esto no es un ini\n%%%\n[sin_cerrar\n", encoding="utf-8")

    save_config(_config_minima(), path)

    recargada = load_config(path)
    assert recargada["player_engine"] == "vlc"
    assert recargada["sources"][0]["name"] == "Lista 1"


def test_save_config_works_when_the_file_does_not_exist(tmp_path):
    path = tmp_path / "nueva.ini"

    save_config(_config_minima(), path)

    assert path.exists()
    assert load_config(path)["sources"][0]["m3u"] == "http://x/m3u"
