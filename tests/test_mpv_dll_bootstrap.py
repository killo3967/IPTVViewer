"""Bootstrap de libmpv-2.dll: descarga en runtime para el motor mpv.

El exe ya no empaqueta libmpv-2.dll; la app la descarga (release pineada
20260814 de shinchiro/mpv-winbuild-cmake) la primera vez que se arranca con
el motor mpv. El módulo es puro (sin PyQt): el progreso se reporta vía
callback y el fallo de descarga/extracción lanza ``MpvDllBootstrapError``.

Estos tests NO usan red real ni la DLL real: ``requests.get`` y
``py7zr.SevenZipFile`` van mockeados.
"""

from pathlib import Path
from unittest import mock

import pytest
import requests

from src.infrastructure.utils.mpv_dll_bootstrap import (
    MPV_ARCHIVE_URL,
    MPV_DLL_FILENAME,
    MpvDllBootstrapError,
    ensure_libmpv_dll,
    is_libmpv_available,
    libmpv_dll_path,
)

FAKE_DLL_CONTENT = b"fake-libmpv-2.dll"


def _make_dll(bin_dir: Path) -> Path:
    dll = libmpv_dll_path(bin_dir)
    bin_dir.mkdir(parents=True, exist_ok=True)
    dll.write_bytes(FAKE_DLL_CONTENT)
    return dll


class FakeResponse:
    """Respuesta HTTP mínima para ``requests.get(stream=True)``."""

    def __init__(self, content: bytes, headers: dict | None = None):
        self.content = content
        self.headers = headers or {"Content-Length": str(len(content))}

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size: int):
        for i in range(0, len(self.content), chunk_size):
            yield self.content[i : i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSevenZipFile:
    """Fake de ``py7zr.SevenZipFile``: escribe la DLL extraída en el destino."""

    def __init__(self, archive_path):
        self.archive_path = archive_path

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract(self, path, targets):
        Path(path, MPV_DLL_FILENAME).write_bytes(FAKE_DLL_CONTENT)


# --- is_libmpv_available ---


def test_is_libmpv_available_true_when_dll_exists(tmp_path):
    _make_dll(tmp_path)
    assert is_libmpv_available(tmp_path) is True


def test_is_libmpv_available_false_when_missing(tmp_path):
    assert is_libmpv_available(tmp_path) is False


def test_is_libmpv_available_false_when_empty_file(tmp_path):
    _make_dll(tmp_path).write_bytes(b"")
    assert is_libmpv_available(tmp_path) is False


# --- libmpv_dll_path ---


def test_libmpv_dll_path_joins_bin_dir(tmp_path):
    assert libmpv_dll_path(tmp_path) == tmp_path / "libmpv-2.dll"


# --- ensure_libmpv_dll ---


def test_ensure_does_not_download_when_dll_exists(tmp_path):
    _make_dll(tmp_path)
    with mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.requests.get"
    ) as get, mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.py7zr.SevenZipFile"
    ) as sevenzip:
        result = ensure_libmpv_dll(tmp_path)
    assert result == libmpv_dll_path(tmp_path)
    get.assert_not_called()
    sevenzip.assert_not_called()


def test_ensure_downloads_extracts_and_moves_dll(tmp_path):
    bin_dir = tmp_path / "bin"  # no existe: hay que crearlo
    sevenzip_factory = mock.Mock(side_effect=FakeSevenZipFile)
    with mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.requests.get",
        return_value=FakeResponse(b"7z-fake-archive-bytes"),
    ) as get, mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.py7zr.SevenZipFile",
        sevenzip_factory,
    ):
        result = ensure_libmpv_dll(bin_dir)

    assert result == bin_dir / "libmpv-2.dll"
    assert result.read_bytes() == FAKE_DLL_CONTENT
    get.assert_called_once_with(MPV_ARCHIVE_URL, stream=True, timeout=120)
    sevenzip_factory.assert_called_once()
    # El .7z temporal se pasa al extractor y queda eliminado al terminar
    archive_arg = sevenzip_factory.call_args.args[0]
    assert archive_arg.exists() is False


def test_ensure_reports_progress(tmp_path):
    archive_bytes = b"x" * 512
    progress_calls: list[tuple[int, int]] = []
    with mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.requests.get",
        return_value=FakeResponse(archive_bytes),
    ), mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.py7zr.SevenZipFile",
        FakeSevenZipFile,
    ):
        ensure_libmpv_dll(tmp_path, progress=lambda d, t: progress_calls.append((d, t)))

    assert progress_calls
    assert progress_calls[-1] == (len(archive_bytes), len(archive_bytes))
    for downloaded, total in progress_calls:
        assert 0 <= downloaded <= total


def test_ensure_cleans_temporary_directory(tmp_path):
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    with mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.requests.get",
        return_value=FakeResponse(b"7z-fake-archive-bytes"),
    ), mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.py7zr.SevenZipFile",
        FakeSevenZipFile,
    ), mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.tempfile.mkdtemp",
        return_value=str(temp_root),
    ):
        ensure_libmpv_dll(tmp_path / "bin")
    assert temp_root.exists() is False
    assert sorted(p.name for p in tmp_path.iterdir()) == ["bin"]


def test_ensure_raises_bootstrap_error_on_download_failure(tmp_path):
    with mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.requests.get",
        side_effect=requests.exceptions.ConnectionError("boom"),
    ), pytest.raises(MpvDllBootstrapError):
        ensure_libmpv_dll(tmp_path)


def test_ensure_raises_bootstrap_error_on_extract_failure(tmp_path):
    class BrokenSevenZip:
        def __init__(self, archive_path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract(self, path, targets):
            raise ValueError("archivo 7z corrupto")

    with mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.requests.get",
        return_value=FakeResponse(b"7z-fake-archive-bytes"),
    ), mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.py7zr.SevenZipFile",
        BrokenSevenZip,
    ), pytest.raises(MpvDllBootstrapError):
        ensure_libmpv_dll(tmp_path)


def test_ensure_raises_bootstrap_error_when_dll_missing_in_archive(tmp_path):
    class SevenZipWithoutDll:
        def __init__(self, archive_path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract(self, path, targets):
            pass  # no extrae nada: el .7z no contenía la DLL

    with mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.requests.get",
        return_value=FakeResponse(b"7z-fake-archive-bytes"),
    ), mock.patch(
        "src.infrastructure.utils.mpv_dll_bootstrap.py7zr.SevenZipFile",
        SevenZipWithoutDll,
    ), pytest.raises(MpvDllBootstrapError):
        ensure_libmpv_dll(tmp_path)
