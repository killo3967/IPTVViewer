from src.domain.entities.channel import Channel
from src.domain.ports.i_player import IPlayer


class PlaybackManager:
    """Servicio de aplicación para controlar la reproducción de canales."""

    def __init__(self, player: IPlayer):
        self._player = player
        self._current_channel: Channel | None = None
        self._muted: bool = False
        self._volume: int = 100

    def play_channel(self, channel: Channel):
        """Inicia la reproducción de un canal específico."""
        self._player.stop()
        self._player.play(channel.url)
        self._current_channel = channel

    def stop_playback(self):
        """Detiene la reproducción actual."""
        self._player.stop()
        self._current_channel = None

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
        # Re-aplicar el estado de audio vigente para que el cambio de
        # motor no altere lo que oye el usuario.
        self._player.set_muted(self._muted)
        self._player.set_volume(self._volume)
        if self._current_channel:
            self.play_channel(self._current_channel)

    @property
    def current_channel(self) -> Channel | None:
        return self._current_channel
