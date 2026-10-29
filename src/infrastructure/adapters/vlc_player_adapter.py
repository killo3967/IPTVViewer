import logging
import sys
import threading
from collections.abc import Callable
from typing import Any, ClassVar

from src.domain.ports.i_player import IPlayer
from src.infrastructure.utils.log_safe import safe_url
from src.infrastructure.utils.vlc_bootstrap import configure_vlc_env, detect_vlc_lib

# Configurar python-vlc ANTES de importarlo: VLC portátil o carpeta señalada.
_libvlc_path = detect_vlc_lib()
if _libvlc_path is not None:
    configure_vlc_env(_libvlc_path.parent)

_vlc_import_error: Exception | None = None


def _import_vlc() -> Any:
    """Importa python-vlc (el entorno ya configurado). None si VLC no está.

    El import es diferido (no a nivel de módulo) para que un VLC instalado o
    señalado después de importar el adaptador se recoja en el siguiente
    ``_init_vlc`` sin reiniciar la app. Un fallo de import no tumba la app:
    se registra en ``_vlc_import_error`` y la instanciación falla limpia.
    """
    global _vlc_import_error
    try:
        import vlc
    except Exception as exc:  # VLC ausente: python-vlc no puede cargar libvlc
        _vlc_import_error = exc
        return None
    _vlc_import_error = None
    return vlc


class VlcPlayerAdapter(IPlayer):
    """Adaptador de infraestructura que utiliza la librería VLC para la reproducción."""

    # Valores por defecto para la configuración de VLC
    DEFAULT_CONFIG: ClassVar[dict] = {
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

    # Autorreconexión: backoff exponencial con tope para no reintentar
    # un canal caído de forma indefinida (spam de log, hilos y CPU).
    RETRY_MAX_ATTEMPTS = 6
    RETRY_BASE_DELAY = 1.0   # segundos tras un error de reproducción
    RETRY_MAX_DELAY = 10.0   # tope del backoff
    EOF_BASE_DELAY = 0.2     # reconexión casi inmediata tras un fin de stream

    # Estado de reintentos: también como valor de clase para tolerar
    # instancias creadas sin __init__ (tests) y reinicios del motor.
    _retry_count: int = 0
    _retry_token: int = 0
    _retry_timer: threading.Timer | None = None
    #: Aviso opcional (sin Qt) cuando se agotan los reintentos.
    on_retry_exhausted: Callable[[], None] | None = None

    def __init__(self, vlc_config: dict | None = None, proxy_config: dict | None = None):
        """
        Inicializa el adaptador con una configuración personalizada.
        """
        self._config = self.DEFAULT_CONFIG.copy()
        if vlc_config:
            self._config.update(vlc_config)

        self._proxy_config = proxy_config
        self._instance: Any = None
        self._player: Any = None
        self._window_id: int | None = None
        self._current_url: str | None = None
        self._init_vlc()

    def _init_vlc(self):
        """Inicializa o reinicializa la instancia de VLC con las opciones actuales."""
        # Liberar si ya existe
        self.release()

        vlc = _import_vlc()
        if vlc is None:
            raise RuntimeError(
                "VLC no está disponible (import vlc falló: "
                f"{_vlc_import_error}). Resuélvelo desde el diálogo de VLC del arranque."
            )

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
        playing = getattr(vlc.EventType, "MediaPlayerPlaying", None)
        if playing is not None:
            events.event_attach(playing, self._on_playing)

        # Re-asociar ventana si existe
        if self._window_id:
            self.set_output_window(self._window_id)

    def _on_end_reached(self, event):
        """Callback cuando VLC detecta fin de flujo (EOF)."""
        self._schedule_retry(self.EOF_BASE_DELAY, "Fin de stream (EOF)")

    def _on_error_encountered(self, event):
        """Callback cuando VLC no consigue reproducir el canal."""
        self._schedule_retry(self.RETRY_BASE_DELAY, "Error de reproducción")

    def _on_playing(self, event):
        """Si el stream arranca, se reinicia el contador de reintentos."""
        if self._retry_count:
            logging.info("VLC: reproducción recuperada tras %d reintento(s).", self._retry_count)
        self._retry_count = 0
        self._cancel_retry()

    def _cancel_retry(self):
        """Cancela el reintento programado, si lo hay."""
        if self._retry_timer is not None:
            self._retry_timer.cancel()
            self._retry_timer = None

    def _schedule_retry(self, base_delay: float, reason: str):
        """Programa un reintento con backoff exponencial y tope de intentos.

        Antes se reintentaba cada 500 ms sin límite: un canal caído generaba
        miles de líneas de log, acumulaba hilos y gastaba CPU indefinidamente.
        """
        url = self._current_url
        if not url:
            return

        self._retry_count += 1
        if self._retry_count > self.RETRY_MAX_ATTEMPTS:
            logging.error(
                "VLC: %s. Reintentos agotados (%d) para %s",
                reason,
                self.RETRY_MAX_ATTEMPTS,
                url,
            )
            self._retry_count = 0
            self._cancel_retry()
            self._notify_retry_exhausted()
            return

        delay = min(self.RETRY_MAX_DELAY, base_delay * (2 ** (self._retry_count - 1)))
        logging.warning(
            "VLC: %s. Reintento %d/%d en %.1f s",
            reason,
            self._retry_count,
            self.RETRY_MAX_ATTEMPTS,
            delay,
        )
        self._cancel_retry()
        timer = threading.Timer(delay, self._retry_play, args=[self._retry_token, url])
        timer.daemon = True
        self._retry_timer = timer
        timer.start()

    def _retry_play(self, token: int, url: str):
        """Reintenta solo si el canal y el motor siguen siendo los mismos."""
        if token != self._retry_token or url != self._current_url or not self._player:
            return
        self._play_url(url)

    def _notify_retry_exhausted(self):
        """Avisa (una sola vez) de que el canal no se puede reproducir."""
        callback = self.on_retry_exhausted
        if callback is None:
            return
        try:
            callback()
        except Exception:  # el aviso nunca debe tumbar el motor
            logging.debug("VLC: falló el aviso de reintentos agotados.", exc_info=True)

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
        """Inicia la reproducción y reinicia el estado de reintentos."""
        self._retry_count = 0
        self._retry_token += 1
        self._cancel_retry()
        self._play_url(url)

    def _play_url(self, url: str):
        """Reproduce ``url`` sin tocar el contador de reintentos."""
        if not self._player or not url:
            return

        self._current_url = url  # Guardar para reconexión
        logging.info(f"VLC: cargando {safe_url(url)}")
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
        """Detiene la reproducción y cancela los reintentos pendientes."""
        self._retry_count = 0
        self._retry_token += 1
        self._cancel_retry()
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

    def set_muted(self, enabled: bool):
        """Silencia (True) o restaura el audio del motor VLC."""
        if not self._player:
            return
        try:
            self._player.audio_set_mute(bool(enabled))
        except (AttributeError, OSError, RuntimeError):
            pass

    def set_volume(self, level: int):
        """Ajusta el volumen VLC en el rango 0-100."""
        if not self._player:
            return
        clamped = max(0, min(100, int(level)))
        try:
            self._player.audio_set_volume(clamped)
        except (AttributeError, OSError, RuntimeError):
            pass

    def release(self):
        """Libera recursos de VLC."""
        self._retry_token += 1
        self._retry_count = 0
        self._cancel_retry()
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
