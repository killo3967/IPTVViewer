"""Pruebas de ProgramInfo y del delegate de la columna Programación."""

import os
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QStyleOptionViewItem

from src.infrastructure.ui.components.epg_program_delegate import (
    EPG_PROGRAM_ROLE,
    EPGProgramDelegate,
    ProgramInfo,
)

START = datetime(2026, 10, 21, 20, 0)


def _info(duration_min: int = 60) -> ProgramInfo:
    return ProgramInfo(
        title="Telediario",
        start=START,
        end=START + timedelta(minutes=duration_min),
    )


def test_progress_zero_at_start():
    info = _info()
    assert info.progress(info.start) == 0.0


def test_progress_half_way():
    info = _info()
    midway = info.start + timedelta(minutes=30)
    assert abs(info.progress(midway) - 0.5) < 1e-9


def test_progress_one_at_end():
    info = _info()
    assert info.progress(info.end) == 1.0


def test_progress_clamped_after_end():
    info = _info()
    assert info.progress(info.end + timedelta(hours=3)) == 1.0


def test_progress_clamped_before_start():
    info = _info()
    assert info.progress(info.start - timedelta(hours=1)) == 0.0


def test_progress_with_zero_duration_is_complete():
    info = ProgramInfo(title="X", start=START, end=START)
    assert info.progress(START) == 1.0


def test_duration_text_formats():
    assert _info(30).duration_text() == "30 min"
    assert _info(90).duration_text() == "1 h 30 min"
    assert _info(120).duration_text() == "2 h"


def test_time_texts_use_hh_mm():
    info = _info()
    assert info.start_text() == "20:00"
    assert info.end_text() == "21:00"


def test_delegate_title_only_defaults_to_false_and_toggles():
    delegate = EPGProgramDelegate()
    assert delegate.title_only is False
    delegate.set_title_only(True)
    assert delegate.title_only is True
    delegate.set_title_only(False)
    assert delegate.title_only is False


class _FakeIndex:
    """Index mínimo: el delegate solo consulta el rol del programa."""

    def __init__(self, info):
        self._info = info

    def data(self, role):
        return self._info if role == EPG_PROGRAM_ROLE else None


def test_delegate_paints_in_both_modes(qtbot):
    """Cubre paint() real (con barra y en modo solo título) sin excepciones."""
    app = QApplication.instance() or QApplication([])
    delegate = EPGProgramDelegate()
    pixmap = QPixmap(400, 90)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 400, 90)
    option.font = app.font()
    info = _info()

    for title_only in (False, True):
        delegate.set_title_only(title_only)
        pixmap.fill()
        painter = QPainter(pixmap)
        try:
            delegate.paint(painter, option, _FakeIndex(info))
        finally:
            painter.end()
        assert not pixmap.isNull()

    assert delegate.sizeHint(option, _FakeIndex(info)).height() == 90
