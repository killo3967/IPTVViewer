import logging
from collections.abc import Callable

from src.domain.entities.channel import Channel
from src.domain.ports.i_player import IPlayer


class PlaybackManager:
    """Servicio de aplicación para controlar la reproducción de canales."""

    def __init__(self, player: IPlayer):
        self._player = player
        self._current_channel: Channel | None = None
        self._muted: bool = False
        self._volume: int = 100
        #: Aviso a la UI cuando el motor agota los reintentos de un canal.
        self.on_playback_failed: Callable[[Channel | None], None] | None = None
        self._wire_retry_callback()

    def _wire_retry_callback(self):
        """Conecta el aviso de "reintentos agotados" del motor, si lo soporta."""
        if hasattr(self._player, "on_retry_exhausted"):
            self._player.on_retry_exhausted = self._handle_retry_exhausted

    def _handle_retry_exhausted(self):
        """Traduce el aviso del motor (hilo de VLC) a un callback de la app."""
        channel = self._current_channel
        logging.warning(
            "Playback: sin señal tras agotar reintentos (%s, motor %s)",
            getattr(channel, "name", "canal desconocido"), self.engine_name,
        )
        callback = self.on_playback_failed
        if callback is not None:
            callback(channel)

    def play_channel(self, channel: Channel):
        """Inicia la reproducción de un canal específico."""
        motor = self.engine_name
        logging.info("Playback: arrancando %r con %s", channel.name, motor)
        self._player.stop()
        try:
            self._player.play(channel.url)
        except Exception as exc:
            logging.error(
                "Playback: el motor %s no pudo arrancar %r: %s", motor, channel.name, exc,
            )
            raise
        self._current_channel = channel
        logging.info("Playback: orden enviada a %s (%r)", motor, channel.name)

    def stop_playback(self):
        """Detiene la reproducción actual."""
        if self._current_channel is not None:
            logging.info("Playback: deteniendo %r", self._current_channel.name)
        self._player.stop()
        self._current_channel = None

    @property
    def engine_name(self) -> str:
        """Nombre del motor activo, para el log."""
        return type(self._player).__name__

    def initialize_display(self, window_id: int):
        """Asocia el reproductor con el widget de la interfaz."""
        self._player.set_output_window(window_id)

    def set_hw_accel(self, enabled: bool):
        """Activa o desactiva la aceleración por hardware en el reproductor."""
        self._player.set_hw_acceleration(enabled)

    def update_engine_options(self, options: dict):
        """Actualiza las opciones técnicas del motor de reproducción actual."""
        self._player.update_engine_options(options)

    def set_muted(self, enabled: bool):
        """Silencia o restaura el audio del reproductor actual."""
        self._muted = bool(enabled)
        self._player.set_muted(self._muted)

    def set_volume(self, level: int):
        """Ajusta el volumen (0-100) del reproductor actual."""
        self._volume = max(0, min(100, int(level)))
        self._player.set_volume(self._volume)

    def switch_player_engine(self, new_player: IPlayer, window_id: int):
        """Cambia el motor de reproducción por uno nuevo."""
        if self._player:
            self._player.stop()
            self._player.release()

        self._player = new_player
        self._player.set_output_window(window_id)
        self._wire_retry_callback()
        # Re-aplicar el estado de audio vigente para que el cambio de
        # motor no altere lo que oye el usuario.
        self._player.set_muted(self._muted)
        self._player.set_volume(self._volume)
        if self._current_channel:
            self.play_channel(self._current_channel)

    @property
    def current_channel(self) -> Channel | None:
        return self._current_channel
