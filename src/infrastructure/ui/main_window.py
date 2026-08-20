import logging
from PyQt6.QtWidgets import (
    QMainWindow, QTableWidget, QTableWidgetItem, QMessageBox,
    QSplitter, QWidget, QVBoxLayout, QHeaderView,
    QMenuBar, QFileDialog, QInputDialog, QMenu,
    QDialog, QFormLayout, QLineEdit, QDialogButtonBox
)
from PyQt6.QtGui import QColor, QPixmap, QAction, QActionGroup, QIcon
from PyQt6.QtCore import Qt, QTimer, QSize

from src.application.services.playlist_loader import PlaylistLoader
from src.application.services.playback_manager import PlaybackManager
from src.application.services.epg_manager import EPGManager
from src.infrastructure.adapters.qt_logo_loader_adapter import QtLogoLoaderAdapter
from src.infrastructure.ui.components.epg_grid import EPGGridDialog
from src.domain.entities.channel import Channel
from src.domain.entities.playlist import Playlist


class SourceEditorDialog(QDialog):
    """Diálogo para añadir o editar una fuente M3U con nombre."""

    def __init__(self, parent=None, source: dict = None):
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
        self._epg_manager = epg_manager
        self._logo_loader = logo_loader
        self._config = config
        self._save_callback = save_callback
        self._last_playlist = Playlist() # Caché de la última lista cargada

        # UI Initialization
        self.setWindowTitle("IPTV Viewer – Arquitectura Hexagonal")
        self.resize(1200, 650)
        
        # Cargar icono de la aplicación
        import os, sys
        if getattr(sys, 'frozen', False):
            base = sys._MEIPASS
        else:
            base = os.path.join(os.path.dirname(__file__), '../../..')
        icon_path = os.path.join(base, 'resources', 'logo.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
            
        self._setup_ui()
        self._create_menus()
        
        # Timer para actualizar EPG cada minuto
        self._epg_timer = QTimer(self)
        self._epg_timer.timeout.connect(self._refresh_epg_display)
        self._epg_timer.start(60000) # 60 segundos
        
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
        
        # Tabla
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Canal", "Logo", "Programación"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 120)
        self.table.verticalHeader().setDefaultSectionSize(90)
        self.table.setIconSize(self.table.iconSize().expandedTo(QSize(100, 75)))
        self.table.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self.table)
        
        # Video
        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background-color: black;")
        splitter.addWidget(self.video_widget)
        
        # Inicializar el visor de video en el reproductor
        self._playback_manager.initialize_display(int(self.video_widget.winId()))

    def _create_menus(self):
        """Crea el sistema de menús."""
        menubar = self.menuBar()
        
        # Menú Archivo
        file_menu = menubar.addMenu("&Archivo")

        view_epg_action = file_menu.addAction("Ver &Parrilla EPG...")
        view_epg_action.setShortcut("Ctrl+G")
        view_epg_action.triggered.connect(self._show_epg_grid)

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

        try:
            playlist = self._playlist_loader.load_and_filter(source, group)
            self._last_playlist = playlist
            self._fill_table(playlist)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar la lista: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar la lista: {e}")

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
        from src.infrastructure.adapters.vlc_player_adapter import VlcPlayerAdapter
        from src.infrastructure.adapters.mpv_player_adapter import MpvPlayerAdapter
        
        current_engine = self._config.get('player_engine', 'vlc')
        vlc_cfg = self._config.get('vlc_config', {})
        mpv_cfg = self._config.get('mpv_config', {})
            
        dialog = EngineConfigDialog(current_engine, vlc_cfg, mpv_cfg, self)
        
        if dialog.exec():
            new_engine, new_vlc_cfg, new_mpv_cfg = dialog.get_results()
            proxy_cfg = self._config.get('proxy_config', {}) # Usar proxy actual
            
            # Persistir cambios en el objeto de config
            self._config['player_engine'] = new_engine
            self._config['vlc_config'] = new_vlc_cfg
            self._config['mpv_config'] = new_mpv_cfg
            
            # Sincronizar ajuste de hardware según motor activo
            hw_enabled = new_mpv_cfg.get('hw_acceleration') if new_engine == 'mpv' else new_vlc_cfg.get('hw_acceleration')
            self._config['hw_acceleration'] = hw_enabled
            self.hw_on_action.setChecked(hw_enabled)
            self.hw_off_action.setChecked(not hw_enabled)

            # ¿Ha cambiado el motor?
            if new_engine != current_engine:
                logging.info(f"Cambiando motor de {current_engine} a {new_engine}")
                from src.infrastructure.utils.proxy import get_standardized_proxy_config
                std_proxy = get_standardized_proxy_config(proxy_cfg)
                
                if new_engine == 'mpv':
                    new_adapter = MpvPlayerAdapter(new_mpv_cfg, std_proxy)
                else:
                    new_adapter = VlcPlayerAdapter(new_vlc_cfg, std_proxy)
                
                self._playback_manager.switch_player_engine(new_adapter, int(self.video_widget.winId()))
            else:
                # Solo actualizar opciones del motor actual
                current_cfg = new_mpv_cfg if new_engine == 'mpv' else new_vlc_cfg
                self._playback_manager.update_engine_options(current_cfg)

            if self._save_callback:
                self._save_callback(self._config)
            
            QMessageBox.information(self, "Reproductor", 
                                  f"Motor configurado: {new_engine.upper()}.\nConfiguración actualizada y reiniciada.")

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

    def _fill_table(self, playlist):
        self.table.setRowCount(len(playlist))
        for row, channel in enumerate(playlist):
            # Nombre
            self.table.setItem(row, 0, QTableWidgetItem(channel.name))
            
            # Logo
            logo_item = QTableWidgetItem()
            logo_item.setData(Qt.ItemDataRole.UserRole, channel)
            self.table.setItem(row, 1, logo_item)
            if channel.logo_url:
                self._logo_loader.get_logo(channel.logo_url)
            
            # EPG (Programación)
            epg_item = QTableWidgetItem("Cargando guía...")
            self.table.setItem(row, 2, epg_item)
        
        # Actualizar visualización de EPG inmediatamente
        self._refresh_epg_display()

    def _refresh_epg_display(self):
        """Actualiza la columna de programación actual para cada canal."""
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            channel = item.data(Qt.ItemDataRole.UserRole)
            if not channel:
                continue
                
            program = self._epg_manager.get_currently_airing(channel.tvg_id, channel.name)
            if program:
                text = f"NOW: {program.title}"
                if program.description:
                    text += f"\n({program.description[:50]}...)"
                self.table.item(row, 2).setText(text)
            else:
                self.table.item(row, 2).setText("Guía no disponible")

    def _on_item_clicked(self, item: QTableWidgetItem):
        row = item.row()
        channel = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)
        if isinstance(channel, Channel):
            logging.info(f"Reproduciendo: {channel.name}")
            self._playback_manager.play_channel(channel)

    def _on_logo_loaded(self, url: str, pixmap: QPixmap):
        """Actualiza todas las filas que usen este logo."""
        icon = QIcon(pixmap)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            if item is not None:
                channel = item.data(Qt.ItemDataRole.UserRole)
                if channel and channel.logo_url == url:
                    item.setIcon(icon)

    def closeEvent(self, event):
        self._playback_manager.stop_playback()
        super().closeEvent(event)
