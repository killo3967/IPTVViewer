"""QtLogoLoaderAdapter: cola con concurrencia acotada, dedup y TTL de caché."""

import logging
import os
import time
from pathlib import Path
from unittest import mock

from PyQt6.QtGui import QColor, QImage
from PyQt6.QtNetwork import QNetworkReply, QNetworkRequest

from src.infrastructure.adapters.qt_logo_loader_adapter import (
    FAILED_RETRY_SECONDS,
    LOGO_CACHE_TTL_SECONDS,
    LOGO_TRANSFER_TIMEOUT_MS,
    MAX_CONCURRENT_LOGOS,
    MAX_WARNINGS_PER_HOST,
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


def _make_error_reply() -> mock.Mock:
    reply = mock.Mock()
    reply.error.return_value = QNetworkReply.NetworkError.HostNotFoundError
    return reply


def test_failed_logo_not_retried_within_ttl(qtbot, tmp_path):
    """Un logo que falla no se vuelve a pedir en la misma sesión (caché negativa)."""
    loader = _make_loader(tmp_path)
    url = "http://x/broken.png"

    loader.get_logo(url)
    reply = loader._nam.get.return_value
    loader._handle_response(reply, url, loader._get_cache_path(url))
    assert loader._nam.get.call_count == 1

    loader.get_logo(url)  # re-render de la tabla: no debe re-descargar

    assert loader._nam.get.call_count == 1


def test_failed_logo_retried_after_ttl(qtbot, tmp_path):
    loader = _make_loader(tmp_path)
    url = "http://x/broken.png"
    loader._failed[url] = time.time() - FAILED_RETRY_SECONDS - 1

    loader.get_logo(url)

    assert loader._nam.get.call_count == 1


def test_request_disables_http2(qtbot, tmp_path):
    """Los CDNs de logos IPTV rompen con HTTP/2: se fuerza HTTP/1.1."""
    loader = _make_loader(tmp_path)

    loader.get_logo("http://x/logo.png")

    request = loader._nam.get.call_args[0][0]
    assert (
        request.attribute(QNetworkRequest.Attribute.Http2AllowedAttribute)
        is False
    )



def test_request_sets_the_transfer_timeout(qtbot, tmp_path):
    """Un host que no responde no puede ocupar un hueco de la cola para siempre."""
    loader = _make_loader(tmp_path)

    loader.get_logo("http://x/logo.png")

    request = loader._nam.get.call_args[0][0]
    assert request.transferTimeout() == LOGO_TRANSFER_TIMEOUT_MS


def test_hung_logo_is_logged_with_url_and_reason(qtbot, tmp_path, caplog):
    loader = _make_loader(tmp_path)
    url = "http://172.26.64.1:34400/images/abc.png"
    reply = _make_error_reply()

    with caplog.at_level("WARNING"):
        loader.get_logo(url)
        loader._handle_response(reply, url, loader._get_cache_path(url))

    assert "172.26.64.1:34400" in caplog.text
    assert "HostNotFoundError" in caplog.text


def test_log_failure_warnings_are_capped_per_host(qtbot, tmp_path, caplog):
    """Miles de canales con el CDN limitando no pueden llenar el log de avisos."""
    loader = _make_loader(tmp_path)
    urls = [f"http://cdn.example/{i}.png" for i in range(5)]
    reply = _make_error_reply()
    reply.errorString.return_value = "Too many requests"

    for url in urls:
        loader.get_logo(url)

    with caplog.at_level(logging.DEBUG):
        for url in urls:
            loader._handle_response(reply, url, loader._get_cache_path(url))

    avisos = [
        r for r in caplog.records
        if r.levelno == logging.WARNING and "cdn.example" in r.getMessage()
    ]
    assert len(avisos) == MAX_WARNINGS_PER_HOST


def test_log_failure_warns_once_per_new_host(qtbot, tmp_path, caplog):
    loader = _make_loader(tmp_path)
    reply = _make_error_reply()
    reply.errorString.return_value = "Connection refused"

    urls = ["http://uno.example/a.png", "http://dos.example/b.png"]
    for url in urls:
        loader.get_logo(url)

    with caplog.at_level(logging.WARNING):
        for url in urls:
            loader._handle_response(reply, url, loader._get_cache_path(url))

    assert "uno.example" in caplog.text
    assert "dos.example" in caplog.text


def test_queue_drained_logs_one_summary_and_resets_the_counters(qtbot, tmp_path, caplog):
    loader = _make_loader(tmp_path)
    reply = _make_error_reply()
    reply.errorString.return_value = "Host unreachable"
    urls = [f"http://muerto.example/{i}.png" for i in range(6)]
    for url in urls:
        loader.get_logo(url)

    with caplog.at_level(logging.INFO):
        for url in urls:
            loader._handle_response(reply, url, loader._get_cache_path(url))

    resumenes = [r for r in caplog.records if "fallos en" in r.getMessage()]
    assert len(resumenes) == 1
    assert "6 fallos en 1 host" in resumenes[0].getMessage()
    assert loader._failed_by_host == {}


def test_failure_reason_does_not_leak_the_url_query(qtbot, tmp_path, caplog):
    """errorString() repite la URL entera, con sus tokens: el log no debe verlos."""
    loader = _make_loader(tmp_path)
    url = "https://cdn.example/logo.png?token=secreto"
    reply = mock.Mock()
    reply.error.return_value = QNetworkReply.NetworkError.ContentNotFoundError
    reply.attribute.return_value = 404
    reply.errorString.return_value = f"Error transferring {url} - server replied: Not Found"

    with caplog.at_level(logging.WARNING):
        loader.get_logo(url)
        loader._handle_response(reply, url, loader._get_cache_path(url))

    assert "secreto" not in caplog.text
    assert "ContentNotFoundError" in caplog.text
    assert "HTTP 404" in caplog.text
