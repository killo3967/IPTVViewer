"""Extracción de .7z con extractores externos (tar.exe de Windows / 7-Zip)."""

from unittest import mock

import pytest

from src.infrastructure.utils.sevenzip import (
    SevenZipExtractError,
    extract_7z,
    windows_tar_path,
)

FAKE_TAR = r"C:\Windows\System32\tar.exe"
FAKE_7Z = r"C:\Program Files\7-Zip\7z.exe"


def test_windows_tar_path_uses_system32(monkeypatch):
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    with mock.patch("pathlib.Path.is_file", return_value=True):
        assert windows_tar_path() == r"C:\Windows\System32\tar.exe"


def test_windows_tar_path_none_when_missing(monkeypatch):
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    with mock.patch("pathlib.Path.is_file", return_value=False):
        assert windows_tar_path() is None


def test_extract_7z_uses_tar_first(tmp_path):
    archive = tmp_path / "a.7z"
    dest = tmp_path / "out"
    with mock.patch(
        "src.infrastructure.utils.sevenzip.windows_tar_path", return_value=FAKE_TAR
    ), mock.patch(
        "src.infrastructure.utils.sevenzip.subprocess.run"
    ) as run_mock:
        extract_7z(archive, dest, targets=["libmpv-2.dll"])

    run_mock.assert_called_once()
    cmd = run_mock.call_args.args[0]
    assert cmd[0] == FAKE_TAR
    assert "-C" in cmd and str(dest) in cmd
    assert "libmpv-2.dll" in cmd


def test_extract_7z_falls_back_to_7z_when_tar_unavailable(tmp_path):
    archive = tmp_path / "a.7z"
    dest = tmp_path / "out"
    with mock.patch(
        "src.infrastructure.utils.sevenzip.windows_tar_path", return_value=None
    ), mock.patch(
        "src.infrastructure.utils.sevenzip.shutil.which", return_value=FAKE_7Z
    ), mock.patch(
        "src.infrastructure.utils.sevenzip.subprocess.run"
    ) as run_mock:
        extract_7z(archive, dest)

    run_mock.assert_called_once()
    cmd = run_mock.call_args.args[0]
    assert cmd[0] == FAKE_7Z
    assert cmd[1] == "x"  # "x" preserva la estructura de directorios


def test_extract_7z_raises_when_no_extractor(tmp_path):
    archive = tmp_path / "a.7z"
    dest = tmp_path / "out"
    with mock.patch(
        "src.infrastructure.utils.sevenzip.windows_tar_path", return_value=None
    ), mock.patch(
        "src.infrastructure.utils.sevenzip.shutil.which", return_value=None
    ), pytest.raises(SevenZipExtractError):
        extract_7z(archive, dest)


def test_extract_7z_raises_when_all_extractors_fail(tmp_path):
    archive = tmp_path / "a.7z"
    dest = tmp_path / "out"
    with mock.patch(
        "src.infrastructure.utils.sevenzip.windows_tar_path", return_value=FAKE_TAR
    ), mock.patch(
        "src.infrastructure.utils.sevenzip.shutil.which", return_value=FAKE_7Z
    ), mock.patch(
        "src.infrastructure.utils.sevenzip.subprocess.run",
        side_effect=OSError("boom"),
    ), pytest.raises(SevenZipExtractError):
        extract_7z(archive, dest)
