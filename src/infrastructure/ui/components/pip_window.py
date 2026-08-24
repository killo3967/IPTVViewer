"""Ventana Picture-in-Picture (PIP) — componente Qt del modo de vista.

REQ-6: ventana desacoplada (DETACH), siempre encima, sin marco, arrastrable
por el cuerpo y redimensionable por el grip inferior-derecho. Los eventos de
teclado se reenvían a la ventana principal (key forwarding).
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget


class ResizeGrip(QWidget):
    """Grip de redimensionado inferior-derecho (mínimo 160x90)."""

    MIN_WIDTH = 160
    MIN_HEIGHT = 90

    def __init__(self, parent: QWidget = None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self._drag_start_global = None
        self._start_geometry = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_global = event.globalPosition().toPoint()
            self._start_geometry = self.parentWidget().geometry()
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_start_global is not None
            and self.parentWidget() is not None
        ):
            delta = event.globalPosition().toPoint() - self._drag_start_global
            parent = self.parentWidget()
            new_w = max(self._start_geometry.width() + delta.x(), self.MIN_WIDTH)
            new_h = max(self._start_geometry.height() + delta.y(), self.MIN_HEIGHT)
            parent.resize(new_w, new_h)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_start_global = None
        self._start_geometry = None
        event.accept()


class PIPWindow(QWidget):
    """Ventana PIP frameless, siempre encima, con reenvío de teclas."""

    # Señal emitida al mover/redimensionar la ventana: la ventana principal
    # la usa para persistir pip_geometry con debounce (REQ-8 / WU 4.3).
    geometry_changed = pyqtSignal()

    def __init__(self, key_forward_target: QWidget):
        super().__init__(
            key_forward_target,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self._key_forward_target = key_forward_target
        self._drag_start_global = None
        self._drag_start_pos = None
        self._resize_grip = ResizeGrip(self)
        self.setMinimumSize(ResizeGrip.MIN_WIDTH, ResizeGrip.MIN_HEIGHT)

    def set_video_widget(self, widget: QWidget) -> None:
        """Re-parenta el widget de video dentro de la ventana PIP."""
        widget.setParent(self)
        widget.show()

    def moveEvent(self, event):
        """Notifica el movimiento del cuerpo (arrastre) para persistencia."""
        super().moveEvent(event)
        self.geometry_changed.emit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Mantener el grip anclado abajo-derecha
        grip_size = self._resize_grip.size()
        self._resize_grip.move(
            self.width() - grip_size.width(),
            self.height() - grip_size.height(),
        )
        self._resize_grip.raise_()
        self.geometry_changed.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_global = event.globalPosition().toPoint()
            self._drag_start_pos = self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_start_global is not None
        ):
            delta = event.globalPosition().toPoint() - self._drag_start_global
            self.move(self._drag_start_pos + delta)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_start_global = None
        self._drag_start_pos = None
        event.accept()

    def keyPressEvent(self, event):
        """Reenvía todas las teclas a la ventana principal (REQ-6)."""
        if self._key_forward_target is not None:
            QApplication.sendEvent(self._key_forward_target, event)
        event.accept()
