"""Bootstrap de VLC: detección, entorno y descarga portátil (motor vlc).

El módulo de bootstrap es puro (sin PyQt): la UI consume ``is_vlc_available``,
``configure_vlc_env`` e ``install_vlc_portable``. También cubre el contrato del
adaptador ``vlc_player_adapter`` cuando VLC no está disponible: el módulo debe
importarse sin tumbar la app y la instanciación debe fallar limpiamente.

Estos tests NO usan red real ni VLC real: ``requests.get``, ``py7zr`` y las
rutas del sistema van mockeados.
"""

import builtins
import importlib
import os
import sys
import types
from pathlib import Path
from unittest import mock

import pytest
import requests

from src.infrastructure.utils.vlc_bootstrap import (
    VLC_7Z_URL,
    VLC_EXE_URL,
    VLC_VERSION,
    VlcBootstrapError,
    configure_vlc_env,
    default_vlc_dir,
    detect_vlc_lib,
    install_vlc_portable,
    is_vlc_available,
)

FAKE_LIBVLC_CONTENT = b"fake-libvlc.dll"
VLC_SUBDIR = f"vlc-{VLC_VERSION}"


@pytest.fixture(autouse=True)
def _clean_vlc_env(monkeypatch):
    """Cada test arranca sin ``PYTHON_VLC_*`` (importar el adaptador los setea)."""
    for var in ("PYTHON_VLC_LIB_PATH", "PYTHON_VLC_MODULE_PATH"):
        monkeypatch.delenv(var, raising=False)


def _make_libvlc(vlc_dir: Path) -> Path:
    dll = vlc_dir / "libvlc.dll"
    vlc_dir.mkdir(parents=True, exist_ok=True)
    dll.write_bytes(FAKE_LIBVLC_CONTENT)
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
    """Fake de ``py7zr.SevenZipFile``: extrae ``vlc-3.0.21/libvlc.dll``."""

    def __init__(self, archive_path):
        self.archive_path = archive_path

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract(self, path, targets=None):
        dll = Path(path) / VLC_SUBDIR / "libvlc.dll"
        dll.parent.mkdir(parents=True, exist_ok=True)
        dll.write_bytes(FAKE_LIBVLC_CONTENT)


def _patch_default_dir(tmp_path: Path, name: str = "app"):
    """Apunta ``default_vlc_dir()`` a ``tmp_path/name`` (sin tocar el sistema)."""
    return mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.default_vlc_dir",
        return_value=tmp_path / name,
    )


# --- constantes ---


def test_constants_pinned_version_and_urls():
    assert VLC_VERSION == "3.0.21"
    assert VLC_EXE_URL == (
        "https://get.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.exe"
    )
    assert VLC_7Z_URL == (
        "https://get.videolan.org/vlc/3.0.21/win64/vlc-3.0.21-win64.7z"
    )


def test_default_vlc_dir_in_dev_is_project_root_vlc():
    project_root = Path(__file__).resolve().parent.parent
    assert default_vlc_dir() == project_root / "vlc"


# --- detect_vlc_lib / is_vlc_available ---


def test_detect_vlc_lib_none_when_no_vlc_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.infrastructure.utils.vlc_bootstrap.default_vlc_dir",
        lambda: tmp_path / "app",
    )
    monkeypatch.delenv("ProgramFiles", raising=False)
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    assert detect_vlc_lib() is None
    assert is_vlc_available() is False


def test_detect_vlc_lib_from_env_var(monkeypatch, tmp_path):
    dll = _make_libvlc(tmp_path / "portable")
    monkeypatch.setenv("PYTHON_VLC_LIB_PATH", str(dll))
    assert detect_vlc_lib() == dll
    assert is_vlc_available() is True


def test_detect_vlc_lib_from_default_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.infrastructure.utils.vlc_bootstrap.default_vlc_dir",
        lambda: tmp_path / "app",
    )
    monkeypatch.delenv("ProgramFiles", raising=False)
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    dll = _make_libvlc(tmp_path / "app" / VLC_SUBDIR)
    assert detect_vlc_lib() == dll


def test_detect_vlc_lib_from_program_files(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.infrastructure.utils.vlc_bootstrap.default_vlc_dir",
        lambda: tmp_path / "app",
    )
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    dll = _make_libvlc(tmp_path / "VideoLAN" / "VLC")
    assert detect_vlc_lib() == dll


def test_detect_vlc_lib_skips_empty_libvlc(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.infrastructure.utils.vlc_bootstrap.default_vlc_dir",
        lambda: tmp_path / "app",
    )
    monkeypatch.delenv("ProgramFiles", raising=False)
    monkeypatch.delenv("ProgramFiles(x86)", raising=False)
    dll = _make_libvlc(tmp_path / "app" / VLC_SUBDIR)
    dll.write_bytes(b"")
    assert detect_vlc_lib() is None


# --- configure_vlc_env ---


def test_configure_vlc_env_sets_lib_and_module_paths(tmp_path):
    vlc_dir = tmp_path / "vlc-3.0.21"
    configure_vlc_env(vlc_dir)
    assert os.environ["PYTHON_VLC_LIB_PATH"] == str(vlc_dir / "libvlc.dll")
    assert os.environ["PYTHON_VLC_MODULE_PATH"] == str(vlc_dir / "plugins")


# --- install_vlc_portable ---


def test_install_portable_downloads_extracts_and_returns_dir(tmp_path):
    dest = tmp_path / "app"
    with _patch_default_dir(tmp_path) as default_dir, mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.requests.get",
        return_value=FakeResponse(b"7z-fake-archive-bytes"),
    ) as get, mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.py7zr.SevenZipFile",
        FakeSevenZipFile,
    ):
        result = install_vlc_portable()

    assert result == dest / VLC_SUBDIR
    assert (result / "libvlc.dll").read_bytes() == FAKE_LIBVLC_CONTENT
    default_dir.assert_called_once()
    get.assert_called_once_with(VLC_7Z_URL, stream=True, timeout=120)


def test_install_portable_reports_progress(tmp_path):
    archive_bytes = b"x" * 512
    progress_calls: list[tuple[int, int]] = []
    with _patch_default_dir(tmp_path), mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.requests.get",
        return_value=FakeResponse(archive_bytes),
    ), mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.py7zr.SevenZipFile",
        FakeSevenZipFile,
    ):
        install_vlc_portable(progress=lambda d, t: progress_calls.append((d, t)))

    assert progress_calls
    assert progress_calls[-1] == (len(archive_bytes), len(archive_bytes))
    for downloaded, total in progress_calls:
        assert 0 <= downloaded <= total


def test_install_portable_raises_on_download_failure(tmp_path):
    with _patch_default_dir(tmp_path), mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.requests.get",
        side_effect=requests.exceptions.ConnectionError("boom"),
    ), pytest.raises(VlcBootstrapError):
        install_vlc_portable()


def test_install_portable_raises_on_extract_failure(tmp_path):
    class BrokenSevenZip:
        def __init__(self, archive_path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract(self, path, targets=None):
            raise ValueError("archivo 7z corrupto")

    with _patch_default_dir(tmp_path), mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.requests.get",
        return_value=FakeResponse(b"7z-fake-archive-bytes"),
    ), mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.py7zr.SevenZipFile",
        BrokenSevenZip,
    ), pytest.raises(VlcBootstrapError):
        install_vlc_portable()


def test_install_portable_raises_when_libvlc_missing_in_archive(tmp_path):
    class SevenZipWithoutLibvlc:
        def __init__(self, archive_path):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract(self, path, targets=None):
            pass  # el .7z descargado no contenía libvlc.dll

    with _patch_default_dir(tmp_path), mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.requests.get",
        return_value=FakeResponse(b"7z-fake-archive-bytes"),
    ), mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.py7zr.SevenZipFile",
        SevenZipWithoutLibvlc,
    ), pytest.raises(VlcBootstrapError):
        install_vlc_portable()


def test_install_portable_cleans_temporary_directory(tmp_path):
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    dest = tmp_path / "app"
    with mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.tempfile.mkdtemp",
        return_value=str(temp_root),
    ), _patch_default_dir(tmp_path), mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.requests.get",
        return_value=FakeResponse(b"7z-fake-archive-bytes"),
    ), mock.patch(
        "src.infrastructure.utils.vlc_bootstrap.py7zr.SevenZipFile",
        FakeSevenZipFile,
    ):
        install_vlc_portable()

    assert temp_root.exists() is False
    assert sorted(p.name for p in dest.iterdir()) == [VLC_SUBDIR]


# --- vlc_player_adapter sin VLC real ---


def _import_adapter_fresh():
    """Reimporta el adaptador VLC descartando el módulo cacheado."""
    sys.modules.pop("src.infrastructure.adapters.vlc_player_adapter", None)
    return importlib.import_module("src.infrastructure.adapters.vlc_player_adapter")


def _patch_bootstrap_functions(monkeypatch, detected, configured):
    """Fija ``detect_vlc_lib``/``configure_vlc_env`` del módulo de bootstrap."""
    monkeypatch.setattr(
        "src.infrastructure.utils.vlc_bootstrap.detect_vlc_lib",
        lambda: detected,
    )
    monkeypatch.setattr(
        "src.infrastructure.utils.vlc_bootstrap.configure_vlc_env",
        lambda d: configured.append(d),
    )


def test_vlc_adapter_imports_without_vlc_and_fails_cleanly_on_use(monkeypatch):
    monkeypatch.setattr(
        "src.infrastructure.utils.vlc_bootstrap.detect_vlc_lib", lambda: None
    )
    monkeypatch.setattr(
        "src.infrastructure.utils.vlc_bootstrap.configure_vlc_env", lambda _d: None
    )

    real_import = builtins.__import__

    def _no_vlc_import(name, *args, **kwargs):
        if name == "vlc":
            raise ImportError("vlc no instalado (simulado)")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_vlc_import)
    module = _import_adapter_fresh()

    with pytest.raises(RuntimeError, match="VLC no está disponible"):
        module.VlcPlayerAdapter(vlc_config={})
    assert module._vlc_import_error is not None


def test_vlc_adapter_configures_env_from_detected_lib_before_import(monkeypatch):
    fake_vlc = types.ModuleType("vlc")
    monkeypatch.setitem(sys.modules, "vlc", fake_vlc)

    detected = Path("C:/FakeVLC/libvlc.dll")
    configured: list[Path] = []
    _patch_bootstrap_functions(monkeypatch, detected, configured)
    module = _import_adapter_fresh()

    assert configured == [detected.parent]
    assert module._vlc_import_error is None


def test_vlc_adapter_reimports_vlc_after_user_resolves(monkeypatch):
    fake_vlc = types.ModuleType("vlc")
    real_import = builtins.__import__
    attempts = {"n": 0}

    def _flaky_import(name, *args, **kwargs):
        if name == "vlc":
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise ImportError("primera vez sin VLC (simulado)")
            return fake_vlc
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(
        "src.infrastructure.utils.vlc_bootstrap.detect_vlc_lib", lambda: None
    )
    monkeypatch.setattr(
        "src.infrastructure.utils.vlc_bootstrap.configure_vlc_env", lambda _d: None
    )
    monkeypatch.setattr(builtins, "__import__", _flaky_import)
    module = _import_adapter_fresh()

    with pytest.raises(RuntimeError, match="VLC no está disponible"):
        module.VlcPlayerAdapter(vlc_config={})
    assert attempts["n"] == 1

    # El usuario señaló/instaló VLC: el siguiente _init_vlc reintenta el import.
    assert module._import_vlc() is fake_vlc
    assert attempts["n"] == 2
    assert module._vlc_import_error is None
