from src.domain.ports.i_player import IPlayer
from src.domain.entities.channel import Channel

class PlaybackManager:
    """Servicio de aplicación para controlar la reproducción de canales."""
    
    def __init__(self, player: IPlayer):
        self._player = player
        self._current_channel = None

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

    def switch_player_engine(self, new_player: IPlayer, window_id: int):
        """Cambia el motor de reproducción por uno nuevo."""
        if self._player:
            self._player.stop()
            self._player.release()
        
        self._player = new_player
        self._player.set_output_window(window_id)
        if self._current_channel:
            self.play_channel(self._current_channel)

    @property
    def current_channel(self) -> Channel:
        return self._current_channel
