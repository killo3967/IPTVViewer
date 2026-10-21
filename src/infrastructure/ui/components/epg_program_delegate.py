"""Pintado de la columna "Programación": título, horas, barra de progreso y duración.

La celda se dibuja con un :class:`QStyledItemDelegate` en lugar de crear un
widget por fila: con listas de cientos o miles de canales, un widget por celda
es mucho más caro y además el delegado puede recalcular el porcentaje en cada
repintado, de forma que las barras avanzan sin volver a consultar la EPG.
"""

from dataclasses import dataclass
from datetime import datetime

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

#: Rol del item donde se guarda el :class:`ProgramInfo` del programa en curso.
EPG_PROGRAM_ROLE = Qt.ItemDataRole.UserRole + 1

#: Alto de la barra de progreso, en píxeles (fina, como pidió el diseño).
BAR_HEIGHT = 6
#: Separación entre las horas y la barra.
BAR_GAP = 6
#: Separación entre el título y la línea de horas/barra.
TITLE_GAP = 8
#: Relleno de la barra (azul celeste) y carril de fondo.
FILL_COLOR = QColor("#38bdf8")
TRACK_COLOR = QColor("#2a3644")
#: Color de los textos secundarios (horas y duración).
SECONDARY_COLOR = QColor("#9aa4b2")


@dataclass(frozen=True)
class ProgramInfo:
    """Datos mínimos para pintar el programa que se está emitiendo."""

    title: str
    start: datetime
    end: datetime

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

    def start_text(self) -> str:
        """Hora de inicio en formato ``HH:MM``."""
        return self.start.strftime("%H:%M")

    def end_text(self) -> str:
        """Hora de fin en formato ``HH:MM``."""
        return self.end.strftime("%H:%M")


class EPGProgramDelegate(QStyledItemDelegate):
    """Dibuja el programa en curso sin crear un widget por fila.

    Layout de la celda (filas de 90 px)::

        Título del programa
        20:15  [=========-------]  21:45
                    90 min

    Las horas van a los lados de la barra y la duración debajo de ella. Con
    :meth:`set_title_only` activo solo se pinta el título.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._title_only = False

    @property
    def title_only(self) -> bool:
        """``True`` si la celda muestra únicamente el título."""
        return self._title_only

    def set_title_only(self, title_only: bool) -> None:
        """Activa o desactiva el modo "solo título" (sin horas, barra ni duración)."""
        self._title_only = bool(title_only)

    def paint(self, painter: QPainter | None, option: QStyleOptionViewItem, index) -> None:
        info = index.data(EPG_PROGRAM_ROLE)
        if painter is None or not isinstance(info, ProgramInfo):
            super().paint(painter, option, index)
            return

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        text_color = QColor("#ffffff") if selected else option.palette.text().color()
        secondary = text_color if selected else SECONDARY_COLOR

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if selected:
            painter.fillRect(option.rect, option.palette.highlight())

        rect = option.rect.adjusted(6, 4, -6, -4)

        title_font = QFont(option.font)
        title_font.setBold(True)
        painter.setFont(title_font)
        title_metrics = QFontMetrics(title_font)
        title_text = title_metrics.elidedText(
            info.title, Qt.TextElideMode.ElideRight, rect.width()
        )
        painter.setPen(text_color)

        # 1) Título. En modo "solo título" se centra en la celda; con barra va arriba.
        if self._title_only:
            painter.drawText(
                rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                title_text,
            )
            painter.restore()
            return

        title_rect = QRect(rect.left(), rect.top(), rect.width(), title_metrics.height())
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            title_text,
        )

        # 2) Hora de inicio · barra · hora de fin
        small_font = QFont(option.font)
        small_font.setPointSizeF(max(7.0, option.font.pointSizeF() - 0.5))
        painter.setFont(small_font)
        small_metrics = QFontMetrics(small_font)

        start_text = info.start_text()
        end_text = info.end_text()
        start_width = small_metrics.horizontalAdvance(start_text)
        end_width = small_metrics.horizontalAdvance(end_text)
        line_height = max(small_metrics.height(), BAR_HEIGHT)
        line_top = title_rect.bottom() + TITLE_GAP

        painter.setPen(secondary)
        painter.drawText(
            QRect(rect.left(), line_top, start_width, line_height),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            start_text,
        )
        painter.drawText(
            QRect(rect.right() - end_width, line_top, end_width, line_height),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            end_text,
        )

        bar_left = rect.left() + start_width + BAR_GAP
        bar_right = rect.right() - end_width - BAR_GAP
        bar_width = bar_right - bar_left
        if bar_width > 0:
            bar_top = line_top + (line_height - BAR_HEIGHT) // 2
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 70) if selected else TRACK_COLOR)
            painter.drawRoundedRect(
                QRect(bar_left, bar_top, bar_width, BAR_HEIGHT),
                BAR_HEIGHT / 2,
                BAR_HEIGHT / 2,
            )

            filled = int(bar_width * info.progress())
            if filled > 0:
                painter.setBrush(FILL_COLOR)
                painter.drawRoundedRect(
                    QRect(bar_left, bar_top, max(BAR_HEIGHT, filled), BAR_HEIGHT),
                    BAR_HEIGHT / 2,
                    BAR_HEIGHT / 2,
                )

            # 3) Duración debajo de la barra
            painter.setPen(secondary)
            painter.drawText(
                QRect(bar_left, bar_top + BAR_HEIGHT + 2, bar_width, small_metrics.height()),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                info.duration_text(),
            )

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        width = option.rect.width() or 200
        return QSize(width, 90)
