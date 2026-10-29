"""Mockup del panel de canales en **una sola columna** (4 canales).

Sandbox aislado: no importa ni modifica ``src/`` ni ``main.py``. Reproducen el
lenguaje visual real (colores, barra de 6 px, selección ``#2f5f8f``) para que la
comparación con la tabla actual de 3 columnas sea honesta.

Ejecución con el entorno del proyecto::

    .\\.venv\\Scripts\\python.exe .\\pruebas\\panel_una_columna.py
    .\\.venv\\Scripts\\python.exe .\\pruebas\\panel_una_columna.py --con-referencia
    .\\.venv\\Scripts\\python.exe .\\pruebas\\panel_una_columna.py --oscuro
    .\\.venv\\Scripts\\python.exe .\\pruebas\\panel_una_columna.py --shot pruebas\\img
    .\\.venv\\Scripts\\python.exe .\\pruebas\\panel_una_columna.py --comprobar

Qué se ve::

    VARIANTE A        normal: logo 96x72 + «Próximamente» bajo la barra
    VARIANTE B        compacta: logo 44x44, sin «Próximamente» (más canales)
    REFERENCIA        (opcional) la tabla actual: Canal | Logo | Programación

Ojo al alto de fila: ``sizeHint()`` del delegado NO lo fija. Si la tabla usa el
alto por defecto del vertical header (~30 px), el delegado pinta ~60 px y las
filas se montan unas encima de otras. ``--comprobar`` lo verifica.

Reparto de información:

* VARIANTE A (normal): logo 96x72 + nombre + programa + horas/barra + duración
  + «Próximamente: <siguiente programa>» bajo la barra. El nombre va destacado con
  el estilo «acento» (``CHOSEN_NAME_STYLE``): +1,5 pt y una barrita celeste a la
  izquierda. ``--nombres`` compara ese estilo con «actual» y «grande».
* VARIANTE B (compacta): lo mismo MENOS la línea de «Próximamente»; su objetivo
  es que entren más canales, así que usa logo de 44x44 y espaciados ajustados.

El alto de fila NO es un número fijo: se calcula con ``QFontMetrics`` de la
fuente del sistema (``_content_height``) contando solo las líneas que se pintan,
así que nada se recorta aunque cambie la fuente o el escalado de Windows.

Los logos se descargan del M3U público de iptv-org y se cachean en
``pruebas/logos/``. Sin red se ven marcadores de posición con iniciales.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from PyQt6.QtCore import QObject, QRect, QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPalette,
    QPixmap,
)
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# --- Constantes calcadas de src/infrastructure/ui/... (para no importar src) ---
BAR_HEIGHT = 6
BAR_GAP = 6
TITLE_GAP = 8

#: Separación entre el nombre del canal y el título del programa.
NAME_GAP = 4
#: Separación entre la barra de progreso y la línea «Próximamente: ...».
NEXT_GAP = 3
#: Margen vertical interior de cada fila (arriba y abajo), igual que en paint().
ROW_MARGIN_Y = 6
#: Barra de acento vertical que subraya el nombre del canal (estilo "acento").
ACCENT_WIDTH = 3
#: Separación entre la barra de acento y el texto.
ACCENT_GAP = 7
#: Punto extra de tamaño del nombre según el estilo elegido.
NAME_STYLE_DELTAS = {"actual": 1.0, "grande": 2.5, "acento": 1.5}
#: Estilo del nombre aprobado para la variante normal: barrita de acento celeste
#: y +1,5 pt. Se compara con los otros dos con ``--nombres``.
CHOSEN_NAME_STYLE = "acento"
FILL_COLOR = QColor("#38bdf8")
SELECTED_BG = QColor("#2f5f8f")

# Los grises de la app real (texto secundario y carril de la barra) están pensados
# para fondo oscuro. Sobre el tema claro nativo de Windows serían invisibles, así
# que se eligen según la luminancia del color de texto de la paleta.
SECONDARY_LIGHT = QColor("#5c6673")
TRACK_LIGHT = QColor("#d5dae1")
SECONDARY_DARK = QColor("#9aa4b2")
TRACK_DARK = QColor("#2a3644")


def _theme_pair(text_color: QColor) -> tuple[QColor, QColor]:
    """Devuelve (secundario, carril) adecuados al tema claro u oscuro."""
    if text_color.lightnessF() > 0.5:
        return SECONDARY_DARK, TRACK_DARK
    return SECONDARY_LIGHT, TRACK_LIGHT

PROGRAM_ROLE = Qt.ItemDataRole.UserRole + 1
CHANNEL_ROLE = Qt.ItemDataRole.UserRole + 2

LOGO_DIR = Path(__file__).parent / "logos"


# --------------------------------------------------------------------------- datos
@dataclass(frozen=True)
class ProgramInfo:
    """Programa en emisión y el que viene después."""

    title: str
    start: datetime
    end: datetime
    next_title: str = ""

    def progress(self, now: datetime | None = None) -> float:
        total = (self.end - self.start).total_seconds()
        if total <= 0:
            return 1.0
        elapsed = ((now or datetime.now()) - self.start).total_seconds()
        return max(0.0, min(1.0, elapsed / total))

    def duration_text(self) -> str:
        minutes = max(0, round((self.end - self.start).total_seconds() / 60))
        hours, rest = divmod(minutes, 60)
        if hours and rest:
            return f"{hours} h {rest} min"
        if hours:
            return f"{hours} h"
        return f"{rest} min"

    @property
    def start_text(self) -> str:
        return self.start.strftime("%H:%M")

    @property
    def end_text(self) -> str:
        return self.end.strftime("%H:%M")


@dataclass(frozen=True)
class Channel:
    name: str
    logo_url: str
    brand: str  # color de respaldo para el placeholder
    program: ProgramInfo = field(default_factory=lambda: ProgramInfo("", datetime.now(), datetime.now()))


def _spec(name: str, logo_url: str, brand: str, title: str,
          started_min_ago: int, total_min: int, next_title: str = "") -> Channel:
    """Construye un canal con el programa en curso anclado a la hora actual."""
    now = datetime.now().replace(second=0, microsecond=0)
    start = now - timedelta(minutes=started_min_ago)
    return Channel(name, logo_url, brand,
                   ProgramInfo(title, start, start + timedelta(minutes=total_min),
                               next_title))


# 4 canales reales del M3U público (nombres y tvg-logo tal como aparecen allí).
CHANNELS: list[Channel] = [
    _spec("La 1", "https://i.ibb.co/MxJNPHsn/La-1.png", "#0f4c97",
          "Telediario 2", 25, 40, "El tiempo"),
    _spec("Antena 3",
          "https://upload.wikimedia.org/wikipedia/commons/thumb/8/89/"
          "Logo_Antena_3_2025_%28Naranja%29.svg/960px-Logo_Antena_3_2025_%28Naranja%29.svg.png",
          "#f26522", "El Hormiguero", 12, 70, "Antena 3 Noticias 2"),
    _spec("La 2", "https://i.ibb.co/rfsr9PSh/La-2.png", "#662d91",
          "Documentos TV", 48, 65, "La noche temática"),
    _spec("Teledeporte", "https://i.ibb.co/0jxLdjnY/TDP.png", "#00a859",
          "Fútbol: Liga F", 3, 95, "Teledeporte Noticias"),
]


# ------------------------------------------------------------------- carga de logos
class LogoLoader(QObject):
    """Descarga asíncrona con caché en disco, igual que el adaptador real."""

    logo_loaded = pyqtSignal(str, QPixmap)

    def __init__(self, cache_dir: Path, parent: QObject | None = None):
        super().__init__(parent)
        self._nam = QNetworkAccessManager(self)
        self._cache_dir = cache_dir
        self._mem: dict[str, QPixmap] = {}
        self._pending: dict[str, list[str]] = {}
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get(self, url: str) -> QPixmap | None:
        """Devuelve el pixmap en caché o None si aún hay que descargarlo."""
        if not url:
            return None
        if url in self._mem:
            return self._mem[url]
        disk = self._disk_path(url)
        if disk.exists():
            pixmap = QPixmap(str(disk))
            if not pixmap.isNull():
                self._mem[url] = pixmap
                return pixmap
        if url in self._pending:
            return None
        self._pending[url] = []
        request = QNetworkRequest(QUrl(url))
        # Algunos servidores solo sirven imágenes con User-Agent.
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "IPTVViewer/1.0")
        # HTTP/2 de Qt falla con muchos CDNs de IPTV; se fuerza HTTP/1.1 (igual que src/).
        request.setAttribute(QNetworkRequest.Attribute.Http2AllowedAttribute, False)
        reply = self._nam.get(request)
        reply.setProperty("url", url)
        reply.finished.connect(self._on_finished)
        return None

    def _disk_path(self, url: str) -> Path:
        return self._cache_dir / f"{hashlib.md5(url.encode('utf-8')).hexdigest()}.png"

    def _on_finished(self) -> None:
        reply = self.sender()
        if not isinstance(reply, QNetworkReply):
            return
        url = str(reply.property("url"))
        reply.deleteLater()
        body = bytes(reply.readAll()) if reply.error() == QNetworkReply.NetworkError.NoError else b""
        pixmap = QPixmap()
        if body and pixmap.loadFromData(body):
            disk = self._disk_path(url)
            pixmap.save(str(disk), "PNG")
            self._mem[url] = pixmap
            self.logo_loaded.emit(url, pixmap)
        self._pending.pop(url, None)


def _content_height(font: QFont, *, name_delta: float, title_delta: float,
                    small_delta: float, title_gap: int, next_gap: int,
                    name_gap: int, with_next: bool = True) -> int:
    """Alto que necesita una fila para pintar todas sus líneas sin recortes.

    Reproduce el mismo apilado vertical que :meth:`SingleColumnDelegate.paint`:
    nombre, programa, horas/barra y «Próximamente». Se calcula con las métricas
    reales de la fuente, de modo que la tabla nunca queda corta.
    """
    name_font = QFont(font)
    name_font.setBold(True)
    name_font.setPointSizeF(name_font.pointSizeF() + name_delta)

    title_font = QFont(font)
    title_font.setPointSizeF(title_font.pointSizeF() + title_delta)

    small_font = QFont(font)
    small_font.setPointSizeF(max(7.0, small_font.pointSizeF() + small_delta))

    name_h = QFontMetrics(name_font).height()
    title_h = QFontMetrics(title_font).height()
    small_h = QFontMetrics(small_font).height()
    bar_h = max(small_h, BAR_HEIGHT)

    total = name_h + name_gap + title_h + title_gap + bar_h
    if with_next:
        total += next_gap + small_h
    return total + 2 * ROW_MARGIN_Y


# --------------------------------------------------------------------- piezas de pintado
def _rounded(path: QPainterPath, rect: QRect, radius: float) -> QPainterPath:
    path.clear()
    path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), radius, radius)
    return path


def _elided(metrics: QFontMetrics, text: str, width: int) -> str:
    return metrics.elidedText(text, Qt.TextElideMode.ElideRight, max(0, width))


def _draw_placeholder(painter: QPainter, box: QRect, channel: Channel) -> None:
    """Marco con el color de la cadena e iniciales, cuando no hay logo."""
    painter.setPen(QColor("#3a4553"))
    painter.setBrush(QColor(channel.brand))
    painter.drawPath(_rounded(QPainterPath(), box, 8))
    initials = "".join(word[0] for word in channel.name.split()[:2]) or channel.name[:2]
    font = QFont(painter.font())
    font.setBold(True)
    font.setPointSizeF(max(8.0, min(15.0, box.height() / 3.0)))
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(box, Qt.AlignmentFlag.AlignCenter, initials.upper())


def _draw_logo(painter: QPainter, box: QRect, channel: Channel,
               loader: LogoLoader | None) -> None:
    pixmap = loader.get(channel.logo_url) if loader else None
    if pixmap is None or pixmap.isNull():
        _draw_placeholder(painter, box, channel)
        return
    scaled = pixmap.scaled(box.size(), Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    x = box.left() + (box.width() - scaled.width()) // 2
    y = box.top() + (box.height() - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)


def _draw_title_line(painter: QPainter, rect: QRect, text: str, font: QFont,
                     color: QColor) -> QRect:
    metrics = QFontMetrics(font)
    painter.setFont(font)
    painter.setPen(color)
    box = QRect(rect.left(), rect.top(), rect.width(), metrics.height())
    painter.drawText(box, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                     _elided(metrics, text, rect.width()))
    return box


#: Texto que precede al siguiente programa, bajo la barra de progreso.
#: Elegida la flecha: 12 px frente a 78 de «Próximamente: ». No hay que abreviar
#: ninguna palabra y el símbolo ya significa «lo que viene» en una lista de TV.
NEXT_PREFIX = "→ "
#: Alternativas medidas en px con la fuente de la línea (8,5 pt). Se comparan con
#: ``--prefijos``: «A continuación» es MÁS largo que «Próximamente», así que no
#: servía como atajo, y «Después» (50) ahorra menos que la flecha (12).
NEXT_PREFIX_OPTIONS = {
    "flecha": "→ ",
    "despues": "Después: ",
    "siguiente": "Siguiente: ",
    "proximamente": "Próximamente: ",
}


def _draw_next_program(painter: QPainter, rect: QRect, info: ProgramInfo, font: QFont,
                       color: QColor, prefix: str = NEXT_PREFIX) -> QRect:
    """Pinta ``Próximamente: <título>`` bajo la barra y devuelve el rect usado.

    El prefijo va atenuado y el título del programa en color normal, para que se
    distinga de un vistazo de lo que se está emitiendo ahora.
    """
    metrics = QFontMetrics(font)
    painter.setFont(font)
    box = QRect(rect.left(), rect.top(), rect.width(), metrics.height())
    if not info.next_title:
        return box

    prefix_w = metrics.horizontalAdvance(prefix)
    dimmer = color.darker(115) if color.lightnessF() > 0.5 else color.lighter(135)
    painter.setPen(dimmer)
    painter.drawText(QRect(box.left(), box.top(), prefix_w, box.height()),
                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, prefix)

    title_width = max(0, box.width() - prefix_w)
    painter.setPen(color)
    painter.drawText(QRect(box.left() + prefix_w, box.top(), title_width, box.height()),
                     Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                     _elided(metrics, info.next_title, title_width))
    return box


def _draw_bar(painter: QPainter, rect: QRect, info: ProgramInfo, font: QFont,
              color: QColor, track: QColor, selected: bool) -> None:
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
    painter.setBrush(QColor(0, 0, 0, 70) if selected else track)
    painter.drawPath(_rounded(path, QRect(left, top, width, BAR_HEIGHT), BAR_HEIGHT / 2))

    filled = int(width * info.progress())
    if filled > 0:
        painter.setBrush(FILL_COLOR)
        painter.drawPath(_rounded(path, QRect(left, top, max(BAR_HEIGHT, filled), BAR_HEIGHT),
                                  BAR_HEIGHT / 2))


# --------------------------------------------------------------------- delegados
class ThreeColumnDelegate(QStyledItemDelegate):
    """RÉPLICA del delegado real de la columna «Programación», para la referencia."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._row_height = 90

    def set_row_height(self, height: int) -> None:
        self._row_height = height

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self._row_height)

    def paint(self, painter, option, index) -> None:
        info = index.data(PROGRAM_ROLE)
        if painter is None or not isinstance(info, ProgramInfo):
            super().paint(painter, option, index)
            return

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        text_color = QColor("#ffffff") if selected else option.palette.text().color()
        secondary, track = _theme_pair(text_color)
        if selected:
            secondary = text_color

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if selected:
            painter.fillRect(option.rect, SELECTED_BG)

        rect = option.rect.adjusted(6, 4, -6, -4)
        title_font = QFont(option.font)
        title_font.setBold(True)
        title_rect = _draw_title_line(painter, rect, info.title, title_font, text_color)

        small = QFont(option.font)
        small.setPointSizeF(max(7.0, small.pointSizeF() - 0.5))
        line_top = title_rect.bottom() + TITLE_GAP
        bar_rect = QRect(rect.left(), line_top, rect.width(),
                         max(QFontMetrics(small).height(), BAR_HEIGHT))
        _draw_bar(painter, bar_rect, info, small, secondary, track, selected)

        # Duración centrada bajo la barra (comportamiento real de la app).
        metrics = QFontMetrics(small)
        painter.setFont(small)
        painter.setPen(secondary)
        painter.drawText(
            QRect(bar_rect.left(), bar_rect.top() + BAR_HEIGHT + 2, bar_rect.width(),
                  metrics.height()),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            info.duration_text(),
        )
        painter.restore()


class SingleColumnDelegate(QStyledItemDelegate):
    """UNA columna con todo: logo + nombre + programa + horas + barra + duración.

    Con ``show_next=True`` añade además, bajo la barra, la línea
    «Próximamente: <siguiente programa>». Eso es solo para la variante normal: la
    compacta existe justo para meter más canales, así que no la lleva.

    El alto de fila se deriva de las métricas de la fuente y del número de líneas,
    así que activar o desactivar la línea nunca recorta nada.
    """

    def __init__(self, loader: LogoLoader, logo_size: QSize,
                 name_style: str = "actual", name_delta: float | None = None,
                 title_delta: float = 0.0,
                 small_delta: float = -0.5, title_gap: int = TITLE_GAP,
                 next_gap: int = NEXT_GAP, name_gap: int = NAME_GAP,
                 show_next: bool = True, next_prefix: str = NEXT_PREFIX,
                 duration_inline: bool = True, parent=None):
        super().__init__(parent)
        self._loader = loader
        self._logo = logo_size
        self._name_style = name_style
        self._name_delta = (NAME_STYLE_DELTAS[name_style] if name_delta is None
                            else name_delta)
        self._title_delta = title_delta
        self._small_delta = small_delta
        self._title_gap = title_gap
        self._next_gap = next_gap
        self._name_gap = name_gap
        self._show_next = show_next
        self._next_prefix = next_prefix
        self._duration_inline = duration_inline
        self._row_height = self._measure_row_height()

    def _measure_row_height(self) -> int:
        """Alto necesario = texto + logo + márgenes; el mayor de los tres manda."""
        font = (self.parent().font() if self.parent() is not None
                else QApplication.font())
        text_h = _content_height(font, name_delta=self._name_delta,
                                 title_delta=self._title_delta,
                                 small_delta=self._small_delta,
                                 title_gap=self._title_gap,
                                 next_gap=self._next_gap,
                                 name_gap=self._name_gap,
                                 with_next=self._show_next)
        return max(text_h, self._logo.height() + 2 * ROW_MARGIN_Y)

    @property
    def row_height(self) -> int:
        """Alto real de cada fila, en px. La tabla DEBE usar este valor."""
        return self._row_height

    def sizeHint(self, option, index) -> QSize:
        return QSize(option.rect.width(), self._row_height)

    def paint(self, painter, option, index) -> None:
        channel = index.data(CHANNEL_ROLE)
        info = index.data(PROGRAM_ROLE)
        if painter is None or not isinstance(channel, Channel) or not isinstance(info, ProgramInfo):
            super().paint(painter, option, index)
            return

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        # OJO: en PyQt6 `option.palette` y `option.font` son ATRIBUTOS, no métodos.
        # Escribir `option.palette()` lanza dentro de paint() y Qt aborta el proceso.
        text_color = QColor("#ffffff") if selected else option.palette.text().color()
        secondary, track = _theme_pair(text_color)
        if selected:
            secondary = text_color

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if selected:
            painter.fillRect(option.rect, SELECTED_BG)

        rect = option.rect.adjusted(8, ROW_MARGIN_Y, -8, -ROW_MARGIN_Y)
        box = QRect(rect.left(), rect.top() + (rect.height() - self._logo.height()) // 2,
                    self._logo.width(), self._logo.height())
        _draw_logo(painter, box, channel, self._loader)

        # El estilo "acento" sangra TODO el bloque de texto para que la barrita
        # vertical quede alineada con las tres líneas, no solo con el nombre.
        indent = (ACCENT_WIDTH + ACCENT_GAP) if self._name_style == "acento" else 0
        text_left = box.right() + 14 + indent
        text = QRect(text_left, rect.top(), rect.right() - text_left, rect.height())

        name_font = QFont(option.font)
        name_font.setBold(True)
        name_font.setPointSizeF(name_font.pointSizeF() + self._name_delta)

        title_font = QFont(option.font)
        title_font.setPointSizeF(title_font.pointSizeF() + self._title_delta)
        title_font.setBold(not self._duration_inline)

        small_font = QFont(option.font)
        small_font.setPointSizeF(max(7.0, small_font.pointSizeF() + self._small_delta))

        name_rect = _draw_title_line(painter, text, channel.name, name_font, text_color)

        if self._name_style == "acento":
            # Barrita azul (mismo celeste de la barra de progreso) a la izquierda
            # del nombre: refuerza la jerarquía sin gritar ni cambiar la tipografía.
            accent = QRect(box.right() + 14, name_rect.top() + 1, ACCENT_WIDTH,
                           max(6, name_rect.height() - 2))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(FILL_COLOR)
            painter.drawRoundedRect(accent, ACCENT_WIDTH / 2, ACCENT_WIDTH / 2)

        program_top = name_rect.bottom() + self._name_gap
        program_rect = QRect(text.left(), program_top, text.width(),
                             QFontMetrics(title_font).height())
        if self._duration_inline:
            # «Telediario 2 · 40 min»: la duración no cuesta una línea extra.
            suffix = f"   ·   {info.duration_text()}"
            suffix_w = QFontMetrics(small_font).horizontalAdvance(suffix)
            _draw_title_line(painter, QRect(text.left(), program_top,
                                            text.width() - suffix_w, program_rect.height()),
                             info.title, title_font, text_color)
            painter.setFont(small_font)
            painter.setPen(secondary)
            painter.drawText(QRect(program_rect.right() - suffix_w, program_top, suffix_w,
                                   program_rect.height()),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, suffix)
        else:
            _draw_title_line(painter, program_rect, info.title, title_font, text_color)

        bar_top = program_rect.bottom() + self._title_gap - 2
        bar_rect = QRect(text.left(), bar_top, text.width(),
                         max(QFontMetrics(small_font).height(), BAR_HEIGHT))
        _draw_bar(painter, bar_rect, info, small_font, secondary, track, selected)

        # «Próximamente: <siguiente programa>» justo debajo de la barra azul.
        # Solo en la variante normal; la compacta no la lleva.
        if self._show_next:
            _draw_next_program(painter,
                               QRect(text.left(), bar_rect.bottom() + self._next_gap,
                                     text.width(), QFontMetrics(small_font).height()),
                               info, small_font, secondary, self._next_prefix)
        painter.restore()


# --------------------------------------------------------------------- construcción
def _make_item(text: str = "") -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return item


def _base_table(rows: int, cols: int) -> QTableWidget:
    table = QTableWidget(rows, cols)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setAlternatingRowColors(True)
    return table


def build_single_column(delegate: SingleColumnDelegate, width: int) -> QTableWidget:
    table = _base_table(len(CHANNELS), 1)
    table.setHorizontalHeaderLabels(["Canal"])
    table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

    # CRÍTICO: `sizeHint()` del delegado NO fija el alto de fila por sí solo. Sin
    # esto el vertical header usa ~30 px, el delegado pinta ~60 px y las filas se
    # montan unas encima de otras.
    vheader = table.verticalHeader()
    vheader.setVisible(False)
    vheader.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
    vheader.setDefaultSectionSize(delegate.row_height)
    vheader.setMinimumSectionSize(delegate.row_height)

    table.setShowGrid(False)
    table.setItemDelegate(delegate)
    for row, channel in enumerate(CHANNELS):
        item = _make_item(channel.name)
        item.setData(CHANNEL_ROLE, channel)
        item.setData(PROGRAM_ROLE, channel.program)
        table.setItem(row, 0, item)
    table.setMinimumWidth(width)
    table.setMaximumWidth(width)
    _fit_table_height(table, delegate.row_height)
    return table


def _fit_table_height(table: QTableWidget, row_height: int) -> None:
    """Fija el alto de la tabla a su contenido exacto.

    Un QTableWidget dentro de un layout no reclama el alto de sus filas (su
    ``sizeHint()`` es el genérico de QAbstractScrollArea), así que la ventana
    salía más baja que la tabla y aparecían scrollbars con las filas cortadas.
    """
    header_h = table.horizontalHeader().sizeHint().height()
    frame = 2 * table.frameWidth()
    table.setFixedHeight(header_h + table.rowCount() * row_height + frame)


def build_reference(delegate: ThreeColumnDelegate, loader: LogoLoader) -> QTableWidget:
    """La tabla actual: Canal | Logo | Programación."""
    table = _base_table(len(CHANNELS), 3)
    table.setHorizontalHeaderLabels(["Canal", "Logo", "Programación"])
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    table.setColumnWidth(1, 120)
    table.verticalHeader().setDefaultSectionSize(90)
    table.setIconSize(QSize(100, 75).expandedTo(table.iconSize()))
    table.setItemDelegateForColumn(2, delegate)

    for row, channel in enumerate(CHANNELS):
        table.setItem(row, 0, _make_item(channel.name))

        logo_item = _make_item()
        logo_item.setData(CHANNEL_ROLE, channel)
        table.setItem(row, 1, logo_item)
        loader.get(channel.logo_url)

        epg_item = _make_item()
        epg_item.setData(PROGRAM_ROLE, channel.program)
        table.setItem(row, 2, epg_item)
    table.setMinimumWidth(420)
    table.setMaximumWidth(420)
    return table


class LogoCellDelegate(QStyledItemDelegate):
    """Columna «Logo» de la referencia: icono centrado en la celda."""

    def __init__(self, loader: LogoLoader, parent=None):
        super().__init__(parent)
        self._loader = loader

    def paint(self, painter, option, index) -> None:
        channel = index.data(CHANNEL_ROLE)
        if painter is None or not isinstance(channel, Channel):
            super().paint(painter, option, index)
            return
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if selected:
            painter.fillRect(option.rect, SELECTED_BG)
        box = option.rect.adjusted(10, 8, -10, -8)
        _draw_logo(painter, box, channel, self._loader)
        painter.restore()


def _card(title: str, note: str, widget: QWidget) -> QFrame:
    """Panel con cabecera y nota. Se aísla del vecino con marco y márgenes amplios."""
    frame = QFrame()
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    frame.setFrameShadow(QFrame.Shadow.Raised)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 14)
    layout.setSpacing(6)
    head = QLabel(f"<b>{title}</b>")
    # Con paneles estrechos el título no cabe en una línea: sin wrap se recorta.
    head.setWordWrap(True)
    sub = QLabel(note)
    sub.setWordWrap(True)
    sub.setStyleSheet("color: #8b95a3;")
    layout.addWidget(head)
    layout.addWidget(sub)
    layout.addWidget(widget)
    # El panel nunca puede encogerse por debajo de la tabla que contiene: así los
    # tres paneles no se solapan ni se aplastan al redimensionar.
    frame.setMinimumWidth(widget.minimumWidth() + 28)
    return frame


#: Ancho de cada panel. Holgado a propósito: con anchos justos los textos de la
#: EPG se eliden todo el rato y cuesta comparar las variantes.
#: Anchos pedidos por el usuario: variante A un 15 % más estrecha (400 -> 340) y
#: variante B un 30 % más estrecha (360 -> 252). Al estrechar, los títulos largos
#: se eliden antes; el resto del layout no cambia.
WIDTH_A = 340
WIDTH_B = 252
WIDTH_REFERENCE = 470
#: Separación horizontal entre paneles, en px.
PANEL_SPACING = 28
#: Margen exterior de la ventana, en px.
WINDOW_MARGIN = 24


def _wire_logos(loader: LogoLoader, tables: list[QTableWidget]) -> None:
    """Repinta las tablas cuando llega un logo."""

    def refresh(*_args) -> None:
        # Con 4 filas, repintar todo sale más barato que rastrear qué canal cambió.
        for table in tables:
            table.viewport().update()

    loader.logo_loaded.connect(refresh)


def build_window(show_reference: bool = False, compare_names: bool = False,
                 compare_prefixes: bool = False) -> QWidget:
    app_window = QWidget()
    layout = QHBoxLayout(app_window)
    layout.setContentsMargins(WINDOW_MARGIN, WINDOW_MARGIN, WINDOW_MARGIN, WINDOW_MARGIN)
    layout.setSpacing(PANEL_SPACING)

    loader = LogoLoader(LOGO_DIR, app_window)
    tables: list[QTableWidget] = []

    if compare_prefixes:
        # Misma variante A con cada prefijo candidato, para elegir el más corto.
        for prefix in NEXT_PREFIX_OPTIONS.values():
            delegate = SingleColumnDelegate(loader, QSize(96, 72), name_style=CHOSEN_NAME_STYLE,
                                            show_next=True, next_prefix=prefix,
                                            parent=app_window)
            tables.append(build_single_column(delegate, WIDTH_A))
            layout.addWidget(_card(
                f"«{prefix.strip()}» · {QFontMetrics(QFont(app_window.font())).horizontalAdvance(prefix)} px",
                "Misma fila de 4 líneas; solo cambia el texto del prefijo.",
                tables[-1]))
        _wire_logos(loader, tables)
        app_window.setWindowTitle("Mockup — prefijo de la línea «siguiente programa»")
        app_window.adjustSize()
        _center_on_primary(app_window)
        return app_window

    if compare_names:
        # Modo comparación: la misma variante A con tres tratamientos del nombre.
        for style, note in (
            ("actual", "Como está ahora: negrita y +1 pt."),
            ("grande", "Solo tamaño: negrita y +2,5 pt."),
            ("acento", "Barrita azul a la izquierda + +1,5 pt."),
        ):
            delegate = SingleColumnDelegate(loader, QSize(96, 72), name_style=style,
                                            show_next=True, parent=app_window)
            tables.append(build_single_column(delegate, WIDTH_A))
            layout.addWidget(_card(
                f"NOMBRE «{style}» · fila {delegate.row_height} px", note, tables[-1]))
        _wire_logos(loader, tables)
        app_window.setWindowTitle("Mockup — resaltado del nombre del canal")
        app_window.adjustSize()
        _center_on_primary(app_window)
        return app_window

    # VARIANTE A — la "normal": logo grande, aire entre líneas y «Próximamente».
    variant_a = SingleColumnDelegate(loader, QSize(96, 72), name_style=CHOSEN_NAME_STYLE,
                                     show_next=True, parent=app_window)
    tables.append(build_single_column(variant_a, WIDTH_A))
    layout.addWidget(_card(
        f"VARIANTE A — normal · 1 columna, logo 96×72, fila {variant_a.row_height} px",
        "Nombre con barrita de acento, duración en línea y «Próximamente» bajo la barra.",
        tables[-1]))

    # VARIANTE B — la "compacta": logo pequeño, espaciados ajustados y sin la
    # línea de «Próximamente» (su objetivo es meter más canales por pantalla).
    variant_b = SingleColumnDelegate(
        loader, QSize(44, 44), title_delta=-0.5, title_gap=5, next_gap=2, name_gap=2,
        show_next=False, parent=app_window)
    tables.append(build_single_column(variant_b, WIDTH_B))
    layout.addWidget(_card(
        f"VARIANTE B — compacta · 1 columna, logo 44×44, fila {variant_b.row_height} px",
        "Sin «Próximamente»: espaciados ajustados para que entren más canales.",
        tables[-1]))

    if show_reference:
        three_col = ThreeColumnDelegate(app_window)
        logo_delegate = LogoCellDelegate(loader, app_window)
        reference = build_reference(three_col, loader)
        reference.setItemDelegateForColumn(1, logo_delegate)
        tables.append(reference)
        layout.addWidget(_card("REFERENCIA — 3 columnas actuales",
                               "Canal | Logo | Programación (reproducción fiel).",
                               reference))

    _wire_logos(loader, tables)

    app_window.setWindowTitle("Mockup — panel de canales en una columna")
    # El tamaño sale del contenido real de los paneles, no de un número a ojo: así
    # ninguno se aplasta ni se solapa con el vecino.
    app_window.adjustSize()
    _center_on_primary(app_window)
    return app_window


def _center_on_primary(window: QWidget) -> None:
    """Centra la ventana en la pantalla principal.

    Sin esto Qt coloca la ventana en la última posición del escritorio virtual,
    que en un equipo con varios monitores puede caer fuera de la vista (X
    negativo), y el usuario no ve nada.
    """
    screen = QApplication.primaryScreen()
    if screen is None:
        return
    area = screen.availableGeometry()
    if window.width() > area.width() or window.height() > area.height():
        window.resize(min(window.width(), area.width() - 40),
                      min(window.height(), area.height() - 60))
    frame = window.frameGeometry()
    frame.moveCenter(area.center())
    window.move(frame.topLeft())


def apply_dark_theme(app: QApplication) -> None:
    """Paleta oscura OPCIONAL. La app real usa el estilo nativo de Windows (claro),
    así que por defecto el mockup tampoco fuerza tema: este modo sirve para ver
    cómo quedarían las tarjetas en oscuro."""
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#20262e"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1a2028"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#212832"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e6e9ee"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e6e9ee"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#2a323d"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e6e9ee"))
    palette.setColor(QPalette.ColorRole.Highlight, SELECTED_BG)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)


def save_shots(directory: Path, show_reference: bool, compare_names: bool = False,
               compare_prefixes: bool = False) -> list[Path]:
    """Captura la ventana a PNG esperando los logos (máx. 8 s) antes de grabar."""
    import time

    directory.mkdir(parents=True, exist_ok=True)
    window = build_window(show_reference, compare_names, compare_prefixes)
    window.show()

    # La descarga de logos es asíncrona: sin esta espera la captura sale con
    # marcadores de posición en lugar de las imágenes reales.
    deadline = time.monotonic() + 8.0
    while time.monotonic() < deadline and not _logos_en_cache():
        QApplication.processEvents()
        time.sleep(0.1)
    QApplication.processEvents()

    if compare_prefixes:
        name = "mockup_prefijos.png"
    elif compare_names:
        name = "mockup_nombres.png"
    elif show_reference:
        name = "mockup_con_referencia.png"
    else:
        name = "mockup.png"
    target = directory / name
    window.grab().save(str(target))
    window.close()
    return [target]


def _logos_en_cache() -> bool:
    """``True`` cuando los 4 logos ya están en disco (o el canal no tiene logo)."""
    return all(
        not channel.logo_url
        or (LOGO_DIR / f"{hashlib.md5(channel.logo_url.encode()).hexdigest()}.png").exists()
        for channel in CHANNELS
    )


def check_geometry(show_reference: bool) -> bool:
    """Verifica que cada fila ocupa el alto que el delegado necesita, sin solapes.

    Es la comprobación que faltaba cuando las filas se montaban unas sobre otras:
    el vertical header usaba su alto por defecto (~30 px) mientras el delegado
    pintaba ~60 px. Devuelve ``True`` si todo está correcto.
    """
    window = build_window(show_reference)
    window.show()
    QApplication.processEvents()

    ok = True
    print(f"ventana: {window.width()}x{window.height()} px")
    for table in window.findChildren(QTableWidget):
        row_h = table.verticalHeader().defaultSectionSize()
        total = sum(table.rowHeight(row) for row in range(table.rowCount()))
        print(f"\ntabla de {table.columnCount()} columna(s): fila={row_h} px, "
              f"{table.rowCount()} filas, suma={total} px, viewport={table.viewport().height()} px")

        previous_bottom = -1
        for row in range(table.rowCount()):
            top = table.rowViewportPosition(row)
            height = table.rowHeight(row)
            overlap = top < previous_bottom
            print(f"   fila {row}: y={top:3d} alto={height:3d} fin={top + height:3d}"
                  f"{'  SOLAPE' if overlap else ''}")
            ok = ok and not overlap
            previous_bottom = top + height

        if total > table.viewport().height():
            print(f"   no caben: {total} > {table.viewport().height()} (aparece scrollbar)")
            ok = False

        delegate = table.itemDelegate()
        option = QStyleOptionViewItem()
        option.rect = table.visualItemRect(table.item(0, 0))
        needed = delegate.sizeHint(option, table.model().index(0, 0)).height()
        print(f"   delegado pide {needed} px, la fila ofrece {table.rowHeight(0)} px")
        ok = ok and needed <= table.rowHeight(0)

    window.close()
    print("\nRESULTADO:", "todo correcto" if ok else "HAY PROBLEMAS")
    return ok


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Mockup del panel de canales en una columna")
    parser.add_argument("--con-referencia", dest="show_reference", action="store_true",
                        help="añadir la tabla actual de 3 columnas para comparar")
    parser.add_argument("--oscuro", dest="dark", action="store_true",
                        help="forzar paleta oscura (la app real va en claro nativo)")
    parser.add_argument("--shot", metavar="DIR", help="guardar PNG y salir sin ventana")
    parser.add_argument("--comprobar", dest="check", action="store_true",
                        help="verificar geometria de filas (sin solapes) y salir")
    parser.add_argument("--nombres", dest="compare_names", action="store_true",
                        help="comparar tres tratamientos del nombre del canal (variante A)")
    parser.add_argument("--prefijos", dest="compare_prefixes", action="store_true",
                        help="comparar prefijos cortos para la línea del siguiente programa")
    args = parser.parse_args(argv)
    show_reference = args.show_reference
    compare_names = args.compare_names
    compare_prefixes = args.compare_prefixes

    app = QApplication(sys.argv)
    if args.dark:
        apply_dark_theme(app)

    if args.shot:
        for path in save_shots(Path(args.shot), show_reference, compare_names,
                               compare_prefixes):
            print(f"escrito: {path}")
        return 0

    if args.check:
        return 0 if check_geometry(show_reference) else 1

    # OJO: hay que guardar la ventana en una variable. Con `build_window(...).show()`
    # el widget se queda sin referencia de Python, Qt lo destruye y el proceso se
    # queda vivo en exec() sin ninguna ventana visible.
    window = build_window(show_reference, compare_names, compare_prefixes)
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))


# --------------------------------------------------------------------------- notas
# Alturas calculadas, no elegidas a ojo. Con Segoe UI 9pt (la de este equipo),
# `_content_height` devuelve:
#
#   variante A (4 líneas + barra, aire normal)        -> 90 px
#   variante B (3 líneas + barra, espaciado ajustado) -> 66 px
#
# La diferencia de 26 px viene de la línea de «Próximamente» (~15 px) más los
# espaciados más ajustados de la compacta. Ese es justo el intercambio: la normal
# informa del siguiente programa, la compacta mete ~40 % más canales por pantalla.
#
# El nombre de la variante normal lleva el estilo «acento» ya aprobado:
# +1,5 pt sobre la fuente base y una barrita celeste (#38bdf8) de 3 px a su
# izquierda, alineada con todo el bloque de texto. Se eligió frente a «grande»
# (+2,5 pt) porque destaca sin ensanchar tanto los nombres largos, y frente a
# dejarlo «actual» porque apenas se distinguía del título del programa.
#
# Por eso el alto se DERIVA de la fuente y de las líneas activas en vez de ser una
# constante: si mañana se añade otra línea o Windows escala el texto,
# `--comprobar` sigue pasando.
#
# Para llevarlo a la aplicación real (sin tocar nada aquí) el cambio sería:
#
#   1. `self.table.setColumnCount(1)` y una sola etiqueta de cabecera.
#   2. Un delegado único por columna 0 que pinte logo + nombre + EPG, en lugar
#      de los tres `setItem` de `_fill_table`.
#   3. Guardar el `Channel` en la columna 0; `_on_item_clicked` ya lee el canal
#      con `data(Qt.ItemDataRole.UserRole)`, así que solo cambia el índice.
#   4. `_on_logo_loaded` pasa a repintar la columna 0 en vez de llamar `setIcon`.
#   5. El progreso se recalcula en cada repintado, así que el `QTimer` de 30 s
#      sigue funcionando sin cambios (`table.viewport().update()` basta).
#   6. Para «Próximamente» hace falta el SIGUIENTE programa: `EPGManager` ya tiene
#      los programas ordenados por canal, así que basta buscar el primero cuyo
#      `start_time` sea posterior a `now` y pasarlo en el `ProgramInfo`.
#
# El pintado usa `option.palette` y `option.font` como ATRIBUTOS: en PyQt6 no son
# métodos y llamarlos con paréntesis aborta el proceso dentro de `paint()`.
