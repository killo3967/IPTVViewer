"""Clasificación de mensajes de Qt para el logging."""

import logging

from PyQt6.QtCore import QtMsgType

from src.infrastructure.utils.qt_logging import classify_qt_message


def test_critical_never_downgraded():
    assert (
        classify_qt_message(QtMsgType.QtCriticalMsg, "qt.network.http2", "boom")
        == logging.ERROR
    )
    assert (
        classify_qt_message(QtMsgType.QtFatalMsg, "qt.network.http2", "boom")
        == logging.CRITICAL
    )


def test_warning_default_category_stays_warning():
    assert (
        classify_qt_message(QtMsgType.QtWarningMsg, "default", "algo raro")
        == logging.WARNING
    )


def test_network_warning_downgraded_to_info():
    assert (
        classify_qt_message(
            QtMsgType.QtWarningMsg, "qt.network.http2", "Server refused a stream"
        )
        == logging.INFO
    )


def test_imageio_warning_downgraded_to_info():
    assert (
        classify_qt_message(QtMsgType.QtWarningMsg, "qt.gui.imageio", "libpng warning")
        == logging.INFO
    )


def test_ssl_noise_downgraded_to_info():
    assert (
        classify_qt_message(
            QtMsgType.QtWarningMsg,
            "default",
            "QIODevice::read (QSslSocket): device not open",
        )
        == logging.INFO
    )


def test_info_stays_info():
    assert classify_qt_message(QtMsgType.QtInfoMsg, "default", "algo") == logging.INFO
