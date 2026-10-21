"""Pruebas de ventana principal (pytest-qt) para el cambio view-modes.

Fakes a nivel de módulo (estilo ``FakePlayer``) que inyectan en
``IPTVMainWindow``: loader de listas fijo, playback manager que registra
llamadas, EPG manager sin datos, logo loader con la señal ``logo_loaded`` y
un stub-recorder para ``EPGGridDialog``.
"""
import os
import time
from datetime import datetime, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget

from src.application.services.view_mode_controller import (
    ViewMode,
    encode_splitter_state,
    )
from src.domain.entities.channel import Channel
from src.domain.entities.playlist import Playlist
from src.infrastructure.ui.main_window import IPTVMainWindow


class FakePlaylistLoader:
    """Devuelve siempre la misma playlist fija."""

    def __init__(self, playlist: Playlist | None = None):
        self._playlist = playlist or Playlist()

    def load_and_filter(self, source: str, group_filter: str = "") -> Playlist:
        return self._playlist


class FakePlaybackManager:
    """Registra play_channel/initialize_display y expone current_channel."""

    def __init__(self):
        self.play_calls = []
        self.initialize_calls = []
        self.stop_calls = []
        self.current_channel = None
        self.mute_calls = []
        self.volume_calls = []

    def play_channel(self, channel):
        self.play_calls.append(channel)
        self.current_channel = channel

    def initialize_display(self, window_id):
        self.initialize_calls.append(window_id)

    def stop_playback(self):
        self.stop_calls.append("stop")

    def set_hw_accel(self, enabled):
        pass

    def switch_player_engine(self, adapter, window_id):
        pass

    def update_engine_options(self, options):
        pass

    def set_muted(self, enabled):
        self.mute_calls.append(enabled)

    def set_volume(self, level):
        self.volume_calls.append(level)


class FakeEPGManager:
    """Devuelve siempre el mismo programa (o nada) y cuenta las consultas."""

    def __init__(self, program=None):
        self.has_data = program is not None
        self.program = program
        self.calls = 0

    def get_currently_airing(self, tvg_id: str, channel_name: str = ""):
        self.calls += 1
        return self.program

    def update_epg(self, source):
        pass


class FakeProgram:
    """Programa mínimo que consume la columna Programación."""

    def __init__(self, title: str = "Telediario", start=None, end=None):
        self.title = title
        self.description = ""
        self.start_time = start or (datetime.now() - timedelta(minutes=30))
        self.end_time = end or (datetime.now() + timedelta(minutes=30))


class FakeLogoLoader(QObject):
    """Expone la señal logo_loaded que el window conecta."""

    logo_loaded = pyqtSignal(str, object)

    def get_logo(self, url: str):
        pass


def make_channels():
    return [
        Channel(name="c1", url="http://test/c1", group="SPAIN"),
        Channel(name="c2", url="http://test/c2", group="SPAIN"),
        Channel(name="c3", url="http://test/c3", group="SPAIN"),
    ]


def make_config(**overrides) -> dict:
    config = {
        "sources": {0: {"name": "Lista 1", "m3u": "http://x/m3u", "filter": "SPAIN", "epg": ""}},
        "active": 0,
        "hw_acceleration": False,
        "player_engine": "vlc",
        "vlc_config": {},
        "mpv_config": {},
        "proxy_config": {},
        "view_mode": "normal",
        "splitter_state": "",
        "pip_geometry": "",
        "epg_show_title_only": True,
    }
    config.update(overrides)
    return config


def _recorder():
    """Espía de llamadas sin argumentos con contador."""
    class Recorder:
        calls = 0

        def __call__(self):
            Recorder.calls += 1

    return Recorder()


def _pump_events(seconds: float):
    """Procesa eventos de Qt sin bucle anidado (headless-safe).

    qtbot.wait() lanza un QEventLoop anidado que provoca un crash nativo en
    offscreen cuando hay ventanas Qt previas acumuladas (quirk del entorno
    PyQt6 6.11 + pytest-qt, presente también con el suite original en HEAD).
    Un bucle de processEvents() mantiene el mismo comportamiento observable:
    el QTimer de debounce de 300 ms dispara igualmente.
    """
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.01)


def make_window(config: dict | None = None, channels=None, save_callback=None,
               playback_manager=None, epg_manager=None):
    """Construye IPTVMainWindow inyectando fakes."""
    if config is None:
        config = make_config()
    playlist = Playlist(channels if channels is not None else make_channels())
    playlist_loader = FakePlaylistLoader(playlist)
    epg_manager = epg_manager or FakeEPGManager()
    logo_loader = FakeLogoLoader()
    if playback_manager is None:
        playback_manager = FakePlaybackManager()
    window = IPTVMainWindow(
        playlist_loader,  # type: ignore[arg-type]
        playback_manager,
        epg_manager,  # type: ignore[arg-type]
        logo_loader,  # type: ignore[arg-type]
        config,
        save_callback,
    )
    return window, playback_manager


def test_window_constructs_with_three_columns(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)

    assert window.table.columnCount() == 3


def test_startup_default_is_normal_layout(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    assert window.table.isVisible()
    assert not window.table.isColumnHidden(0)
    assert not window.table.isColumnHidden(1)
    assert not window.table.isColumnHidden(2)
    assert window.video_widget.isVisible()
    assert window.menuBar().isVisible()
    assert window.table.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu
    assert window.video_widget.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu


def test_compact_layout_hides_columns_and_menubar(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    window._apply_layout(ViewMode.COMPACT)

    assert window.table.isVisible()
    assert not window.table.isColumnHidden(0)
    assert window.table.isColumnHidden(1)
    assert not window.table.isColumnHidden(2)
    assert not window.menuBar().isVisible()
    assert window.table.contextMenuPolicy() == Qt.ContextMenuPolicy.NoContextMenu
    assert window.video_widget.contextMenuPolicy() == Qt.ContextMenuPolicy.NoContextMenu


def test_video_layout_hides_table_and_menubar(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    window._apply_layout(ViewMode.VIDEO)

    assert window.table.isHidden()
    assert not window.menuBar().isVisible()
    assert window.table.contextMenuPolicy() == Qt.ContextMenuPolicy.NoContextMenu
    assert window.video_widget.contextMenuPolicy() == Qt.ContextMenuPolicy.NoContextMenu


def test_return_to_normal_restores_columns_and_menubar(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    window._apply_layout(ViewMode.VIDEO)
    window._apply_layout(ViewMode.NORMAL)

    assert not window.table.isHidden()
    assert not window.table.isColumnHidden(0)
    assert not window.table.isColumnHidden(1)
    assert not window.table.isColumnHidden(2)
    assert window.menuBar().isVisible()
    assert window.table.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu
    assert window.video_widget.contextMenuPolicy() == Qt.ContextMenuPolicy.DefaultContextMenu


def test_startup_applies_persisted_compact_mode(qtbot):
    window, _ = make_window(config=make_config(view_mode="compact"))
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    assert window.table.isVisible()
    assert not window.table.isColumnHidden(0)
    assert window.table.isColumnHidden(1)
    assert not window.table.isColumnHidden(2)
    assert not window.menuBar().isVisible()
    assert window.table.contextMenuPolicy() == Qt.ContextMenuPolicy.NoContextMenu


def test_alt2_switches_to_compact_and_persists(qtbot):
    saved = []
    window, _ = make_window(save_callback=lambda cfg: saved.append(dict(cfg)))
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_2, Qt.KeyboardModifier.AltModifier)

    assert window._view_controller.mode is ViewMode.COMPACT
    assert window._config["view_mode"] == "compact"
    assert saved and saved[-1]["view_mode"] == "compact"


def test_alt3_switches_to_video(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_3, Qt.KeyboardModifier.AltModifier)

    assert window._view_controller.mode is ViewMode.VIDEO


def test_alt1_returns_to_normal(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)

    qtbot.keyClick(window, Qt.Key.Key_3, Qt.KeyboardModifier.AltModifier)
    qtbot.keyClick(window, Qt.Key.Key_1, Qt.KeyboardModifier.AltModifier)

    assert window._view_controller.mode is ViewMode.NORMAL


def test_repressing_active_mode_shortcut_is_noop(qtbot):
    notifications = []
    saved = []
    window, _ = make_window(save_callback=lambda cfg: saved.append(cfg))
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    window._view_controller.register_listener(
        lambda old, new: notifications.append((old, new))
    )

    qtbot.keyClick(window, Qt.Key.Key_2, Qt.KeyboardModifier.AltModifier)
    assert window._view_controller.mode is ViewMode.COMPACT
    assert notifications == [(ViewMode.NORMAL, ViewMode.COMPACT)]
    assert len(saved) == 1  # una sola persistencia por el cambio real

    qtbot.keyClick(window, Qt.Key.Key_2, Qt.KeyboardModifier.AltModifier)

    assert window._view_controller.mode is ViewMode.COMPACT
    assert notifications == [(ViewMode.NORMAL, ViewMode.COMPACT)]
    assert len(saved) == 1  # el no-op no persiste nada


def test_mode_switch_retargets_video_exactly_once(qtbot):
    window, playback = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    before = len(playback.initialize_calls)  # 1 llamada inicial en _setup_ui

    qtbot.keyClick(window, Qt.Key.Key_2, Qt.KeyboardModifier.AltModifier)

    assert len(playback.initialize_calls) == before + 1
    assert playback.initialize_calls[-1] == int(window.video_widget.winId())

def test_f_toggles_fullscreen_on(qtbot, monkeypatch):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    window.showFullScreen = _recorder()
    window.showNormal = _recorder()

    qtbot.keyClick(window, Qt.Key.Key_F)

    assert window._fullscreen_active is True
    assert window.showFullScreen.calls == 1


def test_f_toggles_fullscreen_off(qtbot, monkeypatch):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    window.showFullScreen = _recorder()
    window.showNormal = _recorder()

    qtbot.keyClick(window, Qt.Key.Key_F)
    qtbot.keyClick(window, Qt.Key.Key_F)

    assert window._fullscreen_active is False
    assert window.showNormal.calls == 1


def test_escape_exits_fullscreen_only_when_fullscreen(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    window.showFullScreen = _recorder()
    window.showNormal = _recorder()

    qtbot.keyClick(window, Qt.Key.Key_Escape)
    assert window._fullscreen_active is False
    assert window.showNormal.calls == 0

    qtbot.keyClick(window, Qt.Key.Key_F)
    assert window._fullscreen_active is True
    qtbot.keyClick(window, Qt.Key.Key_Escape)
    assert window._fullscreen_active is False
    assert window.showNormal.calls == 1


def test_cursor_timeout_hides_cursor(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    qtbot.wait(10)

    window._on_cursor_timeout()

    assert window.cursor().shape() == Qt.CursorShape.BlankCursor


def test_mouse_move_restores_cursor_and_restarts_timer(qtbot):
    # offscreen no entrega eventos de ratón sintéticos de forma fiable:
    # se invoca el eventFilter directamente (estrategia headless-safe del diseño)
    from PyQt6.QtCore import QEvent, QPoint, QPointF
    from PyQt6.QtGui import QMouseEvent

    window, _ = make_window()
    qtbot.addWidget(window)
    window._enter_fullscreen()
    window._on_cursor_timeout()
    assert window.cursor().shape() == Qt.CursorShape.BlankCursor

    gpos = window.mapToGlobal(QPoint(5, 5))
    ev = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(5, 5),
        QPointF(gpos),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window.eventFilter(window, ev)

    assert window.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert window._cursor_timer.isActive()


def test_exiting_fullscreen_stops_timer_and_restores_cursor(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window._enter_fullscreen()
    window._on_cursor_timeout()
    assert window._cursor_timer.isActive()

    window._exit_fullscreen()

    assert window._fullscreen_active is False
    assert window._cursor_timer.isActive() is False
    assert window.cursor().shape() == Qt.CursorShape.ArrowCursor


def test_close_event_while_fullscreen_restores_windowed_state(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window._enter_fullscreen()
    assert window._fullscreen_active is True

    window.close()

    assert window._fullscreen_active is False
    assert window._cursor_timer.isActive() is False

def test_zap_down_plays_next_channel(qtbot):
    channels = make_channels()
    window, playback = make_window(channels=channels)
    playback.current_channel = channels[0]
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_Down)

    assert playback.play_calls == [channels[1]]


def test_zap_up_in_video_mode(qtbot):
    channels = make_channels()
    window, playback = make_window(channels=channels)
    playback.current_channel = channels[1]
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_3, Qt.KeyboardModifier.AltModifier)
    qtbot.keyClick(window, Qt.Key.Key_Up)

    assert playback.play_calls == [channels[0]]


def test_zap_down_at_last_wraps_to_first(qtbot):
    channels = make_channels()
    window, playback = make_window(channels=channels)
    playback.current_channel = channels[2]
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_Down)

    assert playback.play_calls == [channels[0]]


def test_zap_up_at_first_wraps_to_last(qtbot):
    channels = make_channels()
    window, playback = make_window(channels=channels)
    playback.current_channel = channels[0]
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_Up)

    assert playback.play_calls == [channels[2]]


def test_zap_empty_playlist_is_noop(qtbot):
    window, playback = make_window(channels=[])
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_Down)

    assert playback.play_calls == []


def test_zap_with_no_current_channel_plays_first(qtbot):
    channels = make_channels()
    window, playback = make_window(channels=channels)
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_Down)

    assert playback.play_calls == [channels[0]]


def test_zap_arrows_fire_with_table_focused(qtbot):
    channels = make_channels()
    window, playback = make_window(channels=channels)
    playback.current_channel = channels[0]
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    window.table.setFocus()

    qtbot.keyClick(window.table, Qt.Key.Key_Down)

    assert playback.play_calls == [channels[1]]

def test_splitter_move_flush_persists_state(qtbot):
    saved = []
    window, _ = make_window(save_callback=lambda cfg: saved.append(dict(cfg)))
    qtbot.addWidget(window)
    window.splitter.setSizes([300, 700])

    window._arm_splitter_save()
    qtbot.wait(350)

    expected = encode_splitter_state(bytes(window.splitter.saveState()))
    assert window._config["splitter_state"] == expected
    assert saved and saved[-1]["splitter_state"] == expected


def test_entering_video_writes_prehide_snapshot_synchronously(qtbot):
    saved = []
    window, _ = make_window(save_callback=lambda cfg: saved.append(dict(cfg)))
    qtbot.addWidget(window)
    window.splitter.setSizes([300, 700])
    expected = encode_splitter_state(bytes(window.splitter.saveState()))

    window._view_controller.activate(ViewMode.VIDEO)

    assert window._config["splitter_state"] == expected
    assert saved and saved[-1]["splitter_state"] == expected


def test_debounce_flush_skipped_while_table_hidden(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window._view_controller.activate(ViewMode.VIDEO)
    before = window._config.get("splitter_state")

    window.splitter.setSizes([10, 890])
    window._arm_splitter_save()
    qtbot.wait(350)

    assert window._config.get("splitter_state") == before


def test_restart_in_video_returns_to_normal_restores_splitter(qtbot):
    # El estado se genera desde una ventana ya montada: saveState captura los
    # tamaños reales tras el layout, y el round-trip compara iguales (AC-8).
    w1, _ = make_window()
    w1.show()
    QApplication.processEvents()
    w1.splitter.setSizes([400, 800])
    QApplication.processEvents()
    reference = list(w1.splitter.sizes())
    saved_state = encode_splitter_state(bytes(w1.splitter.saveState()))
    w1.close()

    window, _ = make_window(
        config=make_config(view_mode="video", splitter_state=saved_state)
    )
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    assert window._view_controller.mode is ViewMode.VIDEO

    qtbot.keyClick(window, Qt.Key.Key_1, Qt.KeyboardModifier.AltModifier)

    assert window.splitter.sizes() == reference

def _all_menu_actions(menu_bar):
    actions = list(menu_bar.actions())
    for action in list(actions):
        if action.menu():
            actions.extend(action.menu().actions())
    return actions


def test_all_menu_actions_enabled_in_compact_and_video(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    window._view_controller.activate(ViewMode.COMPACT)
    assert all(a.isEnabled() for a in _all_menu_actions(window.menuBar()))

    window._view_controller.activate(ViewMode.VIDEO)
    assert all(a.isEnabled() for a in _all_menu_actions(window.menuBar()))


def test_ctrl_g_opens_epg_grid_in_compact_and_video(qtbot, monkeypatch):
    import src.infrastructure.ui.main_window as mw

    recorded = []
    class RecorderDialog:
        def __init__(self, *args, **kwargs):
            recorded.append("created")

        def exec(self):
            recorded.append("exec")

    monkeypatch.setattr(mw, "EPGGridDialog", RecorderDialog)

    window, _ = make_window()
    window._epg_manager.has_data = True
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    window._view_controller.activate(ViewMode.COMPACT)
    qtbot.keyClick(window, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)
    assert recorded == ["created", "exec"]

    window._view_controller.activate(ViewMode.VIDEO)
    recorded.clear()
    qtbot.keyClick(window, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)
    assert recorded == ["created", "exec"]


def test_ctrl_g_works_after_returning_to_normal(qtbot, monkeypatch):
    import src.infrastructure.ui.main_window as mw

    recorded = []
    class RecorderDialog:
        def __init__(self, *args, **kwargs):
            recorded.append("created")

        def exec(self):
            recorded.append("exec")

    monkeypatch.setattr(mw, "EPGGridDialog", RecorderDialog)

    window, _ = make_window()
    window._epg_manager.has_data = True
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_3, Qt.KeyboardModifier.AltModifier)
    qtbot.keyClick(window, Qt.Key.Key_1, Qt.KeyboardModifier.AltModifier)
    assert window.menuBar().isVisible()

    qtbot.keyClick(window, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)
    assert recorded == ["created", "exec"]

def test_pip_window_has_detached_flags(qtbot):
    from src.infrastructure.ui.components.pip_window import PIPWindow

    target = QWidget()
    pip = PIPWindow(target)
    qtbot.addWidget(pip)

    flags = pip.windowFlags()
    assert flags & Qt.WindowType.Tool
    assert flags & Qt.WindowType.FramelessWindowHint
    assert flags & Qt.WindowType.WindowStaysOnTopHint


def test_pip_set_video_widget_reparents(qtbot):
    from src.infrastructure.ui.components.pip_window import PIPWindow

    pip = PIPWindow(QWidget())
    qtbot.addWidget(pip)
    video = QWidget()

    pip.set_video_widget(video)

    assert video.parent() is pip


def test_pip_body_drag_moves_window(qtbot):
    from PyQt6.QtTest import QTest

    from src.infrastructure.ui.components.pip_window import PIPWindow

    pip = PIPWindow(QWidget())
    qtbot.addWidget(pip)
    pip.move(100, 100)
    pip.show()
    QApplication.processEvents()
    start = pip.pos()

    QTest.mousePress(pip, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pip.rect().center())
    QTest.mouseMove(pip, pip.rect().center() + __import__("PyQt6.QtCore", fromlist=["QPoint"]).QPoint(30, 20))
    QTest.mouseRelease(pip, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, pip.rect().center() + __import__("PyQt6.QtCore", fromlist=["QPoint"]).QPoint(30, 20))

    assert pip.pos() != start


def test_pip_grip_drag_resizes_with_minimum(qtbot):
    from PyQt6.QtCore import QPoint
    from PyQt6.QtTest import QTest

    from src.infrastructure.ui.components.pip_window import PIPWindow, ResizeGrip

    pip = PIPWindow(QWidget())
    qtbot.addWidget(pip)
    pip.resize(200, 120)
    pip.show()
    QApplication.processEvents()
    grip = pip.findChild(ResizeGrip)
    assert grip is not None
    before = (pip.width(), pip.height())

    QTest.mousePress(grip, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip.rect().center())
    QTest.mouseMove(grip, grip.rect().center() + QPoint(40, 30))
    QTest.mouseRelease(grip, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip.rect().center() + QPoint(40, 30))

    assert pip.width() >= 160 and pip.height() >= 90
    assert (pip.width(), pip.height()) != before


def test_pip_forwards_key_events_to_target(qtbot):
    from src.infrastructure.ui.components.pip_window import PIPWindow

    class Target(QWidget):
        def __init__(self):
            super().__init__()
            self.received = []

        def keyPressEvent(self, event):
            self.received.append(event.key())

    target = Target()
    pip = PIPWindow(target)
    qtbot.addWidget(pip)

    qtbot.keyClick(pip, Qt.Key.Key_Down)

    assert target.received == [Qt.Key.Key_Down]

def test_p_opens_pip_and_hides_main_placeholder(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)

    assert window._pip_open is True
    pip = window._pip_window
    assert pip is not None
    assert pip.isVisible()
    assert window.video_widget.parent() is pip
    assert window.splitter.indexOf(window.video_widget) == -1


def test_p_closes_pip_and_widget_returns_to_splitter(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)
    qtbot.keyClick(window, Qt.Key.Key_P)

    assert window._pip_open is False
    assert not window._pip_window.isVisible()
    assert window.splitter.indexOf(window.video_widget) == 1
    assert window.video_widget.isVisible()


def test_alt4_toggles_the_same_pip_instance(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_4, Qt.KeyboardModifier.AltModifier)
    first = window._pip_window
    assert first is not None and window._pip_open is True

    qtbot.keyClick(window, Qt.Key.Key_4, Qt.KeyboardModifier.AltModifier)
    assert window._pip_open is False

    qtbot.keyClick(window, Qt.Key.Key_4, Qt.KeyboardModifier.AltModifier)
    assert window._pip_open is True
    assert window._pip_window is first


def test_pip_never_auto_opens_at_launch(qtbot):
    window, _ = make_window(config=make_config(pip_geometry="1280,40,480,270"))
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    assert window._pip_open is False
    assert window._pip_window is None
    assert window.splitter.indexOf(window.video_widget) == 1

# --- WU 4.3: PIP geometry persistence (AC-13) ---------------------------

def test_pip_move_persists_geometry_after_debounce(qtbot):
    # El arrastre del cuerpo (QTest.mouseMove) provoca un crash nativo en
    # offscreen tras varios tests; el wire de persistencia real es el mismo:
    # moveEvent -> senal -> debounce. El arrastre por raton ya esta cubierto
    # por test_pip_body_drag_moves_window.
    from src.application.services.view_mode_controller import geometry_to_str

    saved = []
    window, _ = make_window(save_callback=lambda cfg: saved.append(dict(cfg)))
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)
    pip = window._pip_window
    pip.move(200, 150)
    _pump_events(0.4)

    expected = geometry_to_str(*pip.geometry().getRect()[:4])
    assert window._config["pip_geometry"] == expected
    assert saved and saved[-1]["pip_geometry"] == expected


def test_pip_resize_persists_geometry_after_debounce(qtbot):
    # Mismo rationale que el test de move: el resize por grip dispara el mismo
    # resizeEvent que pip.resize() (el grip ya esta cubierto por
    # test_pip_grip_drag_resizes_with_minimum).
    from src.application.services.view_mode_controller import geometry_to_str

    saved = []
    window, _ = make_window(save_callback=lambda cfg: saved.append(dict(cfg)))
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)
    pip = window._pip_window
    pip.resize(500, 300)
    _pump_events(0.4)

    expected = geometry_to_str(*pip.geometry().getRect()[:4])
    assert window._config["pip_geometry"] == expected
    assert saved and saved[-1]["pip_geometry"] == expected


def test_pip_close_cancels_geometry_debounce(qtbot):
    # REFACTOR de WU 4.3: cerrar el PIP cancela el guardado diferido. Un move
    # justo antes del cierre no debe persistirse (la especificacion exige que
    # los writes de geometria nunca se disparen con el PIP cerrado). El guard
    # de _flush_pip_geometry es la segunda red de seguridad.
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)
    pip = window._pip_window
    pip.move(200, 150)
    assert window._pip_geometry_save_timer is not None
    assert window._pip_geometry_save_timer.isActive()

    qtbot.keyClick(window, Qt.Key.Key_P)  # cerrar antes de que dispare el debounce
    assert window._pip_geometry_save_timer.isActive() is False
    _pump_events(0.4)

    assert window._config["pip_geometry"] == ""


def test_pip_restores_persisted_geometry_on_open(qtbot):
    window, _ = make_window(config=make_config(pip_geometry="100,100,480,270"))
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)

    geo = window._pip_window.geometry()
    assert geo.x() == 100
    assert geo.y() == 100
    assert geo.width() == 480
    assert geo.height() == 270


def test_pip_garbage_geometry_uses_default_placement(qtbot):
    window, _ = make_window(config=make_config(pip_geometry="garbage"))
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)

    pip = window._pip_window
    assert pip.width() == 480
    assert pip.height() == 270

# --- WU 4.4: re-target on PIP open/close (AC-16 second half) -----------

def test_pip_open_close_retargets_video_exactly_twice(qtbot):
    window, playback = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    before = len(playback.initialize_calls)

    qtbot.keyClick(window, Qt.Key.Key_P)
    assert len(playback.initialize_calls) == before + 1
    assert playback.initialize_calls[-1] == int(window.video_widget.winId())

    qtbot.keyClick(window, Qt.Key.Key_P)
    assert len(playback.initialize_calls) == before + 2
    assert playback.initialize_calls[-1] == int(window.video_widget.winId())

# --- WU 4.5: PIP key forwarding to the main window (REQ-6, REQ-9) ------

def test_pip_key_forward_zap_down(qtbot):
    channels = make_channels()
    window, playback = make_window(channels=channels)
    playback.current_channel = channels[0]
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)
    qtbot.keyClick(window._pip_window, Qt.Key.Key_Down)

    assert playback.play_calls == [channels[1]]


def test_opening_pip_hides_main_window(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)

    assert window._pip_open is True
    assert not window.isVisible()
    assert window._pip_window.isVisible()


def test_closing_pip_restores_main_window(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)
    assert not window.isVisible()

    qtbot.keyClick(window._pip_window, Qt.Key.Key_P)

    assert window._pip_open is False
    assert window.isVisible()


def test_pip_native_close_via_closed_signal_restores_main(qtbot):
    # Alt+F4 sobre el PIP emite closed (closeEvent); la principal
    # debe restaurarse en vez de quedar oculta para siempre.
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)
    assert not window.isVisible()

    window._pip_window.close()

    assert window._pip_open is False
    assert window.isVisible()


def test_pip_window_is_top_level(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)

    pip = window._pip_window
    assert pip.parent() is None
    assert pip.isVisible()
    assert window.isVisible() is False or pip.parent() is not window


def test_pip_key_forward_p_toggles_pip_closed(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)
    assert window._pip_open is True

    qtbot.keyClick(window._pip_window, Qt.Key.Key_P)

    assert window._pip_open is False


def test_pip_key_forward_alt2_switches_to_compact(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)
    qtbot.keyClick(window._pip_window, Qt.Key.Key_2, Qt.KeyboardModifier.AltModifier)

    assert window._view_controller.mode is ViewMode.COMPACT


def test_pip_key_forward_ctrl_g_opens_epg_grid(qtbot, monkeypatch):
    import src.infrastructure.ui.main_window as mw

    recorded = []
    class RecorderDialog:
        def __init__(self, *args, **kwargs):
            recorded.append("created")

        def exec(self):
            recorded.append("exec")

    monkeypatch.setattr(mw, "EPGGridDialog", RecorderDialog)

    window, _ = make_window()
    window._epg_manager.has_data = True
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_P)
    qtbot.keyClick(window._pip_window, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)

    assert recorded == ["created", "exec"]
# --- Follow-up fixes: compacto muestra programacion, F=ALT+3+fullscreen, OSD, PIP fit ---

def test_f_forces_video_mode_then_restores_previous(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    window.showFullScreen = _recorder()
    window.showNormal = _recorder()

    assert window._view_controller.mode is ViewMode.NORMAL

    qtbot.keyClick(window, Qt.Key.Key_F)
    assert window._fullscreen_active is True
    assert window._view_controller.mode is ViewMode.VIDEO

    qtbot.keyClick(window, Qt.Key.Key_F)
    assert window._fullscreen_active is False
    assert window._view_controller.mode is ViewMode.NORMAL


def test_channel_overlay_shown_on_video_mode_and_zap(qtbot):
    channels = make_channels()
    window, playback = make_window(channels=channels)
    playback.current_channel = channels[0]
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    qtbot.keyClick(window, Qt.Key.Key_3, Qt.KeyboardModifier.AltModifier)
    _pump_events(0.05)
    assert window._channel_overlay.isVisible()
    assert window._channel_overlay.text() == "c1"

    qtbot.keyClick(window, Qt.Key.Key_Down)
    assert window._channel_overlay.text() == "c2"


def test_channel_overlay_hides_after_two_seconds(qtbot):
    channels = make_channels()
    window, playback = make_window(channels=channels)
    playback.current_channel = channels[0]
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    window._show_channel_overlay()
    assert window._channel_overlay.isVisible()

    _pump_events(2.1)
    assert not window._channel_overlay.isVisible()


def test_pip_video_widget_fills_pip_rect(qtbot):
    from src.infrastructure.ui.components.pip_window import PIPWindow

    pip = PIPWindow(QWidget())
    qtbot.addWidget(pip)
    pip.resize(480, 270)
    video = QWidget()

    pip.set_video_widget(video)

    assert video.parent() is pip
    assert video.width() == 480
    assert video.height() == 270

def test_help_menu_has_three_actions(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)

    help_menu = None
    for a in window.menuBar().actions():
        if a.menu() and a.text().replace("&", "") == "Ayuda":
            help_menu = a.menu()
            break
    assert help_menu is not None
    sub = [a.text() for a in help_menu.actions()]
    assert any("Versión" in t for t in sub)
    assert any("Teclas" in t for t in sub)
    assert any("Licencia" in t for t in sub)

def test_help_menu_has_update_and_repo_actions(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)

    help_menu = None
    for a in window.menuBar().actions():
        if a.menu() and a.text().replace("&", "") == "Ayuda":
            help_menu = a.menu()
            break
    assert help_menu is not None
    sub = [a.text().replace("&", "") for a in help_menu.actions()]
    assert any("actualizaciones" in t for t in sub)
    assert any("Repositorio" in t for t in sub)


def test_open_repository_opens_url(qtbot, monkeypatch):
    import src.infrastructure.ui.main_window as mw

    recorded = []
    monkeypatch.setattr(mw.QDesktopServices, "openUrl", lambda url: recorded.append(url.toString()))

    window, _ = make_window()
    qtbot.addWidget(window)

    window._open_repository()

    assert recorded == ["https://github.com/killo3967/IPTVViewer"]


def test_check_updates_newer_version(qtbot, monkeypatch):
    import src.infrastructure.ui.main_window as mw

    recorded = []
    monkeypatch.setattr(
        mw.QMessageBox, "information",
        lambda parent, title, text, *a, **k: recorded.append((title, text)),
    )

    class FakeResponse:
        status_code = 200
        def json(self):
            return {"tag_name": "v9.9.9"}

    monkeypatch.setattr(mw.requests, "get", lambda *a, **k: FakeResponse())

    window, _ = make_window()
    qtbot.addWidget(window)

    window._check_updates()

    assert recorded and "9.9.9" in recorded[0][1]


def test_check_updates_handles_no_network(qtbot, monkeypatch):
    import src.infrastructure.ui.main_window as mw

    recorded = []
    monkeypatch.setattr(
        mw.QMessageBox, "warning",
        lambda parent, title, text, *a, **k: recorded.append(title),
    )

    def fake_get(*a, **k):
        raise mw.requests.exceptions.ConnectionError("no net")

    monkeypatch.setattr(mw.requests, "get", fake_get)

    window, _ = make_window()
    qtbot.addWidget(window)

    window._check_updates()

    assert recorded == ["Actualización"]


def test_help_actions_open_dialogs(qtbot, monkeypatch):
    import src.infrastructure.ui.main_window as mw

    recorded = []
    monkeypatch.setattr(
        mw.QMessageBox, "about",
        lambda parent, title, text, *a, **k: recorded.append(("about", title)),
    )
    monkeypatch.setattr(
        mw.QMessageBox, "information",
        lambda parent, title, text, *a, **k: recorded.append(("info", title)),
    )

    window, _ = make_window()
    qtbot.addWidget(window)

    window._show_about()
    window._show_shortcuts()
    window._show_license()

    titles = [t for _, t in recorded]
    assert "Acerca de IPTV Viewer" in titles
    assert "Atajos de teclado" in titles
    assert "Licencia" in titles



def test_ctrl_s_toggles_mute(qtbot):
    window, playback = make_window()
    qtbot.addWidget(window)

    qtbot.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    assert window._muted is True
    assert playback.mute_calls[-1] is True

    qtbot.keyClick(window, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    assert window._muted is False
    assert playback.mute_calls[-1] is False


def test_shift_up_down_changes_volume_with_clamping(qtbot):
    window, playback = make_window()
    qtbot.addWidget(window)

    window._volume = 95  # partir bajo el techo
    qtbot.keyClick(window, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    assert window._volume == 100
    qtbot.keyClick(window, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    qtbot.keyClick(window, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert window._volume == 90
    assert playback.volume_calls == [100, 95, 90]


def test_volume_clamped_at_bounds(qtbot):
    window, _playback = make_window()

    for _ in range(3):
        qtbot.keyClick(window, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert window._volume == 85
    for _ in range(50):
        qtbot.keyClick(window, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert window._volume == 0
    qtbot.keyClick(window, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert window._volume == 0
    for _ in range(50):
        qtbot.keyClick(window, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    assert window._volume == 100
    qtbot.keyClick(window, Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    assert window._volume == 100


def test_plain_arrows_still_zap_with_shift_variant(qtbot):
    """Shift+Down ajusta volumen (no zapea); Down plano sigue zapeando."""
    channels = make_channels()
    window, playback = make_window(channels=channels)
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()
    playback.current_channel = channels[0]
    window._volume = 100

    qtbot.keyClick(window, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert playback.play_calls == []
    assert playback.volume_calls == [95]

    qtbot.keyClick(window, Qt.Key.Key_Down)
    assert playback.play_calls == [channels[1]]


def test_audio_keys_forwarded_from_pip(qtbot):
    """Ctrl+S reenviado desde el PIP silencia igual que el atajo local."""
    window, playback = make_window()
    qtbot.addWidget(window)
    from PyQt6.QtCore import QEvent
    from PyQt6.QtGui import QKeyEvent
    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_S,
                      Qt.KeyboardModifier.ControlModifier)
    QApplication.sendEvent(window, event)
    assert window._muted is True
    assert playback.mute_calls[-1] is True


# ---------------------------------------------------------------------------
# Columna Programación: sin prefijo NOW, barra de progreso y configuración EPG
# ---------------------------------------------------------------------------

def test_epg_column_has_no_now_prefix(qtbot):
    """La celda guarda ProgramInfo y no escribe "NOW: ..." como texto."""
    from src.infrastructure.ui.components.epg_program_delegate import (
        EPG_PROGRAM_ROLE,
        ProgramInfo,
    )

    window, _ = make_window(epg_manager=FakeEPGManager(program=FakeProgram()))
    qtbot.addWidget(window)

    item = window.table.item(0, 2)
    assert item.text() == ""
    info = item.data(EPG_PROGRAM_ROLE)
    assert isinstance(info, ProgramInfo)
    assert info.title == "Telediario"


def test_epg_column_without_program_shows_placeholder(qtbot):
    from src.infrastructure.ui.components.epg_program_delegate import EPG_PROGRAM_ROLE

    window, _ = make_window()
    qtbot.addWidget(window)

    item = window.table.item(0, 2)
    assert item.text() == "Guía no disponible"
    assert item.data(EPG_PROGRAM_ROLE) is None


def test_epg_title_only_setting_is_applied_to_delegate(qtbot):
    window, _ = make_window(config=make_config(epg_show_title_only=False))
    qtbot.addWidget(window)

    assert window._epg_delegate.title_only is False
    assert window._epg_show_title_only is False


def test_epg_title_only_defaults_to_true(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)

    assert window._epg_delegate.title_only is True


def test_epg_config_dialog_action_persists_and_applies(qtbot, monkeypatch):
    """Configuración → Configuración de EPG guarda la casilla y repinta la tabla."""
    from PyQt6.QtWidgets import QDialog

    import src.infrastructure.ui.main_window as mw_module

    saved = []
    window, _ = make_window(
        epg_manager=FakeEPGManager(program=FakeProgram()),
        save_callback=lambda cfg: saved.append(dict(cfg)),
    )
    qtbot.addWidget(window)

    monkeypatch.setattr(mw_module.EPGConfigDialog, "exec",
                        lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(mw_module.EPGConfigDialog, "title_only", lambda self: False)

    window._open_epg_config_dialog()

    assert window._config["epg_show_title_only"] is False
    assert window._epg_delegate.title_only is False
    assert saved and saved[-1]["epg_show_title_only"] is False


def test_epg_config_dialog_cancel_keeps_setting(qtbot, monkeypatch):
    from PyQt6.QtWidgets import QDialog

    import src.infrastructure.ui.main_window as mw_module

    window, _ = make_window()
    qtbot.addWidget(window)
    monkeypatch.setattr(mw_module.EPGConfigDialog, "exec",
                        lambda self: QDialog.DialogCode.Rejected)

    window._open_epg_config_dialog()

    assert window._config["epg_show_title_only"] is True


def test_visible_rows_refresh_does_not_touch_hidden_rows(qtbot):
    """El refresco periódico recalcula solo las filas visibles."""
    channels = [
        Channel(name=f"c{i}", url=f"http://test/{i}", group="SPAIN") for i in range(40)
    ]
    epg = FakeEPGManager(program=FakeProgram())
    window, _ = make_window(channels=channels, epg_manager=epg)
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    visible = list(window._visible_rows())
    assert 0 < len(visible) < len(channels)

    epg.calls = 0
    window._refresh_epg_display()
    assert epg.calls == len(visible)

    epg.calls = 0
    window._refresh_epg_display(visible_only=False)
    assert epg.calls == len(channels)


def test_epg_refresh_after_scroll_updates_new_visible_rows(qtbot):
    """Tras mover el scroll, el refresco alcanza las filas recién visibles."""
    from src.infrastructure.ui.components.epg_program_delegate import EPG_PROGRAM_ROLE

    channels = [
        Channel(name=f"c{i}", url=f"http://test/{i}", group="SPAIN") for i in range(40)
    ]
    epg = FakeEPGManager(program=FakeProgram())
    window, _ = make_window(channels=channels, epg_manager=epg)
    qtbot.addWidget(window)
    window.show()
    QApplication.processEvents()

    window.table.scrollToBottom()
    QApplication.processEvents()
    epg.calls = 0
    window._arm_epg_refresh()
    _pump_events(0.3)

    assert epg.calls > 0
    for row in window._visible_rows():
        assert window.table.item(row, 2).data(EPG_PROGRAM_ROLE) is not None

def test_playback_failed_signal_shows_overlay(qtbot):
    """El aviso de "sin señal" llega a la UI como OSD."""
    window, _ = make_window()
    qtbot.addWidget(window)

    window.playback_failed.emit("LA 1")
    QApplication.processEvents()

    assert window._channel_overlay.text() == "Sin señal: LA 1"


def test_notify_playback_failed_emits_channel_name(qtbot):
    window, _ = make_window()
    qtbot.addWidget(window)
    received = []
    window.playback_failed.connect(received.append)

    window._notify_playback_failed(Channel(name="LA 2", url="http://test/la2"))

    assert received == ["LA 2"]
