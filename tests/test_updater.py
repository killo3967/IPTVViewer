"""Lógica de autoactualización: comparar versiones, elegir asset y verificar."""

from datetime import datetime, timedelta
from unittest import mock

import pytest

from src.infrastructure.utils.updater import (
    CHECK_INTERVAL,
    UpdateInfo,
    download,
    is_newer,
    parse_release,
    setup_arguments,
    sha256_of,
    should_check,
    verify_digest,
    version_tuple,
)

DIGEST = "sha256:" + "a" * 64


def _payload(tag="v1.10.0", setup=True, digest=DIGEST):
    assets = [
        {
            "name": "IPTVViewer.exe",
            "browser_download_url": "https://x/IPTVViewer.exe",
            "digest": "sha256:" + "b" * 64,
        },
    ]
    if setup:
        assets.insert(
            0,
            {
                "name": "IPTVViewer-Setup-1.10.0.exe",
                "browser_download_url": "https://x/IPTVViewer-Setup-1.10.0.exe",
                "digest": digest,
            },
        )
    return {
        "tag_name": tag,
        "body": "## Novedades\n- algo",
        "html_url": "https://x/releases/tag/1.10.0",
        "assets": assets,
    }


@pytest.mark.parametrize(
    ("candidate", "current", "esperado"),
    [
        ("1.10.0", "1.9.0", True),
        ("1.9.10", "1.9.9", True),
        ("2.0.0", "1.99.99", True),
        ("1.9.0", "1.9.0", False),
        ("1.8.9", "1.9.0", False),
        ("", "1.9.0", False),
    ],
)
def test_is_newer_compares_numerically(candidate, current, esperado):
    assert is_newer(candidate, current) is esperado


def test_version_tuple_tolerates_garbage():
    assert version_tuple("1.9.0") == (1, 9, 0)
    assert version_tuple("no-es-version") == (0,)


def test_should_check_when_never_checked():
    assert should_check("") is True


def test_should_check_respects_the_interval():
    ahora = datetime(2026, 10, 29, 12, 0, 0)
    hace_una_hora = (ahora - timedelta(hours=1)).isoformat(sep=" ")
    hace_dos_dias = (ahora - timedelta(days=2)).isoformat(sep=" ")

    assert should_check(hace_una_hora, ahora) is False
    assert should_check(hace_dos_dias, ahora) is True
    assert should_check(hace_una_hora, ahora + CHECK_INTERVAL + timedelta(minutes=1)) is True


def test_should_check_ignores_a_corrupt_timestamp():
    assert should_check("ayer") is True


def test_parse_release_prefers_the_setup_asset():
    info = parse_release(_payload(), "1.9.0")

    assert info is not None
    assert info.version == "1.10.0"
    assert info.asset_name == "IPTVViewer-Setup-1.10.0.exe"
    assert info.digest == DIGEST
    assert info.page_url.endswith("1.10.0")
    assert info.can_self_update is True


def test_parse_release_falls_back_to_the_bare_exe():
    info = parse_release(_payload(setup=False), "1.9.0")

    assert info is not None
    assert info.asset_name == "IPTVViewer.exe"


def test_parse_release_returns_none_when_not_newer():
    assert parse_release(_payload(tag="v1.9.0"), "1.9.0") is None


def test_parse_release_returns_none_without_assets():
    payload = _payload()
    payload["assets"] = []

    assert parse_release(payload, "1.9.0") is None


def test_update_without_digest_cannot_self_update():
    info = parse_release(_payload(digest=""), "1.9.0")

    assert info is not None
    assert info.can_self_update is False


def test_verify_digest_accepts_the_published_hash(tmp_path):
    fichero = tmp_path / "setup.exe"
    fichero.write_bytes(b"instalador")
    esperado = "sha256:" + sha256_of(fichero)

    assert verify_digest(fichero, esperado) is True
    assert verify_digest(fichero, esperado.upper().replace("SHA256", "sha256")) is True


@pytest.mark.parametrize("digest", ["", "md5:abc", "sha256:corta", None])
def test_verify_digest_refuses_anything_but_sha256(tmp_path, digest):
    fichero = tmp_path / "setup.exe"
    fichero.write_bytes(b"instalador")

    assert verify_digest(fichero, digest) is False


def test_verify_digest_detects_a_tampered_file(tmp_path):
    fichero = tmp_path / "setup.exe"
    fichero.write_bytes(b"instalador")
    esperado = "sha256:" + "0" * 64

    assert verify_digest(fichero, esperado) is False


def test_setup_arguments_are_silent_and_close_the_app():
    argumentos = setup_arguments()

    assert "/VERYSILENT" in argumentos
    assert "/CLOSEAPPLICATIONS" in argumentos
    assert "/SUPPRESSMSGBOXES" in argumentos


def test_download_writes_the_file_and_accepts_the_digest(tmp_path):
    contenido = b"instalador de prueba"
    respuesta = mock.MagicMock()
    respuesta.headers = {"Content-Length": str(len(contenido))}
    respuesta.iter_content.return_value = [contenido]
    respuesta.__enter__.return_value = respuesta
    destino = tmp_path / "IPTVViewer-Setup-1.10.0.exe"
    progreso = []

    with mock.patch("requests.get", return_value=respuesta):
        ruta = download(
            "https://x/setup.exe",
            destino,
            "sha256:" + __import__("hashlib").sha256(contenido).hexdigest(),
            progress=lambda hechos, total: progreso.append((hechos, total)),
        )

    assert ruta == destino
    assert destino.read_bytes() == contenido
    assert progreso and progreso[-1] == (len(contenido), len(contenido))
    assert not destino.with_suffix(destino.suffix + ".part").exists()


def test_download_discards_the_file_when_the_digest_fails(tmp_path):
    respuesta = mock.MagicMock()
    respuesta.headers = {"Content-Length": "3"}
    respuesta.iter_content.return_value = [b"mal"]
    respuesta.__enter__.return_value = respuesta
    destino = tmp_path / "setup.exe"

    with mock.patch("requests.get", return_value=respuesta), pytest.raises(ValueError):
        download("https://x/setup.exe", destino, "sha256:" + "0" * 64)

    assert not destino.exists()
    assert not destino.with_suffix(destino.suffix + ".part").exists()


def test_update_info_exposes_the_candidate_version():
    info = UpdateInfo(
        version="1.10.0",
        notes="",
        asset_name="a.exe",
        asset_url="https://x/a.exe",
        digest=DIGEST,
        page_url="",
    )

    assert info.version == "1.10.0"
    assert info.can_self_update is True
