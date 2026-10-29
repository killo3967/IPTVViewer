"""Pruebas de ``ProgramInfo`` y del delegado de fila del panel de canales."""

import os
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtWidgets import QApplication, QStyleOptionViewItem

from src.domain.entities.channel import Channel
from src.infrastructure.ui.components.channel_row_delegate import (
    CHANNEL_ROLE,
    EPG_PROGRAM_ROLE,
    LAYOUTS,
    STYLE_NORMAL,
    ChannelRowDelegate,
    ProgramInfo,
    content_height,
)

START = datetime(2026, 10, 21, 20, 0)


def _info(duration_min: int = 60, next_title: str = "") -> ProgramInfo:
    return ProgramInfo(
        title="Telediario",
        start=START,
        end=START + timedelta(minutes=duration_min),
        next_title=next_title,
    )


def _channel() -> Channel:
    return Channel(name="La 1", url="http://example/stream", logo_url=None)


# --- ProgramInfo -----------------------------------------------------------
def test_progress_zero_at_start():
    info = _info()
    assert info.progress(info.start) == 0.0


def test_progress_half_way():
    info = _info()
    assert abs(info.progress(info.start + timedelta(minutes=30)) - 0.5) < 1e-9


def test_progress_one_at_end_and_clamped_outside():
    info = _info()
    assert info.progress(info.end) == 1.0
    assert info.progress(info.end + timedelta(hours=3)) == 1.0
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
    assert info.start_text == "20:00"
    assert info.end_text == "21:00"


def test_next_title_defaults_to_empty():
    assert _info().next_title == ""
    assert _info(next_title="El tiempo").next_title == "El tiempo"


# --- ChannelRowDelegate ----------------------------------------------------
def test_delegate_rejects_unknown_layout(qtbot):
    import pytest

    with pytest.raises(ValueError):
        ChannelRowDelegate("inexistente")


def test_layouts_define_normal_and_compact(qtbot):
    assert set(LAYOUTS) == {"normal", "compact"}
    assert LAYOUTS["normal"].show_next is True
    assert LAYOUTS["compact"].show_next is False
    assert LAYOUTS["normal"].accent is True
    assert LAYOUTS["compact"].logo_width < LAYOUTS["normal"].logo_width


def test_title_only_defaults_to_false_and_toggles(qtbot):
    delegate = ChannelRowDelegate()
    assert delegate.title_only is False
    delegate.set_title_only(True)
    assert delegate.title_only is True
    delegate.set_title_only(False)
    assert delegate.title_only is False


def test_title_only_never_increases_row_height(qtbot):
    delegate = ChannelRowDelegate("normal")
    alto_completo = delegate.row_height
    delegate.set_title_only(True)
    assert delegate.row_height <= alto_completo


def test_title_only_reduces_text_height():
    """Con «solo título» el texto necesita menos alto (aunque el logo mande)."""
    app = QApplication.instance() or QApplication([])
    completo = content_height(app.font(), STYLE_NORMAL, title_only=False)
    reducido = content_height(app.font(), STYLE_NORMAL, title_only=True)
    assert reducido < completo


def test_row_height_is_never_below_the_logo(qtbot):
    for layout in ("normal", "compact"):
        delegate = ChannelRowDelegate(layout)
        assert delegate.row_height >= delegate.style.logo_height
        delegate.set_title_only(True)
        assert delegate.row_height >= delegate.style.logo_height


def test_compact_needs_less_height_than_normal(qtbot):
    normal = ChannelRowDelegate("normal")
    compact = ChannelRowDelegate("compact")
    assert compact.row_height < normal.row_height


def test_normal_height_covers_logo_and_text(qtbot):
    delegate = ChannelRowDelegate("normal")
    assert delegate.row_height >= delegate.style.logo_height


class _FakeIndex:
    """Index mínimo: el delegado solo consulta roles."""

    def __init__(self, info, channel, icon=None):
        self._values = {
            EPG_PROGRAM_ROLE: info,
            CHANNEL_ROLE: channel,
            Qt.ItemDataRole.DecorationRole: icon,
        }

    def data(self, role):
        return self._values.get(role)


def test_delegate_paints_in_both_layouts_and_title_only(qtbot):
    """Cubre paint() real (con y sin siguiente programa) sin excepciones."""
    app = QApplication.instance() or QApplication([])
    option = QStyleOptionViewItem()
    option.font = app.font()
    index = _FakeIndex(_info(next_title="El tiempo"), _channel())

    for layout in ("normal", "compact"):
        delegate = ChannelRowDelegate(layout)
        option.rect = QRect(0, 0, 340, delegate.row_height)
        for title_only in (False, True):
            delegate.set_title_only(title_only)
            pixmap = QPixmap(340, delegate.row_height)
            pixmap.fill()
            painter = QPainter(pixmap)
            try:
                delegate.paint(painter, option, index)
            finally:
                painter.end()
            assert not pixmap.isNull()


def test_paint_without_next_program_does_not_raise(qtbot):
    app = QApplication.instance() or QApplication([])
    delegate = ChannelRowDelegate("normal")
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 340, delegate.row_height)
    option.font = app.font()
    pixmap = QPixmap(340, delegate.row_height)
    pixmap.fill()
    painter = QPainter(pixmap)
    try:
        delegate.paint(painter, option, _FakeIndex(_info(), _channel()))
    finally:
        painter.end()
    assert not pixmap.isNull()


def test_size_hint_height_matches_row_height(qtbot):
    delegate = ChannelRowDelegate("normal")
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 340, 92)
    hint = delegate.sizeHint(option, _FakeIndex(_info(), _channel()))
    assert hint.height() == delegate.row_height


def _ink_pixels(delegate, index, width: int = 340) -> int:
    """Cuenta los píxeles distintos del fondo que pinta la fila."""
    app = QApplication.instance() or QApplication([])
    option = QStyleOptionViewItem()
    option.font = app.font()
    option.rect = QRect(0, 0, width, delegate.row_height)
    fondo = QColor("#1e1e1e")
    pixmap = QPixmap(width, delegate.row_height)
    pixmap.fill(fondo)
    painter = QPainter(pixmap)
    try:
        delegate.paint(painter, option, index)
    finally:
        painter.end()
    image = pixmap.toImage()
    return sum(1 for y in range(image.height()) for x in range(image.width())
               if image.pixel(x, y) != fondo.rgb())


def test_delegate_paints_the_row_when_epg_is_available(qtbot):
    delegate = ChannelRowDelegate("normal")
    assert _ink_pixels(delegate, _FakeIndex(_info(), _channel())) > 0


def test_delegate_paints_the_channel_name_without_epg(qtbot):
    """Sin datos de EPG la fila no puede quedar en blanco: se perdería la lista.

    Una fuente cuya EPG falla (descarga caída, URL equivocada) deja todas las
    filas sin ``ProgramInfo``; si el delegado no pinta el nombre, el panel
    aparece vacío y parece que la lista de canales no ha cargado.
    """
    delegate = ChannelRowDelegate("normal")
    assert _ink_pixels(delegate, _FakeIndex(None, _channel())) > 0


def test_delegate_paints_the_channel_name_without_epg_in_title_only(qtbot):
    delegate = ChannelRowDelegate("normal")
    delegate.set_title_only(True)
    assert _ink_pixels(delegate, _FakeIndex(None, _channel())) > 0
