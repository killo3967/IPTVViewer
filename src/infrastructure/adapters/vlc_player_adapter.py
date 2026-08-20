import logging
import sys

import vlc

from src.domain.ports.i_player import IPlayer


class VlcPlayerAdapter(IPlayer):
    """Adaptador de infraestructura que utiliza la librería VLC para la reproducción."""

    # Valores por defecto para la configuración de VLC
    DEFAULT_CONFIG = {
        "reset_plugins_cache": True,
        "network_caching": 5000,
        "clock_jitter": 500,
        "clock_synchro": 0,
        "drop_late_frames": False,
        "skip_frames": False,
        "repeat": True,
        "log_verbose": 2,
        "file_logging": True,
        "logfile": "logs/vlc.log",
        "hw_acceleration": False,
    }

    def __init__(self, vlc_config: dict = None, proxy_config: dict = None):
        """
        Inicializa el adaptador con una configuración personalizada.
        """
        self._config = self.DEFAULT_CONFIG.copy()
        if vlc_config:
            self._config.update(vlc_config)

        self._proxy_config = proxy_config
        self._instance = None
        self._player = None
        self._window_id = None
        self._current_url = None
        self._init_vlc()

    def _init_vlc(self):
        """Inicializa o reinicializa la instancia de VLC con las opciones actuales."""
        # Liberar si ya existe
        self.release()

        vlc_args = []

        # Opciones booleanas y de valor
        if self._config.get("reset_plugins_cache"):
            vlc_args.append("--reset-plugins-cache")

        vlc_args.append(f"--network-caching={self._config.get('network_caching', 5000)}")
        vlc_args.append(f"--clock-jitter={self._config.get('clock_jitter', 500)}")
        vlc_args.append(f"--clock-synchro={self._config.get('clock_synchro', 0)}")

        # Drop / Skip frames (VLC usa no- prefijo para desactivar)
        if not self._config.get("drop_late_frames", False):
            vlc_args.append("--no-drop-late-frames")
        else:
            vlc_args.append("--drop-late-frames")

        if not self._config.get("skip_frames", False):
            vlc_args.append("--no-skip-frames")
        else:
            vlc_args.append("--skip-frames")

        if self._config.get("repeat"):
            vlc_args.append("--repeat")

        vlc_args.append(f"--log-verbose={self._config.get('log_verbose', 2)}")

        if self._config.get("file_logging"):
            vlc_args.append("--file-logging")
            logfile = self._config.get("logfile", "logs/vlc.log")
            vlc_args.append(f"--logfile={logfile}")

        if self._config.get("hw_acceleration"):
            # Aceleración por hardware activa (Optimizado para Windows 11 / NVIDIA)
            vlc_args.extend([
                "--avcodec-hw=dxva2",
                "--vout=direct3d11",
                "--direct3d11-hw-blending",
            ])
            logging.info("VLC: Aceleración por hardware ACTIVADA (dxva2, d3d11)")
        else:
            # Aceleración desactivada totalmente
            vlc_args.extend([
                "--avcodec-hw=none",
                "--no-directx-hw-yuv",
                "--no-direct3d11-hw-blending",
                "--no-direct3d9-hw-blending",
                "--no-directx-overlay",
            ])
            logging.info("VLC: Aceleración por hardware DESACTIVADA (Forzado CPU)")

        # Configuración de Proxy
        if self._proxy_config and self._proxy_config.get("enabled"):
            p_type = self._proxy_config.get("type", "http").lower()
            server = self._proxy_config.get("server")
            port = self._proxy_config.get("port", 8080)
            user = self._proxy_config.get("username")
            pwd = self._proxy_config.get("password")

            if server:
                if "socks" in p_type:
                    vlc_args.append(f"--socks={server}:{port}")
                    if user:
                        vlc_args.append(f"--socks-user={user}")
                    if pwd:
                        vlc_args.append(f"--socks-pwd={pwd}")
                else:
                    # HTTP/HTTPS
                    vlc_args.append(f"--http-proxy={server}:{port}")
                    if user:
                        vlc_args.append(f"--http-proxy-user={user}")
                    if pwd:
                        vlc_args.append(f"--http-proxy-pwd={pwd}")
                logging.info(f"VLC: Usando proxy {p_type} en {server}:{port}")

        logging.debug(f"VLC: Inicializando con argumentos: {vlc_args}")
        self._instance = vlc.Instance(vlc_args)
        self._player = self._instance.media_player_new()

        # Suscribirse a eventos para detección de fin de stream (Autorreconector)
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)
        events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_error_encountered)

        # Re-asociar ventana si existe
        if self._window_id:
            self.set_output_window(self._window_id)

    def _on_end_reached(self, event):
        """Callback cuando VLC detecta fin de flujo."""
        if self._current_url:
            logging.warning("VLC: Fin de stream (EOF) detectado. Reintentando inmediatamente...")
            import threading

            # Reducido a 200ms para una reconexión casi instantánea
            threading.Timer(0.2, self.play, args=[self._current_url]).start()

    def _on_error_encountered(self, event):
        """Callback cuando hay un error de reproducción."""
        logging.error("VLC: Error de reproducción. Reintentando...")
        if self._current_url:
            import threading

            # Reducido a 500ms para errores de red
            threading.Timer(0.5, self.play, args=[self._current_url]).start()

    def update_engine_options(self, new_config: dict):
        """Actualiza la configuración y reinicia la instancia de VLC."""
        self._config.update(new_config)
        self._init_vlc()

    def set_hw_acceleration(self, enabled: bool):
        """Mantener compatibilidad con la interfaz anterior."""
        if self._config.get("hw_acceleration") == enabled:
            return

        self._config["hw_acceleration"] = enabled
        self._init_vlc()

    def play(self, url: str):
        """Implementa el inicio de reproducción con VLC."""
        if not self._player or not url:
            return

        self._current_url = url  # Guardar para reconexión
        media = self._instance.media_new(url)
        # Refuerzo de caching en el media
        media.add_option(f":network-caching={self._config.get('network_caching', 5000)}")
        media.add_option(":no-video-title-show")
        media.add_option(":http-reconnect")
        media.add_option(":http-continuous")

        # User-Agent simulado para evitar bloqueos del servidor
        media.add_option(":http-user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

        # Opciones agresivas para ignorar errores de stream y ocultar artefactos
        media.add_option(":avcodec-error-concealment=3")
        media.add_option(":avcodec-threads=1")  # Decodificación monocanal para estabilidad en cortes
        media.add_option(":no-clock-synchro")  # No esperar sincronía perfecta de reloj
        media.add_option(":skip-frames")  # Saltar frames si hay retraso (evita el efecto cámara lenta)

        # Reforzar HW accel en el media también
        if self._config.get("hw_acceleration"):
            media.add_option(":avcodec-hw=dxva2")
        else:
            media.add_option(":avcodec-hw=none")

        self._player.set_media(media)
        self._player.play()

    def stop(self):
        """Detiene el reproductor VLC."""
        if self._player:
            self._player.stop()

    def set_output_window(self, window_id: int):
        """Asocia el widget de la UI con el motor VLC."""
        self._window_id = window_id
        if not self._player:
            return

        if sys.platform == "win32":
            self._player.set_hwnd(window_id)
        else:
            self._player.set_xwindow(window_id)

    def release(self):
        """Libera recursos de VLC."""
        if self._player:
            try:
                self._player.stop()
                self._player.release()
            except (AttributeError, OSError, RuntimeError):
                logging.debug("VLC: Falló la liberación limpia del reproductor.")
            self._player = None

        if self._instance:
            try:
                self._instance.release()
            except (AttributeError, OSError, RuntimeError):
                logging.debug("VLC: Falló la liberación limpia de la instancia.")
            self._instance = None
