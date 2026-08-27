"""QtLogoLoaderAdapter: cola con concurrencia acotada, dedup y TTL de caché."""

import os
import time
from pathlib import Path
from unittest import mock

from PyQt6.QtGui import QColor, QImage

from src.infrastructure.adapters.qt_logo_loader_adapter import (
    LOGO_CACHE_TTL_SECONDS,
    MAX_CONCURRENT_LOGOS,
    QtLogoLoaderAdapter,
)


def _make_loader(tmp_path: Path) -> QtLogoLoaderAdapter:
    loader = QtLogoLoaderAdapter(cache_dir=str(tmp_path / "cache"))
    loader._nam = mock.Mock()
    loader._nam.get = mock.Mock(return_value=mock.Mock())
    return loader


def _write_valid_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(10, 10, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    assert image.save(str(path), "PNG")


def test_get_logo_limits_concurrency(qtbot, tmp_path):
    loader = _make_loader(tmp_path)
    urls = [f"http://x/{i}.png" for i in range(MAX_CONCURRENT_LOGOS + 3)]

    for url in urls:
        loader.get_logo(url)

    assert loader._nam.get.call_count == MAX_CONCURRENT_LOGOS
    assert len(loader._active) == MAX_CONCURRENT_LOGOS
    assert len(loader._pending) == len(urls) - MAX_CONCURRENT_LOGOS


def test_get_logo_dedups_pending_urls(qtbot, tmp_path):
    loader = _make_loader(tmp_path)

    loader.get_logo("http://x/logo.png")
    loader.get_logo("http://x/logo.png")

    assert len(loader._active) + len(loader._pending) == 1


def test_get_logo_uses_fresh_disk_cache(qtbot, tmp_path):
    loader = _make_loader(tmp_path)
    cache_path = loader._get_cache_path("http://x/logo.png")
    _write_valid_png(cache_path)
    os.utime(cache_path, (time.time(), time.time()))

    loader.get_logo("http://x/logo.png")

    assert loader._nam.get.call_count == 0
    assert "http://x/logo.png" in loader._memory_cache


def test_get_logo_redownloads_stale_disk_cache(qtbot, tmp_path):
    loader = _make_loader(tmp_path)
    cache_path = loader._get_cache_path("http://x/logo.png")
    _write_valid_png(cache_path)
    old = time.time() - LOGO_CACHE_TTL_SECONDS - 100
    os.utime(cache_path, (old, old))

    loader.get_logo("http://x/logo.png")

    assert loader._nam.get.call_count == 1
