"""Reescritura del host de bucle local en las URLs de una lista remota."""

import pytest

from src.infrastructure.utils.url_hosts import (
    is_loopback_host,
    normalize_loopback_host,
    source_authority,
)

#: Lista servida por xteve en la LAN (caso real que motivó esta utilidad).
SOURCE = "http://198.51.100.20:34400/m3u/xteve.m3u"


@pytest.mark.parametrize(
    "host",
    ["localhost", "LOCALHOST", "localhost.", "foo.localhost", "127.0.0.1", "::1", "0.0.0.0"],
)
def test_is_loopback_host_accepts_local_names(host):
    assert is_loopback_host(host) is True


@pytest.mark.parametrize(
    "host",
    ["10.20.30.40", "198.51.100.20", "raw.githubusercontent.com", "", "127.0.0.2"],
)
def test_is_loopback_host_rejects_everything_else(host):
    """Solo el bucle local es un error seguro: una IP privada puede ser válida."""
    assert is_loopback_host(host) is False


def test_source_authority_takes_host_and_port():
    assert source_authority(SOURCE) == "198.51.100.20:34400"


@pytest.mark.parametrize(
    "source", ["m3u/tv_channel.m3u", "", "C:\\listas\\tv.m3u", "ftp://host/list.m3u"]
)
def test_source_authority_is_empty_for_local_sources(source):
    assert source_authority(source) == ""


def test_normalize_swaps_loopback_host_for_the_playlist_host():
    url = "http://localhost:34400/data_images/AMC.png"

    assert normalize_loopback_host(url, SOURCE) == "http://198.51.100.20:34400/data_images/AMC.png"


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:34400/data_images/13TV.png",
        "http://LOCALHOST:34400/data_images/13TV.png",
        "http://localhost.:34400/data_images/13TV.png",
        "http://127.0.0.1:34400/data_images/13TV.png",
        "http://[::1]:34400/data_images/13TV.png",
        "http://0.0.0.0:34400/data_images/13TV.png",
    ],
)
def test_normalize_covers_every_loopback_form(url):
    assert normalize_loopback_host(url, SOURCE) == "http://198.51.100.20:34400/data_images/13TV.png"


def test_normalize_keeps_the_path_byte_for_byte():
    """Ni el espacio ni el %20 se re-codifican: eso rompería los nombres."""
    con_espacio = "http://localhost:34400/data_images/amc crime.png"
    con_escape = "http://localhost:34400/data_images/amc%20crime.png"

    assert normalize_loopback_host(con_espacio, SOURCE).endswith("/data_images/amc crime.png")
    assert normalize_loopback_host(con_escape, SOURCE).endswith("/data_images/amc%20crime.png")


def test_normalize_keeps_query_fragment_and_credentials():
    url = "http://usuario:clave@localhost:34400/data_images/AMC.png?v=2#top"

    assert (
        normalize_loopback_host(url, SOURCE)
        == "http://usuario:clave@198.51.100.20:34400/data_images/AMC.png?v=2#top"
    )


def test_normalize_keeps_the_logo_scheme():
    url = "https://localhost:34400/data_images/AMC.png"

    assert normalize_loopback_host(url, SOURCE).startswith("https://198.51.100.20:34400/")


def test_normalize_takes_the_playlist_port_when_the_logo_has_none():
    url = "http://localhost/data_images/AMC.png"

    assert normalize_loopback_host(url, SOURCE) == "http://198.51.100.20:34400/data_images/AMC.png"


def test_normalize_drops_the_port_when_the_playlist_has_none():
    url = "http://localhost:34400/data_images/AMC.png"

    assert (
        normalize_loopback_host(url, "http://198.51.100.20/m3u/xteve.m3u")
        == "http://198.51.100.20/data_images/AMC.png"
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://10.20.30.40:34400/images/abc.png",
        "https://raw.githubusercontent.com/davidmuma/picons/master/icon/x.png",
        "http://198.51.100.20:34400/data_images/AMC.png",
    ],
)
def test_normalize_leaves_other_hosts_untouched(url):
    assert normalize_loopback_host(url, SOURCE) == url


@pytest.mark.parametrize("url", ["", None])
def test_normalize_tolerates_missing_logo(url):
    assert normalize_loopback_host(url, SOURCE) == url


def test_normalize_does_nothing_when_the_source_is_a_local_file():
    url = "http://localhost:34400/data_images/AMC.png"

    assert normalize_loopback_host(url, "m3u/tv_channel.m3u") == url
