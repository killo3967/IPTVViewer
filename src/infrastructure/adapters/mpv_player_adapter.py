import os
import sys
import logging
import threading
from pathlib import Path

# --- CONFIGURACIÓN DE LIBMPV (DEBE IR ANTES DE IMPORT MPV) ---
if getattr(sys, 'frozen', False):
    # PyInstaller bundle: bin/ está en _internal/
    bin_path = Path(sys._MEIPASS) / "bin"
else:
    bin_path = Path(__file__).parent.parent.parent.parent / "bin"
if bin_path.exists():
    abs_bin_path = str(bin_path.absolute())
    if sys.version_info >= (3, 8):
        try:
            os.add_dll_directory(abs_bin_path)
        except Exception as e:
            logging.error(f"MPV: Error al añadir directorio de DLLs: {e}")

    # También añadir a PATH para redundancia y compatibilidad con ctypes interno de mpv.py
    if abs_bin_path not in os.environ["PATH"]:
        os.environ["PATH"] = abs_bin_path + os.pathsep + os.environ["PATH"]
    logging.debug(f"MPV: DLL path configurado: {abs_bin_path}")
# -----------------------------------------------------------

import mpv  # noqa: E402
from src.domain.ports.i_player import IPlayer  # noqa: E402

class MpvPlayerAdapter(IPlayer):
    """Adaptador de infraestructura que utiliza la librería mpv para la reproducción."""

    # Valores por defecto para la configuración de mpv
    DEFAULT_CONFIG = {
        "network_caching": 5000,
        "hw_acceleration": False,
        "cache": True,
        "demuxer_readahead_secs": 5.0,
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "log_level": "info",
        "logfile": "logs/mpv.log",
        "file_logging": True
    }

    def __init__(self, mpv_config: dict = None, proxy_config: dict = None):
        """
        Inicializa el adaptador con una configuración personalizada.
        """
        self._config = self.DEFAULT_CONFIG.copy()
        if mpv_config:
            self._config.update(mpv_config)

        self._proxy_config = proxy_config
        self._player = None
        self._window_id = None
        self._current_url = None
        self._reconnecting = False # Flag para evitar bucles de reconexión

        # mpv ya está importado y la DLL cargada gracias al setup previo en este módulo
        self._init_mpv()

    def _init_mpv(self):
        """Inicializa la instancia de mpv con las opciones actuales."""
        self.release()

        try:
            log_handler = None
            log_level = self._config.get("log_level", "info")

            # --- Configuración de Logging del Motor ---
            if self._config.get("file_logging"):
                log_path = Path(self._config.get("logfile", "logs/mpv.log"))
                log_path.parent.mkdir(exist_ok=True)

                def my_log(level, prefix, text):
                    if not text.strip():
                        return
                    try:
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(f"{level.upper()} [{prefix}] {text}\n")
                    except OSError:
                        logging.debug("MPV: No se pudo escribir en el log de archivo.")
                log_handler = my_log
                logging.info(f"MPV: Sistema de log preparado en {log_path} (Nivel: {log_level})")

            # --- OPCIONES DE RESILIENCIA MPV (EQUILIBRADO) ---
            options = {
                "ytdl": False,
                "input_default_bindings": True,
                "input_vo_keyboard": True,
                "osc": True,

                # Reconexión agresiva a nivel de transporte (FFmpeg)
                "stream_lavf_o": "reconnect=1,reconnect_streamed=1,reconnect_delay_max=5,reconnect_on_network_error=1,reconnect_on_http_error=all",
                "force_seekable": "yes",

                # Buffer y Demuxer
                "cache": "yes" if self._config.get("cache", True) else "no",
                "demuxer_max_bytes": f"{self._config.get('network_caching', 5000) * 1024}",
                "demuxer_readahead_secs": self._config.get("demuxer_readahead_secs", 10.0),
                "demuxer_lavf_o": "analyzeduration=1000000,probesize=1000000",

                # Cabeceras y Agente
                "user_agent": self._config.get("user_agent"),
                "http_header_fields": "Referer: 'http://localhost/'",

                "vd_lavc_threads": 1,

                # Sincronización (Volvemos a calidad normal)
                "log_handler": log_handler,
                "loglevel": log_level,
                "video_sync": "audio",
                "hr_seek": "yes"
            }

            # Configuración de Proxy
            if self._proxy_config and self._proxy_config.get('enabled'):
                p_type = self._proxy_config.get('type', 'http').lower()
                server = self._proxy_config.get('server', '')

                if server:
                    logging.info(f"MPV: Configurando acceso por red via proxy {p_type} (vía entorno)")
                    # No pasamos 'proxy' como opción directa ya que libmpv puede fallar con esa opción
                    # en algunas versiones. Al haber configurado os.environ['ALL_PROXY'],
                    # FFmpeg (backend de mpv) lo detectará automáticamente.

            # Aceleración por hardware
            if self._config.get("hw_acceleration"):
                options["hwdec"] = "auto"
                logging.info("MPV: Aceleración por hardware ACTIVADA (auto)")
            else:
                options["hwdec"] = "no"
                logging.info("MPV: Aceleración por hardware DESACTIVADA")

            self._player = mpv.MPV(**options)

            # Configurar eventos para reconexión
            @self._player.property_observer('idle-active')
            def on_idle_change(_name, value):
                # Si el reproductor entra en estado inactivo (pero se supone que debería estar reproduciendo)
                if value and self._current_url and not self._reconnecting:
                    self._reconnecting = True
                    logging.warning("MPV: El motor ha quedado inactivo. Intentando reconectar en 1s...")
                    # Delay para no saturar al intentar reconectar tras un error fatal
                    threading.Timer(1.0, self._perform_reconnect).start()

            # Re-asociar ventana si existe
            if self._window_id:
                self.set_output_window(self._window_id)

        except Exception as e:
            logging.error(f"MPV: Error fatal inicializando motor: {e}")

    def _perform_reconnect(self):
        """Tarea de reconexión con reseteo de flag."""
        if self._current_url:
            self.play(self._current_url)
        # Dar tiempo al motor para salir del estado idle antes de permitir otra reconexión
        threading.Timer(2.0, self._reset_reconnect_flag).start()

    def _reset_reconnect_flag(self):
        self._reconnecting = False

    def play(self, url: str):
        """Implementa la reproducción con mpv."""
        if not self._player or not url:
            return

        self._current_url = url
        try:
            self._player.play(url)
            logging.debug(f"MPV: Reproduciendo {url}")
        except Exception as e:
            logging.error(f"MPV: Error al intentar reproducir: {e}")

    def stop(self):
        """Detiene la reproducción."""
        if self._player:
            self._player.stop()

    def set_output_window(self, window_id: int):
        """Asocia el widget de la UI con el motor mpv."""
        self._window_id = window_id
        if self._player:
            self._player.wid = str(window_id)

    def set_hw_acceleration(self, enabled: bool):
        """Cambia la aceleración hardware y reinicia."""
        if self._config.get("hw_acceleration") == enabled:
            return
        self._config["hw_acceleration"] = enabled
        self._init_mpv()

    def update_engine_options(self, options: dict):
        """Actualiza opciones y reinicia."""
        self._config.update(options)
        self._init_mpv()

    def release(self):
        """Libera recursos."""
        if self._player:
            try:
                self._player.terminate()
            except (AttributeError, OSError, RuntimeError):
                logging.debug("MPV: Falló la liberación limpia del reproductor.")
            self._player = None
