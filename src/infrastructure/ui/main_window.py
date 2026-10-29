import logging
import os
import sys
import threading
import time

import requests
from PyQt6.QtCore import QEvent, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QActionGroup,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.application.services.epg_manager import EPGManager
from src.application.services.playback_manager import PlaybackManager
from src.application.services.playlist_loader import PlaylistLoader
from src.application.services.view_mode_controller import (
    ViewMode,
    ViewModeController,
    decode_splitter_state,
    encode_splitter_state,
    geometry_to_str,
    resolve_zap_index,
    str_to_geometry,
)
from src.domain.entities.channel import Channel
from src.domain.entities.playlist import Playlist
from src.infrastructure.adapters.qt_logo_loader_adapter import QtLogoLoaderAdapter
from src.infrastructure.ui.components.channel_row_delegate import (
    CHANNEL_ROLE,
    EPG_PROGRAM_ROLE,
    ChannelRowDelegate,
    ProgramInfo,
)
from src.infrastructure.ui.components.epg_config_dialog import EPGConfigDialog
from src.infrastructure.ui.components.epg_grid import EPGGridDialog
from src.infrastructure.ui.components.pip_window import PIPWindow
from src.infrastructure.utils.log_safe import safe_url
from src.infrastructure.utils.stream_probe import is_proxied_stream, log_stream_target

APP_VERSION = "1.8.1"

#: Ancho mínimo del panel de canales por modo de vista, en px.
#: Es un mínimo, no un ancho fijo: el splitter permite ensanchar el panel y el
#: espacio restante se lo queda el vídeo.
TABLE_MIN_WIDTH = {"normal": 340, "compact": 252}

MIT_LICENSE_TEXT = """MIT License

Copyright (c) 2026 killo3967

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def _version_tuple(v):
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return (0,)


class SourceEditorDialog(QDialog):
    """Diálogo para añadir o editar una fuente M3U con nombre."""

    def __init__(self, parent=None, source: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Editar lista" if source else "Añadir lista")
        self.setMinimumWidth(450)

        layout = QFormLayout(self)

        self.name_edit = QLineEdit(source.get('name', '') if source else '')
        self.name_edit.setPlaceholderText("Ej: TV España")
        layout.addRow("&Nombre:", self.name_edit)

        self.m3u_edit = QLineEdit(source.get('m3u', '') if source else '')
        self.m3u_edit.setPlaceholderText("http://... o ruta local")
        layout.addRow("&M3U:", self.m3u_edit)

        self.filter_edit = QLineEdit(source.get('filter', '') if source else '')
        self.filter_edit.setPlaceholderText("SPAIN (vacío = sin filtro)")
        layout.addRow("&Filtro:", self.filter_edit)

        self.epg_edit = QLineEdit(source.get('epg', '') if source else '')
        self.epg_edit.setPlaceholderText("http://.../guia.xml")
        layout.addRow("&EPG:", self.epg_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_source(self) -> dict:
        return {
            'name': self.name_edit.text().strip(),
            'm3u': self.m3u_edit.text().strip(),
            'filter': self.filter_edit.text().strip(),
            'epg': self.epg_edit.text().strip(),
        }

class IPTVMainWindow(QMainWindow):
    """Interfaz gráfica principal refactorizada según Arquitectura Hexagonal."""

    #: Emitida (desde el hilo de VLC) cuando un canal agota los reintentos.
    playback_failed = pyqtSignal(str)
    
    def __init__(self, 
                 playlist_loader: PlaylistLoader, 
                 playback_manager: PlaybackManager,
                 epg_manager: EPGManager,
                 logo_loader: QtLogoLoaderAdapter,
                 config: dict,
                 save_callback=None):
        super().__init__()
        self._playlist_loader = playlist_loader
        self._playback_manager = playback_manager
        self.playback_failed.connect(self._on_playback_failed)
        if hasattr(self._playback_manager, "on_playback_failed"):
            self._playback_manager.on_playback_failed = self._notify_playback_failed
        self._epg_manager = epg_manager
        self._logo_loader = logo_loader
        self._config = config
        self._save_callback = save_callback
        self._last_playlist = Playlist() # Caché de la última lista cargada
        self._logo_rows: dict[str, list[int]] = {}  # URL -> filas que usan ese logo

        # Estado de sesión (no persistido)
        self._fullscreen_active = False
        self._cursor_timer: QTimer | None = None
        self._fullscreen_watchers: list[QWidget] = []
        self._splitter_snapshot: bytes | None = None
        self._splitter_save_timer: QTimer | None = None
        self._pip_window: PIPWindow | None = None
        self._pip_open = False
        self._pip_geometry_save_timer: QTimer | None = None
        self._overlay_timer: QTimer | None = None
        self._pre_fullscreen_mode: ViewMode | None = None
        self._muted = False
        self._volume = 100
        self._epg_show_title_only = bool(self._config.get('epg_show_title_only', True))
        self._epg_scroll_timer: QTimer | None = None

        # UI Initialization
        self.setWindowTitle("IPTV Viewer")
        self.resize(1200, 650)
        
        # Cargar icono de la aplicación
        import os
        import sys
        if getattr(sys, 'frozen', False):
            base = getattr(sys, "_MEIPASS", "")
        else:
            base = os.path.join(os.path.dirname(__file__), '../../..')
        icon_path = os.path.join(base, 'resources', 'logo.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self._setup_ui()
        self._create_menus()

        # Controlador de modos de vista: estado puro, layout aplicado por listener
        self._view_controller = ViewModeController(
            ViewMode.parse(config.get('view_mode', 'normal'))
        )
        self._view_controller.register_listener(self._on_view_mode_changed)
        self._apply_layout(self._view_controller.mode)
        self._register_shortcuts()

        # Timer para actualizar EPG cada minuto
        self._epg_timer = QTimer(self)
        self._epg_timer.timeout.connect(self._refresh_epg_display)
        self._epg_timer.start(30000)  # 30 s: la barra de progreso avanza de forma perceptible
        
        # Connect logo loader
        self._logo_loader.logo_loaded.connect(self._on_logo_loaded)

        # Load data
        self._load_data()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        self.splitter = splitter
        self.splitter.splitterMoved.connect(self._arm_splitter_save)
        
        # Tabla
        self.table = QTableWidget()
        self.table.setColumnCount(1)
        self.table.setHorizontalHeaderLabels(["Canales"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Quitar el indicador de foco (barra azul) del estilo nativo Windows 11
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setStyleSheet("QTableWidget::item:selected { background-color: #2f5f8f; color: white; }")
        self.table.itemClicked.connect(self._on_item_clicked)
        # Una sola columna: el delegado pinta logo, nombre y toda la EPG.
        self._channel_delegate = ChannelRowDelegate("normal", self.table)
        self._channel_delegate.set_title_only(self._epg_show_title_only)
        self.table.setItemDelegate(self._channel_delegate)
        self._apply_table_metrics(ViewMode.NORMAL)
        self.table.verticalScrollBar().valueChanged.connect(self._arm_epg_refresh)
        splitter.addWidget(self.table)
        
        # Video
        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background-color: black;")
        splitter.addWidget(self.video_widget)

        # OSD: overlay que muestra el nombre del canal actual (2 s)
        self._channel_overlay = QLabel(self.video_widget)
        self._channel_overlay.setStyleSheet(
            "color: white; background-color: rgba(0, 0, 0, 170);"
            " padding: 8px 16px; border-radius: 6px;"
            " font-size: 18px; font-weight: bold;"
        )
        self._channel_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Native window propia para pintarse ENCIMA del video embebido (VLC/mpv
        # dibujan directamente en el HWND del video_widget y tapan a los hijos Qt).
        self._channel_overlay.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self._channel_overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self._channel_overlay.hide()
        
        # Inicializar el visor de video en el reproductor
        self._playback_manager.initialize_display(int(self.video_widget.winId()))

    def _apply_table_metrics(self, mode: ViewMode):
        """Ajusta delegado, alto de fila y ancho mínimo al modo de vista.

        El alto se toma del delegado, que lo deriva de las métricas de la fuente:
        fijarlo a mano hacía que las filas se montaran unas sobre otras.
        """
        layout = "compact" if mode is ViewMode.COMPACT else "normal"
        self._channel_delegate.set_layout(layout)

        row_height = self._channel_delegate.row_height
        vheader = self.table.verticalHeader()
        vheader.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        vheader.setDefaultSectionSize(row_height)
        vheader.setMinimumSectionSize(row_height)
        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, row_height)

        self.table.setMinimumWidth(TABLE_MIN_WIDTH[layout])

    def _apply_layout(self, mode: ViewMode):
        """Aplica el mapeo de layout por modo (REQ-2, REQ-10).

        Nunca deshabilita QActions (REQ-9): solo muestra/oculta la barra
        de menús y cambia la política de menú contextual de tabla/video.
        """
        default_policy = Qt.ContextMenuPolicy.DefaultContextMenu
        no_menu_policy = Qt.ContextMenuPolicy.NoContextMenu
        if mode is ViewMode.NORMAL:
            self.table.show()
            self.menuBar().show()
            self._apply_table_metrics(mode)
            self.table.setContextMenuPolicy(default_policy)
            self.video_widget.setContextMenuPolicy(default_policy)
            self._restore_splitter_state()
        elif mode is ViewMode.COMPACT:
            # La variante compacta solo cambia el aspecto del panel: ni oculta
            # columnas ni esconde el menú (decisión D10 del ODD).
            self.table.show()
            self.menuBar().show()
            self._apply_table_metrics(mode)
            self.table.setContextMenuPolicy(default_policy)
            self.video_widget.setContextMenuPolicy(default_policy)
        elif mode is ViewMode.VIDEO:
            self.table.hide()
            self.menuBar().hide()
            self.table.setContextMenuPolicy(no_menu_policy)
            self.video_widget.setContextMenuPolicy(no_menu_policy)

    def _on_view_mode_changed(self, old: ViewMode, new: ViewMode):
        """Listener del controlador: layout + persistencia (REQ-2, REQ-8).

        El no-op ya está garantizado por el controlador (activate() no notifica
        si el modo no cambia), así que aquí siempre hay un cambio real.
        """
        if new is ViewMode.VIDEO and old is not ViewMode.VIDEO:
            self._snapshot_splitter_state()
        self._apply_layout(new)
        self._retarget_video()
        self._config['view_mode'] = new.value
        if self._save_callback:
            self._save_callback(self._config)
        if new is ViewMode.VIDEO:
            QTimer.singleShot(0, self._show_channel_overlay)

    def _retarget_video(self):
        """Re-apunta la salida del reproductor al winId actual (REQ-7).

        El winId se re-lee en cada llamada (nunca se cachea): puede cambiar
        tras setParent/hide-show.
        """
        self._playback_manager.initialize_display(int(self.video_widget.winId()))

    def _arm_splitter_save(self):
        """Arma el guardado diferido del estado del splitter (REQ-8).

        Se salta mientras la tabla está oculta (VIDEO) para que el estado
        colapsado nunca pise el estado persistido bueno.
        """
        if self.table.isHidden():
            return
        timer = self._splitter_save_timer
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._flush_splitter_state)
            self._splitter_save_timer = timer
        timer.start(300)

    def _flush_splitter_state(self):
        self._config['splitter_state'] = encode_splitter_state(
            bytes(self.splitter.saveState())
        )
        if self._save_callback:
            self._save_callback(self._config)

    def _snapshot_splitter_state(self):
        """Snapshot síncrono PRE-ocultación al entrar en VIDEO (REQ-8).

        Se ejecuta antes de ocultar la tabla: este es el estado autoritativo
        guardado antes de que el layout colapsado pueda sobreescribirlo.
        """
        snapshot = bytes(self.splitter.saveState())
        self._splitter_snapshot = snapshot
        self._config['splitter_state'] = encode_splitter_state(snapshot)
        if self._save_callback:
            self._save_callback(self._config)

    def _restore_splitter_state(self):
        """Restaura el splitter: snapshot de sesión primero, persistido después."""
        state = self._splitter_snapshot
        if state is None:
            state = decode_splitter_state(self._config.get('splitter_state', ''))
        if state is not None:
            self.splitter.restoreState(state)

    def _register_shortcuts(self):
        """Registra los atajos de modos de vista (REQ-3).

        Alt+1..3 cambian de modo; Alt+4 alterna la ventana PIP (REQ-6,
        cuerpo implementado en la integración de PIP).
        """
        QShortcut(QKeySequence("Alt+1"), self, activated=lambda: self._view_controller.activate(ViewMode.NORMAL))
        QShortcut(QKeySequence("Alt+2"), self, activated=lambda: self._view_controller.activate(ViewMode.COMPACT))
        QShortcut(QKeySequence("Alt+3"), self, activated=lambda: self._view_controller.activate(ViewMode.VIDEO))
        QShortcut(QKeySequence("Alt+4"), self, activated=self._toggle_pip)
        QShortcut(QKeySequence("P"), self, activated=self._toggle_pip)
        # ↑/↓ sin Shift zapean; con Shift ajustan volumen. Qt matchea Shift+Down
        # contra el atajo plano "Down" (los modificadores no anulan el match),
        # asi que la distincion se hace en el handler via modifiers.
        QShortcut(QKeySequence("Up"), self, activated=self._on_up_key)
        QShortcut(QKeySequence("Down"), self, activated=self._on_down_key)
        QShortcut(QKeySequence("F"), self, activated=self._toggle_fullscreen)
        QShortcut(QKeySequence("Esc"), self, activated=self._exit_fullscreen)
        # Ctrl+G debe funcionar con la barra de menús oculta (REQ-9): el atajo
        # del QAction muere al ocultar el menú, así que se registra a nivel
        # de ventana y se dispara la misma acción (nunca deshabilitada).
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self.view_epg_action.trigger)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._toggle_mute)

    def keyPressEvent(self, event):
        """Gestiona teclas reenviadas desde el PIP (REQ-6).

        Con la ventana principal oculta los QShortcut de ventana no
        disparan; PIPWindow reenvia el QKeyEvent crudo via sendEvent y
        se maneja aqui. sendEvent no activa atajos: no hay doble disparo.
        """
        key = event.key()
        modifiers = event.modifiers()
        alt = Qt.KeyboardModifier.AltModifier
        ctrl = Qt.KeyboardModifier.ControlModifier
        shift = Qt.KeyboardModifier.ShiftModifier
        if key == Qt.Key.Key_P and not modifiers or key == Qt.Key.Key_4 and modifiers & alt:
            self._toggle_pip()
        elif key == Qt.Key.Key_Up:
            if modifiers & shift:
                self._change_volume(+5)
            else:
                self._zap(-1)
        elif key == Qt.Key.Key_Down:
            if modifiers & shift:
                self._change_volume(-5)
            else:
                self._zap(+1)
        elif key == Qt.Key.Key_F and not modifiers:
            self._toggle_fullscreen()
        elif key == Qt.Key.Key_Escape:
            self._exit_fullscreen()
        elif key == Qt.Key.Key_G and modifiers & ctrl:
            self.view_epg_action.trigger()
        elif key == Qt.Key.Key_1 and modifiers & alt:
            self._view_controller.activate(ViewMode.NORMAL)
        elif key == Qt.Key.Key_2 and modifiers & alt:
            self._view_controller.activate(ViewMode.COMPACT)
        elif key == Qt.Key.Key_3 and modifiers & alt:
            self._view_controller.activate(ViewMode.VIDEO)
        elif key == Qt.Key.Key_S and modifiers & ctrl:
            self._toggle_mute()
        else:
            super().keyPressEvent(event)

    def _toggle_pip(self):
        """Alterna la ventana PIP: DETACH del video_widget (REQ-6).

        Nunca se auto-abre al arrancar; solo se crea de forma perezosa en el
        primer uso y se reutiliza (oculta) después.
        """
        if self._pip_open:
            self._close_pip()
        else:
            self._open_pip()

    def _open_pip(self):
        pip = self._pip_window
        if pip is None:
            # Top-level (sin padre): si fuera hija de la principal, al
            # ocultarla Qt ocultaria tambien el PIP.
            pip = PIPWindow(self, parent=None)
            pip.geometry_changed.connect(self._arm_pip_geometry_save)
            pip.closed.connect(self._close_pip)
            self._pip_window = pip
        pip.set_video_widget(self.video_widget)
        self._apply_pip_geometry(pip)
        pip.show()
        self._pip_open = True
        # Ocultar la principal: el PIP queda como unica ventana visible
        # (desaparece tambien de la barra de tareas). La app sigue viva
        # porque la principal solo se oculta, no se cierra.
        self.hide()
        pip.raise_()
        pip.activateWindow()
        self._retarget_video()

    def _close_pip(self):
        pip = self._pip_window
        if pip is None:
            return
        # Cancelar el guardado diferido: los cambios de geometría durante el
        # cierre no deben persistirse (WU 4.3 / REFACTOR).
        if self._pip_geometry_save_timer is not None:
            self._pip_geometry_save_timer.stop()
        pip.hide()
        self.video_widget.setParent(self.splitter)
        self.splitter.insertWidget(1, self.video_widget)
        # Restaurar la principal (el PIP era la unica ventana visible).
        if not self.isVisible():
            self.show()
            self.raise_()
            self.activateWindow()
        self._pip_open = False
        self._apply_layout(self._view_controller.mode)
        self._retarget_video()

    def _arm_pip_geometry_save(self):
        """Arma el guardado diferido (300 ms) de pip_geometry (REQ-8).

        Se dispara desde la señal geometry_changed de PIPWindow (move/resize
        del cuerpo o del grip); el debounce evita escrituras a ráfagas.
        """
        timer = self._pip_geometry_save_timer
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._flush_pip_geometry)
            self._pip_geometry_save_timer = timer
        timer.start(300)

    def _flush_pip_geometry(self):
        """Persiste la geometría actual del PIP vía save_callback (REQ-8)."""
        if self._pip_window is None or not self._pip_open:
            return
        x, y, w, h = self._pip_window.geometry().getRect()
        self._config['pip_geometry'] = geometry_to_str(x, y, w, h)
        if self._save_callback:
            self._save_callback(self._config)

    def _apply_pip_geometry(self, pip):
        """Aplica geometría persistida válida o la colocación por defecto."""
        parsed = str_to_geometry(self._config.get('pip_geometry', ''))
        if parsed is not None:
            pip.setGeometry(*parsed)
            return
        screen = QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen is not None else None
        if avail is not None:
            pip.setGeometry(avail.right() - 480 - 20, avail.top() + 20, 480, 270)
        else:
            pip.resize(480, 270)

    def _zap(self, direction: int):
        """Cambia al canal anterior/siguiente con wrap-around (REQ-5).

        Funciona en cualquier modo: el atajo es de ventana (WindowShortcut)
        y la resolución de índice es la función pura del servicio.
        """
        channels = self._last_playlist.channels
        idx = resolve_zap_index(
            channels, self._playback_manager.current_channel, direction
        )
        if idx is not None:
            self._playback_manager.play_channel(channels[idx])
            if self._view_controller.mode is ViewMode.VIDEO or self._fullscreen_active:
                self._show_channel_overlay()

    def _on_up_key(self):
        """↑ plano zapea; ↑ con Shift sube volumen (mismo atajo, distinto modificador)."""
        if QApplication.queryKeyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._change_volume(+5)
        else:
            self._zap(-1)

    def _on_down_key(self):
        """↓ plano zapea; ↓ con Shift baja volumen (mismo atajo, distinto modificador)."""
        if QApplication.queryKeyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._change_volume(-5)
        else:
            self._zap(+1)

    def _toggle_mute(self):
        """Alterna silenciado/audible (Ctrl+S, también desde el PIP)."""
        self._muted = not self._muted
        self._playback_manager.set_muted(self._muted)

    def _change_volume(self, delta: int):
        """Ajusta el volumen en pasos de 5, acotado a 0-100 (Shift+↑/↓)."""
        self._volume = max(0, min(100, self._volume + delta))
        self._playback_manager.set_volume(self._volume)

    def _show_channel_overlay(self):
        """Muestra el nombre del canal actual en un OSD durante 2 s."""
        channel = self._playback_manager.current_channel
        name = channel.name if isinstance(channel, Channel) else ""
        self._show_overlay(name)

    def _notify_playback_failed(self, channel):
        """Callback del PlaybackManager; puede llegar desde el hilo de VLC."""
        name = channel.name if isinstance(channel, Channel) else ""
        self.playback_failed.emit(name)

    def _on_playback_failed(self, name: str):
        """Avisa en el OSD de que el canal no se puede reproducir."""
        self._show_overlay(f"Sin señal: {name}" if name else "Sin señal")

    def _show_overlay(self, text: str):
        """Muestra un texto en el OSD del vídeo durante 2 s."""
        self._channel_overlay.setText(text)
        self._channel_overlay.adjustSize()
        x = (self.video_widget.width() - self._channel_overlay.width()) // 2
        y = self.video_widget.height() - self._channel_overlay.height() - 40
        self._channel_overlay.move(max(x, 0), max(y, 0))
        self._channel_overlay.show()
        self._channel_overlay.raise_()
        timer = self._overlay_timer
        if timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self._channel_overlay.hide)
            self._overlay_timer = timer
        timer.start(2000)

    def _toggle_fullscreen(self):
        """Alterna el eje de pantalla completa (REQ-4). Estado de sesión."""
        if self._fullscreen_active:
            self._exit_fullscreen()
        else:
            self._enter_fullscreen()

    def _enter_fullscreen(self):
        """Entra en pantalla completa forzando el modo VIDEO (F = ALT+3 + fullscreen)."""
        self._pre_fullscreen_mode = self._view_controller.mode
        self._fullscreen_active = True
        self.showFullScreen()
        cursor_timer = QTimer(self)
        cursor_timer.setSingleShot(True)
        cursor_timer.timeout.connect(self._on_cursor_timeout)
        cursor_timer.start(3000)
        self._cursor_timer = cursor_timer
        central = self.centralWidget()
        assert central is not None
        self._fullscreen_watchers = [
            self, central, self.splitter, self.table, self.video_widget,
        ]
        for w in self._fullscreen_watchers:
            w.installEventFilter(self)
        self._view_controller.activate(ViewMode.VIDEO)
        QTimer.singleShot(0, self._show_channel_overlay)

    def _exit_fullscreen(self):
        """Única ruta de salida de pantalla completa (F-off, Esc, closeEvent).

        Cancela el timer, restaura el cursor visible y quita los filtros.
        No-op si no estamos en pantalla completa.
        """
        if not self._fullscreen_active:
            return
        self._fullscreen_active = False
        if self._cursor_timer is not None:
            self._cursor_timer.stop()
        self.unsetCursor()
        for w in self._fullscreen_watchers:
            w.removeEventFilter(self)
        self._fullscreen_watchers = []
        self.showNormal()
        if self._pre_fullscreen_mode is not None:
            self._view_controller.activate(self._pre_fullscreen_mode)
            self._pre_fullscreen_mode = None

    def _on_cursor_timeout(self):
        """Oculta el cursor tras 3 s sin movimiento (REQ-4)."""
        self.setCursor(Qt.CursorShape.BlankCursor)

    def eventFilter(self, obj, event):
        """Restaura el cursor y reinicia el timer ante cualquier MouseMove."""
        if event.type() == QEvent.Type.MouseMove and self._fullscreen_active:
            self.unsetCursor()
            if self._cursor_timer is not None:
                self._cursor_timer.start(3000)
        return super().eventFilter(obj, event)

    def _create_menus(self):
        """Crea el sistema de menús."""
        menubar = self.menuBar()
        
        # Menú Archivo
        file_menu = menubar.addMenu("&Archivo")

        view_epg_action = file_menu.addAction("Ver &Parrilla EPG...")
        view_epg_action.triggered.connect(self._show_epg_grid)
        self.view_epg_action = view_epg_action
        # Sin setShortcut aquí: Ctrl+G se registra a nivel de ventana en
        # _register_shortcuts() (el atajo del QAction muere al ocultar el
        # menú; REQ-9 exige que siga funcionando en COMPACT/VIDEO).

        exit_action = file_menu.addAction("&Salir")
        exit_action.triggered.connect(self.close)
        
        # Menú Reproducción
        playback_menu = menubar.addMenu("&Reproducción")
        hw_group = QActionGroup(self)
        
        self.hw_off_action = playback_menu.addAction("Aceleración por hardware desactivado")
        self.hw_off_action.setCheckable(True)
        self.hw_off_action.setActionGroup(hw_group)
        self.hw_off_action.triggered.connect(lambda: self._set_hw_accel(False))
        
        self.hw_on_action = playback_menu.addAction("Activación por hardware activado")
        self.hw_on_action.setCheckable(True)
        self.hw_on_action.setActionGroup(hw_group)
        self.hw_on_action.triggered.connect(lambda: self._set_hw_accel(True))
        
        # Estado inicial
        if self._config.get('hw_acceleration', False):
            self.hw_on_action.setChecked(True)
        else:
            self.hw_off_action.setChecked(True)
        
        # Menú Listas (Dinámico)
        self._playlists_menu = menubar.addMenu("&Mis Listas")
        self._update_playlists_menu()

        # Menú Configuración
        config_menu = menubar.addMenu("Con&figuración")
        
        config_action = config_menu.addAction("&Configuración del Reproductor...")
        config_action.triggered.connect(self._open_engine_options_dialog)

        proxy_action = config_menu.addAction("Configuración de &Proxy...")
        proxy_action.triggered.connect(self._open_proxy_config_dialog)

        epg_action = config_menu.addAction("Configuración de &EPG...")
        epg_action.triggered.connect(self._open_epg_config_dialog)

        # Menú Ayuda
        help_menu = menubar.addMenu("Ay&uda")

        about_action = help_menu.addAction("&Versión...")
        about_action.triggered.connect(self._show_about)

        shortcuts_action = help_menu.addAction("&Teclas...")
        shortcuts_action.triggered.connect(self._show_shortcuts)

        license_action = help_menu.addAction("&Licencia...")
        license_action.triggered.connect(self._show_license)

        updates_action = help_menu.addAction("Comprobar &actualizaciones...")
        updates_action.triggered.connect(self._check_updates)

        repo_action = help_menu.addAction("&Repositorio en GitHub...")
        repo_action.triggered.connect(self._open_repository)

    def _update_playlists_menu(self):
        """Actualiza el menú dinámico de listas guardadas."""
        self._playlists_menu.clear()
        sources = self._config.get('sources', {})
        active_idx = self._config.get('active', 0)

        # Acciones de gestión
        add_action = self._playlists_menu.addAction("&Añadir lista...")
        add_action.triggered.connect(self._add_source_dialog)

        if sources:
            self._playlists_menu.addSeparator()

        for idx in sorted(sources.keys()):
            src = sources[idx]
            name = src.get('name', f'Lista {idx+1}')

            action = self._playlists_menu.addAction(name)
            action.setCheckable(True)
            if idx == active_idx:
                action.setChecked(True)

            action.triggered.connect(lambda checked, i=idx: self._switch_playlist(i))

        if sources:
            self._playlists_menu.addSeparator()

            edit_action = self._playlists_menu.addAction("&Editar lista activa...")
            edit_action.triggered.connect(self._edit_active_source)

            delete_action = self._playlists_menu.addAction("&Eliminar lista activa")
            delete_action.triggered.connect(self._delete_current_source)

    def _add_source_dialog(self):
        """Abre el diálogo para añadir una nueva fuente M3U."""
        dialog = SourceEditorDialog(self)
        if dialog.exec():
            src = dialog.get_source()
            if not src['name'] or not src['m3u']:
                QMessageBox.warning(self, "Campos requeridos", "Nombre y M3U son obligatorios.")
                return

            sources = self._config.get('sources', {})
            new_idx = max(sources.keys(), default=-1) + 1
            sources[new_idx] = src
            self._config['sources'] = sources

            logging.info(f"Usuario añade lista: {src['name']} → {src['m3u']}")
            self._switch_playlist(new_idx)

    def _edit_active_source(self):
        """Edita la fuente activa."""
        sources = self._config.get('sources', {})
        active_idx = self._config.get('active', 0)
        if active_idx not in sources:
            return

        dialog = SourceEditorDialog(self, sources[active_idx])
        if dialog.exec():
            src = dialog.get_source()
            if not src['name'] or not src['m3u']:
                QMessageBox.warning(self, "Campos requeridos", "Nombre y M3U son obligatorios.")
                return

            sources[active_idx] = src
            self._config['sources'] = sources

            logging.info(f"Usuario edita lista: {src['name']}")
            self._update_playlists_menu()
            self._load_data()

            if self._save_callback:
                self._save_callback(self._config)

    def _switch_playlist(self, idx: int):
        """Cambia a la fuente por índice."""
        sources = self._config.get('sources', {})
        if idx not in sources:
            return

        self._config['active'] = idx
        if self._save_callback:
            self._save_callback(self._config)

        src = sources[idx]
        logging.info(f"Cambiando a lista: {src['name']}")
        self._update_playlists_menu()
        self._load_data()

    def _delete_current_source(self):
        """Elimina la fuente activa."""
        sources = self._config.get('sources', {})
        active_idx = self._config.get('active', 0)

        if len(sources) <= 1:
            QMessageBox.warning(self, "Acción denegada", "No puedes eliminar la única lista disponible.")
            return

        if active_idx in sources:
            src = sources[active_idx]
            logging.info(f"Usuario elimina lista: {src['name']}")
            del sources[active_idx]

            # Reindexar para mantener índices contiguos
            new_sources = {}
            for new_i, (_, val) in enumerate(sorted(sources.items())):
                new_sources[new_i] = val
            new_active = 0
            self._config['sources'] = new_sources
            self._config['active'] = new_active

            if self._save_callback:
                self._save_callback(self._config)

            self._update_playlists_menu()
            self._load_data()

    def _load_data(self):
        sources = self._config.get('sources', {})
        active_idx = self._config.get('active', 0)
        active_src = sources.get(active_idx, {})

        source = active_src.get('m3u', '')
        group = active_src.get('filter', '')
        nombre = active_src.get('name') or f'Lista {active_idx + 1}'

        # Traza de la carga: sin estas líneas el log no dice si se llegó al
        # servidor, cuántos canales llegaron, ni por qué se quedó en cero.
        logging.info("Lista activa: %r desde %s", nombre, safe_url(source))
        inicio = time.monotonic()
        try:
            playlist = self._playlist_loader.load_and_filter(source, group)
        except Exception as e:
            logging.error(
                "Lista %r: error al cargar tras %.2f s: %s",
                nombre, time.monotonic() - inicio, e,
            )
            QMessageBox.critical(self, "Error", f"No se pudo cargar la lista: {e}")
            return

        tardanza = time.monotonic() - inicio
        if len(playlist) > 0:
            logging.info(
                "Lista %r: %d canales en pantalla en %.2f s",
                nombre, len(playlist), tardanza,
            )
        else:
            logging.error(
                "Lista %r: 0 canales tras %.2f s; revisa la URL (%s) y el filtro %r",
                nombre, tardanza, safe_url(source), group,
            )

        self._last_playlist = playlist
        self._fill_table(playlist)

    def _show_epg_grid(self):
        """Muestra el diálogo de la parrilla EPG."""
        if not self._epg_manager.has_data:
            QMessageBox.information(self, "EPG", "No hay datos de programación cargados.")
            return
            
        dialog = EPGGridDialog(self._epg_manager, self._last_playlist, self)
        dialog.exec()

    def _set_epg_url(self):
        """Permite al usuario configurar la URL de la EPG de la fuente activa."""
        sources = self._config.get('sources', {})
        active_idx = self._config.get('active', 0)
        active_src = sources.get(active_idx, {})
        current_url = active_src.get('epg', '')
        url, ok = QInputDialog.getText(
            self, "Configurar URL de EPG",
            "Introduce la URL de la guía (XMLTV):",
            text=current_url
        )
        if ok and url:
            logging.info(f"Usuario cambia URL de EPG a: {url}")
            self._update_epg_source(url)

    def _set_epg_local(self):
        """Permite al usuario cargar un archivo EPG local."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar EPG Local", "", "Archivos XMLTV (*.xml *.xml.gz)"
        )
        if file_path:
            logging.info(f"Usuario carga EPG local: {file_path}")
            self._update_epg_source(file_path)

    def _set_hw_accel(self, enabled: bool):
        """Actualiza la configuración de aceleración por hardware."""
        if self._config.get('hw_acceleration') == enabled:
            return
            
        self._config['hw_acceleration'] = enabled
        logging.info(f"Usuario cambia aceleración hardware a: {enabled}")
        self._playback_manager.set_hw_accel(enabled)
        
        if self._save_callback:
            self._save_callback(self._config)
            
        status = "activada" if enabled else "desactivada"
        
        # Sincronizar en vlc_config si existe
        if 'vlc_config' in self._config:
            self._config['vlc_config']['hw_acceleration'] = enabled
            
        QMessageBox.information(self, "Reproducción", f"Aceleración por hardware {status}.\nEl cambio se aplicará en la siguiente reproducción.")

    def _open_engine_options_dialog(self):
        """Abre el diálogo de configuración técnica del motor (VLC y mpv)."""
        from src.infrastructure.ui.components.engine_config_dialog import EngineConfigDialog
        
        current_engine = self._config.get('player_engine', 'vlc')
        vlc_cfg = self._config.get('vlc_config', {})
        mpv_cfg = self._config.get('mpv_config', {})
            
        dialog = EngineConfigDialog(current_engine, vlc_cfg, mpv_cfg, self)
        
        if dialog.exec():
            new_engine, new_vlc_cfg, new_mpv_cfg = dialog.get_results()

            if new_engine in ('mpv', 'mpv-v3'):
                from src.infrastructure.ui.mpv_bootstrap_dialog import ensure_mpv_engine
                new_engine = ensure_mpv_engine(new_engine, self)
            
            # Persistir cambios en el objeto de config
            self._config['player_engine'] = new_engine
            self._config['vlc_config'] = new_vlc_cfg
            self._config['mpv_config'] = new_mpv_cfg
            
            # Sincronizar ajuste de hardware según motor activo
            hw_enabled = new_mpv_cfg.get('hw_acceleration') if new_engine in ('mpv', 'mpv-v3') else new_vlc_cfg.get('hw_acceleration')
            self._config['hw_acceleration'] = hw_enabled
            self.hw_on_action.setChecked(hw_enabled)
            self.hw_off_action.setChecked(not hw_enabled)

            # ¿Ha cambiado el motor? libmpv se carga una sola vez por proceso,
            # así que cambiar de motor (o de variante mpv) exige reiniciar la app.
            if new_engine != current_engine:
                logging.info(f"Cambiando motor de {current_engine} a {new_engine}: reiniciando...")
                self._restart_app()
                return

            # Solo actualizar opciones del motor actual (mismo motor).
            current_cfg = new_mpv_cfg if new_engine in ('mpv', 'mpv-v3') else new_vlc_cfg
            self._playback_manager.update_engine_options(current_cfg)

            if self._save_callback:
                self._save_callback(self._config)
            
            QMessageBox.information(self, "Reproductor", 
                                  f"Configuración de {new_engine.upper()} actualizada.")

    def _restart_app(self):
        """Reinicia la app para aplicar un cambio de motor.

        ``libmpv`` se carga una sola vez por proceso, así que cambiar entre las
        variantes de mpv (genérica/AVX2) o entre motores exige relanzar. Se
        persiste la configuración y se detiene el proxy Tor antes de relanzar.
        """
        if self._save_callback:
            self._save_callback(self._config)
        try:
            from src.infrastructure.utils.proxy import TorpyProxyManager
            TorpyProxyManager.get_instance().stop()
        except Exception:
            logging.exception("No se pudo detener el proxy Tor antes de reiniciar")
        os.execl(sys.executable, sys.executable, *sys.argv)

    def _open_proxy_config_dialog(self):
        """Abre el diálogo de configuración independiente del Proxy."""
        from src.infrastructure.ui.components.proxy_config_dialog import ProxyConfigDialog
        from src.infrastructure.utils.proxy import setup_proxy
        
        proxy_cfg = self._config.get('proxy_config', {})
        dialog = ProxyConfigDialog(proxy_cfg, self)
        
        if dialog.exec():
            new_proxy_cfg = dialog.get_results()
            self._config['proxy_config'] = new_proxy_cfg
            
            # Aplicar inmediatamente a nivel global
            setup_proxy(new_proxy_cfg)

            # Reiniciar el reproductor para aplicar el nuevo proxy (antes no se aplicaba en runtime)
            from src.infrastructure.adapters.mpv_player_adapter import MpvPlayerAdapter
            from src.infrastructure.adapters.player_factory import build_player_adapter
            from src.infrastructure.adapters.vlc_player_adapter import VlcPlayerAdapter

            engine = self._config.get('player_engine', 'vlc')
            if engine in ('mpv', 'mpv-v3'):
                from src.infrastructure.ui.mpv_bootstrap_dialog import ensure_mpv_engine
                engine = ensure_mpv_engine(engine, self)
            new_adapter = build_player_adapter(
                engine,
                self._config.get('vlc_config'),
                self._config.get('mpv_config'),
                new_proxy_cfg,
                VlcPlayerAdapter,
                MpvPlayerAdapter,
            )
            self._playback_manager.switch_player_engine(new_adapter, int(self.video_widget.winId()))
            
            # Persistir
            if self._save_callback:
                self._save_callback(self._config)
                
            QMessageBox.information(self, "Proxy", "Configuración de red actualizada correctamente.")

    def _update_epg_source(self, source):
        """Actualiza la fuente de EPG, recarga los datos y persiste la configuración."""
        try:
            self._epg_manager.update_epg(source)
            sources = self._config.get('sources', {})
            active_idx = self._config.get('active', 0)
            if active_idx in sources:
                sources[active_idx]['epg'] = source
            if self._save_callback:
                self._save_callback(self._config)

            self._refresh_epg_display()
            QMessageBox.information(self, "EPG", "Guía de programación actualizada correctamente.")
        except Exception as e:
            QMessageBox.critical(self, "Error EPG", f"No se pudo cargar la EPG: {e}")

    def _make_item(self, text: str = "") -> QTableWidgetItem:
        """Crea un item no editable (evita el cursor de edición al hacer clic)."""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def _fill_table(self, playlist):
        self.table.setRowCount(len(playlist))
        self._logo_rows = {}
        for row, channel in enumerate(playlist):
            # Una sola celda por canal: el delegado pinta logo, nombre y EPG.
            item = self._make_item()
            item.setData(CHANNEL_ROLE, channel)
            item.setData(EPG_PROGRAM_ROLE, None)
            self.table.setItem(row, 0, item)
            if channel.logo_url:
                self._logo_rows.setdefault(channel.logo_url, []).append(row)
                self._logo_loader.get_logo(channel.logo_url)

        # Actualizar visualización de EPG inmediatamente (todas las filas)
        self._refresh_epg_display(visible_only=False)

    def _open_epg_config_dialog(self):
        """Abre el diálogo de configuración de la EPG y aplica el cambio."""
        dialog = EPGConfigDialog(self._epg_show_title_only, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        title_only = dialog.title_only()
        self._config['epg_show_title_only'] = title_only
        if self._save_callback:
            self._save_callback(self._config)

        logging.info(f"Usuario cambia configuración de EPG: solo título={title_only}")
        self._apply_epg_title_only(title_only)

    def _apply_epg_title_only(self, title_only: bool):
        """Aplica el modo «solo título»: sin horas, barra, duración ni siguiente."""
        self._epg_show_title_only = title_only
        self._channel_delegate.set_title_only(title_only)
        # El alto de fila depende de las líneas visibles: hay que recalcularlo.
        self._apply_table_metrics(self._view_controller.mode)
        self._refresh_epg_display(visible_only=False)

    def _arm_epg_refresh(self):
        """Programa un refresco de la columna Programación tras moverse por la tabla."""
        if self._epg_scroll_timer is None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(120)
            timer.timeout.connect(self._refresh_epg_display)
            self._epg_scroll_timer = timer
        self._epg_scroll_timer.start()

    def _visible_rows(self) -> range:
        """Filas visibles ahora mismo (todas si la tabla aún no tiene layout)."""
        row_count = self.table.rowCount()
        if row_count == 0:
            return range(0)
        first = self.table.rowAt(0)
        last = self.table.rowAt(max(0, self.table.viewport().height() - 1))
        if first < 0 or last < 0:
            return range(row_count)
        return range(first, last + 1)

    def _refresh_epg_display(self, visible_only: bool = True):
        """Actualiza las filas con el programa en curso y el siguiente.

        Por defecto solo recalcula las filas visibles. El porcentaje de la barra
        se calcula al pintar (ver ``ChannelRowDelegate``), así que repintar el
        viewport basta para que todas las barras visibles avancen.
        """
        rows = self._visible_rows() if visible_only else range(self.table.rowCount())
        for row in rows:
            self._refresh_epg_row(row)
        self.table.viewport().update()

    def _refresh_epg_row(self, row: int):
        """Fija en la fila el programa en curso y el siguiente (o los limpia)."""
        item = self.table.item(row, 0)
        if item is None:
            return

        channel = item.data(CHANNEL_ROLE)
        if not isinstance(channel, Channel):
            item.setData(EPG_PROGRAM_ROLE, None)
            return

        # Una sola consulta por fila: la ventana ya no pide actual y siguiente
        # por separado, que recorrería y ordenaría la lista dos veces.
        program, next_program = self._epg_manager.get_current_and_next(
            channel.tvg_id or "", channel.name
        )

        if program is None:
            item.setData(EPG_PROGRAM_ROLE, None)
            return

        item.setData(EPG_PROGRAM_ROLE, ProgramInfo(
            title=program.title,
            start=program.start_time,
            end=program.end_time,
            next_title=next_program.title if next_program else "",
        ))

    def _on_item_clicked(self, item: QTableWidgetItem):
        channel = self.table.item(item.row(), 0).data(CHANNEL_ROLE)
        if isinstance(channel, Channel):
            logging.info("Reproduciendo: %s (%s)", channel.name, safe_url(channel.url))
            self._trace_stream_target(channel.url)
            self._playback_manager.play_channel(channel)

    def _trace_stream_target(self, url: str, timeout: float = 3.0):
        """Apunta en el log la URL real del stream, sin retrasar la reproducción.

        Con un front-end delante (xteve) la lista trae ``/stream/<hash>`` y la URL
        del proveedor solo aparece en el 302, así que se resuelve en un hilo
        aparte: la sonda no puede bloquear el arranque del motor.
        """
        if not is_proxied_stream(url):
            return
        threading.Thread(
            target=log_stream_target,
            args=(url, timeout),
            name="stream-target",
            daemon=True,
        ).start()

    def _on_logo_loaded(self, url: str, pixmap: QPixmap):
        """Actualiza solo las filas que usan este logo (índice inverso O(1))."""
        icon = QIcon(pixmap)
        for row in self._logo_rows.get(url, []):
            item = self.table.item(row, 0)
            if item is not None:
                item.setIcon(icon)


    def _show_about(self):
        """Muestra el diálogo de versión (Acerca de)."""
        QMessageBox.about(
            self,
            "Acerca de IPTV Viewer",
            f"<b>IPTV Viewer</b><br>"
            f"Versión {APP_VERSION}<br><br>"
            "Visor de IPTV con arquitectura hexagonal.<br>"
            "Motores VLC y mpv, EPG XMLTV y proxy Tor.<br><br>"
            "Licencia MIT — Copyright (c) 2026 killo3967",
        )

    def _show_shortcuts(self):
        """Muestra la lista de atajos de teclado."""
        QMessageBox.information(
            self,
            "Atajos de teclado",
            "<table>"
            "<tr><td><b>Alt+1</b></td><td>Modo Normal</td></tr>"
            "<tr><td><b>Alt+2</b></td><td>Modo Compacto</td></tr>"
            "<tr><td><b>Alt+3</b></td><td>Modo Video</td></tr>"
            "<tr><td><b>Alt+4</b> / <b>P</b></td><td>Ventana PIP</td></tr>"
            "<tr><td><b>F</b></td><td>Pantalla completa</td></tr>"
            "<tr><td><b>Esc</b></td><td>Salir de pantalla completa</td></tr>"
            "<tr><td><b>↑</b> / <b>↓</b></td><td>Canal anterior / siguiente</td></tr>"
            "<tr><td><b>Ctrl+G</b></td><td>Parrilla EPG</td></tr>"
            "</table>",
        )

    def _show_license(self):
        """Muestra el texto de la licencia MIT."""
        QMessageBox.information(self, "Licencia", MIT_LICENSE_TEXT)

    def _open_repository(self):
        """Abre el repositorio de GitHub en el navegador."""
        QDesktopServices.openUrl(QUrl("https://github.com/killo3967/IPTVViewer"))

    def _check_updates(self):
        """Comprueba si hay una versión más reciente en GitHub Releases."""
        try:
            resp = requests.get(
                "https://api.github.com/repos/killo3967/IPTVViewer/releases/latest",
                timeout=5,
            )
            if resp.status_code == 200:
                latest = resp.json().get("tag_name", "").lstrip("v")
                if _version_tuple(latest) > _version_tuple(APP_VERSION):
                    QMessageBox.information(
                        self, "Actualización",
                        f"Hay una versión más reciente: {latest} (actual: {APP_VERSION}).",
                    )
                else:
                    QMessageBox.information(
                        self, "Actualización",
                        f"Ya tienes la última versión ({APP_VERSION}).",
                    )
            else:
                QMessageBox.warning(self, "Actualización", "No se pudo comprobar la versión.")
        except Exception:
            QMessageBox.warning(self, "Actualización", "No se pudo comprobar la versión (¿sin conexión?).")

    def closeEvent(self, event):
        if self._fullscreen_active:
            self._exit_fullscreen()
        if self._pip_open:
            self._close_pip()
        self._playback_manager.stop_playback()
        super().closeEvent(event)
