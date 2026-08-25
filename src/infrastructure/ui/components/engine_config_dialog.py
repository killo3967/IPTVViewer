from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class EngineConfigDialog(QDialog):
    """Diálogo para configurar el motor de reproducción y sus parámetros técnicos."""
    
    def __init__(self, current_engine: str, vlc_config: dict, mpv_config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración del Reproductor")
        self.setMinimumWidth(500)
        self.setMinimumHeight(550)
        
        self._current_engine = current_engine
        self._vlc_config = vlc_config.copy()
        self._mpv_config = mpv_config.copy()
        
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Selector de Motor ---
        engine_group = QGroupBox("Motor Principal")
        engine_layout = QFormLayout(engine_group)
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["vlc", "mpv"])
        self.engine_combo.setCurrentText(self._current_engine)
        engine_layout.addRow("Seleccionar motor:", self.engine_combo)
        layout.addWidget(engine_group)
        
        # --- Pestañas para cada motor ---
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Pestaña VLC
        vlc_tab = QWidget()
        self._setup_vlc_tab(vlc_tab)
        self.tabs.addTab(vlc_tab, "Opciones VLC")
        
        # Pestaña mpv
        mpv_tab = QWidget()
        self._setup_mpv_tab(mpv_tab)
        self.tabs.addTab(mpv_tab, "Opciones mpv")
        
        # Seleccionar pestaña según el motor actual
        if self._current_engine == "mpv":
            self.tabs.setCurrentIndex(1)
        
        # --- Botones ---
        btns = QHBoxLayout()
        save_btn = QPushButton("Guardar y Reiniciar")
        save_btn.clicked.connect(self.accept)
        save_btn.setDefault(True)
        
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

    def _setup_vlc_tab(self, widget):
        layout = QVBoxLayout(widget)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        
        # Cache y Red
        net_group = QGroupBox("Caché y Red")
        net_form = QFormLayout(net_group)
        self.vlc_net_caching = QSpinBox()
        self.vlc_net_caching.setRange(0, 60000)
        self.vlc_net_caching.setSuffix(" ms")
        self.vlc_net_caching.setValue(self._vlc_config.get("network_caching", 5000))
        net_form.addRow("Caché de red:", self.vlc_net_caching)
        
        self.vlc_clock_jitter = QSpinBox()
        self.vlc_clock_jitter.setRange(0, 5000)
        self.vlc_clock_jitter.setSuffix(" ms")
        self.vlc_clock_jitter.setValue(self._vlc_config.get("clock_jitter", 500))
        net_form.addRow("Clock jitter:", self.vlc_clock_jitter)
        form.addRow(net_group)
        
        # Reproducción
        play_group = QGroupBox("Reproducción y Frames")
        play_form = QFormLayout(play_group)
        self.vlc_drop_frames = QCheckBox("Permitir soltar frames atrasados")
        self.vlc_drop_frames.setChecked(self._vlc_config.get("drop_late_frames", False))
        play_form.addRow(self.vlc_drop_frames)
        
        self.vlc_skip_frames = QCheckBox("Permitir saltar frames")
        self.vlc_skip_frames.setChecked(self._vlc_config.get("skip_frames", False))
        play_form.addRow(self.vlc_skip_frames)
        
        self.vlc_hw_accel = QCheckBox("Aceleración por Hardware (VLC)")
        self.vlc_hw_accel.setChecked(self._vlc_config.get("hw_acceleration", False))
        play_form.addRow(self.vlc_hw_accel)
        form.addRow(play_group)
        
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _setup_mpv_tab(self, widget):
        layout = QVBoxLayout(widget)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        
        # Cache y Buffer
        cache_group = QGroupBox("Buffer y Streaming")
        cache_form = QFormLayout(cache_group)
        
        self.mpv_net_caching = QSpinBox()
        self.mpv_net_caching.setRange(0, 500000)
        self.mpv_net_caching.setSuffix(" KB")
        self.mpv_net_caching.setValue(self._mpv_config.get("network_caching", 5000))
        cache_form.addRow("Buffer máximo (KB):", self.mpv_net_caching)
        
        self.mpv_readahead = QDoubleSpinBox()
        self.mpv_readahead.setRange(0, 600)
        self.mpv_readahead.setSuffix(" seg")
        self.mpv_readahead.setValue(self._mpv_config.get("demuxer_readahead_secs", 5.0))
        cache_form.addRow("Antelación lectura:", self.mpv_readahead)
        
        self.mpv_cache_enabled = QCheckBox("Habilitar caché en disco/memoria")
        self.mpv_cache_enabled.setChecked(self._mpv_config.get("cache", True))
        cache_form.addRow(self.mpv_cache_enabled)
        
        form.addRow(cache_group)
        
        # Reproducción
        play_group = QGroupBox("Hardware y Agente")
        play_form = QFormLayout(play_group)
        
        self.mpv_hw_accel = QCheckBox("Aceleración por Hardware (mpv)")
        self.mpv_hw_accel.setChecked(self._mpv_config.get("hw_acceleration", False))
        play_form.addRow(self.mpv_hw_accel)
        
        self.mpv_ua = QLineEdit()
        self.mpv_ua.setText(self._mpv_config.get("user_agent", ""))
        play_form.addRow("User Agent:", self.mpv_ua)
        
        form.addRow(play_group)
        
        # --- Grupo: Diagnóstico y Logs ---
        log_group = QGroupBox("Diagnóstico y Logs")
        log_form = QFormLayout(log_group)
        
        self.mpv_file_logging = QCheckBox("Guardar log en archivo")
        self.mpv_file_logging.setChecked(self._mpv_config.get("file_logging", True))
        log_form.addRow(self.mpv_file_logging)
        
        self.mpv_log_level = QComboBox()
        self.mpv_log_level.addItems(["fatal", "error", "warn", "info", "v", "debug", "trace"])
        self.mpv_log_level.setCurrentText(self._mpv_config.get("log_level", "info"))
        log_form.addRow("Nivel de log:", self.mpv_log_level)
        
        self.mpv_logfile = QLineEdit()
        self.mpv_logfile.setText(self._mpv_config.get("logfile", "logs/mpv.log"))
        log_form.addRow("Ruta del log:", self.mpv_logfile)
        
        form.addRow(log_group)
        
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def get_results(self) -> tuple:
        """Retorna (engine, vlc_config, mpv_config)."""
        new_engine = self.engine_combo.currentText()
        
        vlc_results = self._vlc_config.copy()
        vlc_results.update({
            "network_caching": self.vlc_net_caching.value(),
            "clock_jitter": self.vlc_clock_jitter.value(),
            "drop_late_frames": self.vlc_drop_frames.isChecked(),
            "skip_frames": self.vlc_skip_frames.isChecked(),
            "hw_acceleration": self.vlc_hw_accel.isChecked()
        })
        
        mpv_results = self._mpv_config.copy()
        mpv_results.update({
            "network_caching": self.mpv_net_caching.value(),
            "demuxer_readahead_secs": self.mpv_readahead.value(),
            "cache": self.mpv_cache_enabled.isChecked(),
            "hw_acceleration": self.mpv_hw_accel.isChecked(),
            "user_agent": self.mpv_ua.text(),
            "file_logging": self.mpv_file_logging.isChecked(),
            "log_level": self.mpv_log_level.currentText(),
            "logfile": self.mpv_logfile.text()
        })
        
        return new_engine, vlc_results, mpv_results
