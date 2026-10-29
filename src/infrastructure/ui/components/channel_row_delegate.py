"""Pintado del panel de canales en una sola columna.

Cada fila integra todo lo que antes ocupaba tres columnas (Canal | Logo |
Programación): el logo, el nombre del canal, el programa en curso con sus horas,
la barra de progreso, la duración y —solo en la variante normal— el siguiente
programa bajo la barra.

Se pinta con un :class:`QStyledItemDelegate` en lugar de crear widgets por fila:
con listas de miles de canales un widget por celda es mucho más caro, y así la
barra de progreso se recalcula en cada repintado sin volver a consultar la EPG.

El delegado **no** consulta la EPG ni descarga logos: todo lo que pinta llega por
roles del item. El logo se toma del rol de decoración (``setIcon``), que es lo que
rellena el cargador asíncrono de logos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
)

#: Rol del item donde se guarda el :class:`ProgramInfo` de la fila.
EPG_PROGRAM_ROLE = Qt.ItemDataRole.UserRole + 1
#: Rol del item donde se guarda el ``Channel`` que se reproduce al hacer clic.
CHANNEL_ROLE = Qt.ItemDataRole.UserRole + 2

#: Alto de la barra de progreso, en píxeles.
BAR_HEIGHT = 6
#: Separación entre las horas y la barra.
BAR_GAP = 6
#: Margen vertical interior de la fila.
ROW_MARGIN_Y = 6
#: Margen horizontal interior de la fila.
ROW_MARGIN_X = 8
#: Separación entre el logo y el bloque de texto.
LOGO_GAP = 14
#: Barra de acento vertical que subraya el nombre del canal.
ACCENT_WIDTH = 3
#: Separación entre la barra de acento y el texto.
ACCENT_GAP = 7
#: Prefijo del siguiente programa: la flecha ocupa 12 px frente a 78 de
#: «Próximamente: », y ya se lee como «lo que viene».
NEXT_PREFIX = "→ "

#: Texto de la línea de programa cuando la fila no tiene datos de EPG.
NO_EPG_TEXT = "Sin programación"

#: Relleno de la barra de progreso y carril de fondo.
FILL_COLOR = QColor("#38bdf8")
SELECTED_BG = QColor("#2f5f8f")
#: Colores secundarios para tema oscuro y claro (el carril oscuro sería invisible
#: sobre el tema claro nativo de Windows).
SECONDARY_DARK = QColor("#9aa4b2")
TRACK_DARK = QColor("#2a3644")
SECONDARY_LIGHT = QColor("#5c6673")
TRACK_LIGHT = QColor("#d5dae1")


@dataclass(frozen=True)
class ProgramInfo:
    """Datos mínimos para pintar el programa en curso y el siguiente."""

    title: str
    start: datetime
    end: datetime
    next_title: str = ""

    def progress(self, now: datetime | None = None) -> float:
        """Fracción transcurrida del programa, acotada a ``[0.0, 1.0]``."""
        total = (self.end - self.start).total_seconds()
        if total <= 0:
            return 1.0
        elapsed = ((now or datetime.now()) - self.start).total_seconds()
        return max(0.0, min(1.0, elapsed / total))

    def duration_text(self) -> str:
        """Duración legible: ``30 min``, ``1 h 30 min``, ``2 h``."""
        minutes = max(0, round((self.end - self.start).total_seconds() / 60))
        hours, rest = divmod(minutes, 60)
        if hours and rest:
            return f"{hours} h {rest} min"
        if hours:
            return f"{hours} h"
        return f"{rest} min"

    @property
    def start_text(self) -> str:
        """Hora de inicio en formato ``HH:MM``."""
        return self.start.strftime("%H:%M")

    @property
    def end_text(self) -> str:
        """Hora de fin en formato ``HH:MM``."""
        return self.end.strftime("%H:%M")


@dataclass(frozen=True)
class RowStyle:
    """Medidas y espaciados de una variante del panel.

    Los deltas son puntos de fuente sobre la fuente base; los huecos, píxeles.
    """

    logo_width: int
    logo_height: int
    name_delta: float
    title_delta: float
    small_delta: float
    name_gap: int
    title_gap: int
    next_gap: int
    show_next: bool
    accent: bool


#: Variante **normal** (``Alt+1``): logo grande, aire entre líneas, nombre con
#: barrita de acento y línea del siguiente programa.
STYLE_NORMAL = RowStyle(
    logo_width=96, logo_height=72, name_delta=1.5, title_delta=0.0, small_delta=-0.5,
    name_gap=4, title_gap=8, next_gap=3, show_next=True, accent=True,
)

#: Variante **compacta** (``Alt+2``): logo pequeño, espaciados ajustados y sin
#: línea del siguiente programa; su objetivo es que entren más canales.
STYLE_COMPACT = RowStyle(
    logo_width=44, logo_height=44, name_delta=1.0, title_delta=-0.5, small_delta=-0.5,
    name_gap=2, title_gap=5, next_gap=2, show_next=False, accent=False,
)

LAYOUTS: dict[str, RowStyle] = {"normal": STYLE_NORMAL, "compact": STYLE_COMPACT}


def content_height(font: QFont, style: RowStyle, title_only: bool = False) -> int:
    """Alto que necesita la fila para pintar sus líneas sin recortes.

    Se calcula con las métricas reales de la fuente, así que el alto se adapta al
    escalado de Windows o a cambios de tipografía en vez de romperse.
    """
    name_h = QFontMetrics(_scaled(font, style.name_delta, bold=True)).height()
    title_h = QFontMetrics(_scaled(font, style.title_delta)).height()
    small_h = QFontMetrics(_scaled(font, style.small_delta)).height()
    bar_h = max(small_h, BAR_HEIGHT)

    total = name_h + style.name_gap + title_h
    if not title_only:
        total += style.title_gap + bar_h
        if style.show_next:
            total += style.next_gap + small_h
    return total + 2 * ROW_MARGIN_Y


def _scaled(font: QFont, delta: float, bold: bool = False) -> QFont:
    """Copia de ``font`` con el tamaño desplazado ``delta`` puntos."""
    copy = QFont(font)
    copy.setPointSizeF(max(7.0, copy.pointSizeF() + delta))
    if bold:
        copy.setBold(True)
    return copy


def _theme_pair(text_color: QColor) -> tuple[QColor, QColor]:
    """Devuelve (secundario, carril) adecuados al tema claro u oscuro."""
    if text_color.lightnessF() > 0.5:
        return SECONDARY_DARK, TRACK_DARK
    return SECONDARY_LIGHT, TRACK_LIGHT


def _elided(metrics: QFontMetrics, text: str, width: int) -> str:
    return metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(0, width))


def _rounded(path: QPainterPath, rect: QRect, radius: float) -> QPainterPath:
    path.clear()
    path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), radius, radius)
    return path


def _draw_title_line(painter: QPainter, rect: QRect, text: str, font: QFont,
                     color: QColor) -> QRect:
    """Pinta un texto en una línea y devuelve el rect que ocupa."""
    metrics = QFontMetrics(font)
    painter.setFont(font)
    painter.setPen(color)
    box = QRect(rect.left(), rect.top(), rect.width(), metrics.height())
    painter.drawText(box, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                     _elided(metrics, text, rect.width()))
    return box


def _draw_logo(painter: QPainter, rect: QRect, icon: QIcon) -> None:
    """Pinta el logo centrado en ``rect`` respetando su proporción."""
    if icon is None or icon.isNull():
        return
    icon.paint(painter, rect, Qt.AlignmentFlag.AlignCenter)


def _draw_bar(painter: QPainter, rect: QRect, info: ProgramInfo, font: QFont,
              color: QColor, track: QColor | None, selected: bool) -> None:
    """``HH:MM [====___] HH:MM`` con la barra ocupando el espacio libre."""
    metrics = QFontMetrics(font)
    start_w = metrics.horizontalAdvance(info.start_text)
    end_w = metrics.horizontalAdvance(info.end_text)
    height = max(metrics.height(), BAR_HEIGHT)

    painter.setFont(font)
    painter.setPen(color)
    painter.drawText(QRect(rect.left(), rect.top(), start_w, height),
                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                     info.start_text)
    painter.drawText(QRect(rect.right() - end_w, rect.top(), end_w, height),
                     Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                     info.end_text)

    left = rect.left() + start_w + BAR_GAP
    right = rect.right() - end_w - BAR_GAP
    width = right - left
    if width <= 0:
        return

    top = rect.top() + (height - BAR_HEIGHT) // 2
    path = QPainterPath()
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(0, 0, 0, 70) if selected else (track or TRACK_DARK))
    painter.drawPath(_rounded(path, QRect(left, top, width, BAR_HEIGHT), BAR_HEIGHT / 2))

    filled = int(width * info.progress())
    if filled > 0:
        painter.setBrush(FILL_COLOR)
        painter.drawPath(
            _rounded(path, QRect(left, top, max(BAR_HEIGHT, filled), BAR_HEIGHT),
                     BAR_HEIGHT / 2)
        )


def _draw_next_program(painter: QPainter, rect: QRect, info: ProgramInfo, font: QFont,
                       color: QColor) -> None:
    """Pinta ``→ <siguiente programa>`` y no dibuja nada si no hay siguiente."""
    if not info.next_title:
        return

    metrics = QFontMetrics(font)
    painter.setFont(font)
    box = QRect(rect.left(), rect.top(), rect.width(), metrics.height())

    prefix_w = metrics.horizontalAdvance(NEXT_PREFIX)
    dimmer = color.darker(115) if color.lightnessF() > 0.5 else color.lighter(135)
    painter.setPen(dimmer)
    painter.drawText(QRect(box.left(), box.top(), prefix_w, box.height()),
                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                     NEXT_PREFIX)

    title_width = max(0, box.width() - prefix_w)
    painter.setPen(color)
    painter.drawText(QRect(box.left() + prefix_w, box.top(), title_width, box.height()),
                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                     _elided(metrics, info.next_title, title_width))


class ChannelRowDelegate(QStyledItemDelegate):
    """Pinta una fila completa del panel de canales.

    Layout de la variante normal (fila de ~92 px)::

        [logo]  ▌ La 1
                ▌ Telediario 2                · 40 min
                ▌ 18:27 [========----------] 19:07
                ▌ → El tiempo

    La variante compacta es igual pero con logo pequeño y sin la última línea.
    Con :meth:`set_title_only` activo se pintan solo nombre y título del
    programa, sin horas, barra, duración ni siguiente programa.
    """

    def __init__(self, layout: str = "normal", parent=None):
        super().__init__(parent)
        self._layout = ""
        self._style = STYLE_NORMAL
        self._title_only = False
        self._row_height = 0
        self.set_layout(layout)

    # -- API pública ------------------------------------------------------
    @property
    def layout(self) -> str:
        """Nombre del layout: ``normal`` o ``compact``."""
        return self._layout

    @property
    def style(self) -> RowStyle:
        """Medidas de la variante activa."""
        return self._style

    @property
    def row_height(self) -> int:
        """Alto de fila necesario. La tabla DEBE usar este valor."""
        return self._row_height

    @property
    def title_only(self) -> bool:
        """``True`` si la fila se reduce a nombre y título del programa."""
        return self._title_only

    def set_title_only(self, title_only: bool) -> None:
        """Activa o desactiva el modo «solo título» y recalcula el alto."""
        self._title_only = bool(title_only)
        self._row_height = self._measure_row_height()

    def set_layout(self, layout: str) -> None:
        """Cambia de variante (``normal`` o ``compact``) y recalcula el alto."""
        if layout not in LAYOUTS:
            raise ValueError(f"Layout desconocido: {layout!r}. Válidos: {sorted(LAYOUTS)}")
        self._layout = layout
        self._style = LAYOUTS[layout]
        self._row_height = self._measure_row_height()

    def _measure_row_height(self) -> int:
        texto = content_height(self._base_font(), self._style, self._title_only)
        return max(texto, self._style.logo_height + 2 * ROW_MARGIN_Y)

    def _base_font(self) -> QFont:
        """Fuente base: la del widget padre o la de la aplicación.

        ``QApplication.font()`` es estático y aborta el proceso si no hay
        instancia de ``QApplication``, así que se comprueba antes. Se usa
        ``getattr`` porque ``QStyledItemDelegate.parent()`` es un ``QObject``
        cualquiera y no todos exponen ``font()``.
        """
        parent_font = getattr(self.parent(), "font", None)
        if callable(parent_font):
            return parent_font()
        app_font = getattr(QApplication.instance(), "font", None)
        if callable(app_font):
            return app_font()
        return QFont()

    # -- QStyledItemDelegate ---------------------------------------------
    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return QSize(option.rect.width(), self._row_height)

    def paint(self, painter: QPainter | None, option: QStyleOptionViewItem,
              index) -> None:
        info = index.data(EPG_PROGRAM_ROLE)
        channel = index.data(CHANNEL_ROLE)
        channel_name = getattr(channel, "name", "") or ""
        if painter is None or not channel_name:
            super().paint(painter, option, index)
            return

        # Sin EPG (descarga caída o URL equivocada) la fila sigue teniendo que
        # mostrar el nombre: si el delegado se retirase, todas las filas
        # quedarían en blanco y el panel parecería no haber cargado la lista.
        has_epg = isinstance(info, ProgramInfo)

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        # OJO: en PyQt6 `option.palette` y `option.font` son ATRIBUTOS, no métodos.
        text_color = QColor("#ffffff") if selected else option.palette.text().color()
        secondary, track = _theme_pair(text_color)
        if selected:
            secondary = text_color

        style = self._style
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if selected:
            painter.fillRect(option.rect, SELECTED_BG)

        rect = option.rect.adjusted(ROW_MARGIN_X, ROW_MARGIN_Y, -ROW_MARGIN_X, -ROW_MARGIN_Y)
        logo_box = QRect(rect.left(),
                         rect.top() + (rect.height() - style.logo_height) // 2,
                         style.logo_width, style.logo_height)
        _draw_logo(painter, logo_box, index.data(Qt.ItemDataRole.DecorationRole))

        indent = (ACCENT_WIDTH + ACCENT_GAP) if style.accent else 0
        text_left = logo_box.right() + LOGO_GAP + indent
        text = QRect(text_left, rect.top(), rect.right() - text_left, rect.height())

        name_font = _scaled(option.font, style.name_delta, bold=True)
        title_font = _scaled(option.font, style.title_delta)
        small_font = _scaled(option.font, style.small_delta)

        name_rect = _draw_title_line(painter, text, channel_name, name_font, text_color)

        if style.accent:
            accent = QRect(logo_box.right() + LOGO_GAP, name_rect.top() + 1, ACCENT_WIDTH,
                           max(6, name_rect.height() - 2))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(FILL_COLOR)
            painter.drawRoundedRect(accent, ACCENT_WIDTH / 2, ACCENT_WIDTH / 2)

        program_top = name_rect.bottom() + style.name_gap
        program_rect = QRect(text.left(), program_top, text.width(),
                             QFontMetrics(title_font).height())

        if not has_epg:
            _draw_title_line(painter, program_rect, NO_EPG_TEXT, title_font, secondary)
            painter.restore()
            return

        if self._title_only:
            _draw_title_line(painter, program_rect, info.title, title_font, text_color)
            painter.restore()
            return

        # «Telediario 2   ·   40 min»: la duración no cuesta una línea extra.
        suffix = f"   ·   {info.duration_text()}"
        suffix_w = QFontMetrics(small_font).horizontalAdvance(suffix)
        _draw_title_line(painter,
                         QRect(text.left(), program_top, text.width() - suffix_w,
                               program_rect.height()),
                         info.title, title_font, text_color)
        painter.setFont(small_font)
        painter.setPen(secondary)
        painter.drawText(QRect(program_rect.right() - suffix_w, program_top, suffix_w,
                               program_rect.height()),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, suffix)

        bar_rect = QRect(text.left(), program_rect.bottom() + style.title_gap,
                         text.width(), max(QFontMetrics(small_font).height(), BAR_HEIGHT))
        _draw_bar(painter, bar_rect, info, small_font, secondary, track, selected)

        if style.show_next:
            _draw_next_program(painter,
                               QRect(text.left(), bar_rect.bottom() + style.next_gap,
                                     text.width(), QFontMetrics(small_font).height()),
                               info, small_font, secondary)

        painter.restore()
