from src.domain.ports.i_playlist_repo import IPlaylistRepository
from src.domain.entities.playlist import Playlist

class PlaylistLoader:
    """Servicio de aplicación para gestionar la carga y filtrado de listas."""
    
    def __init__(self, repository: IPlaylistRepository):
        self._repository = repository

    def load_and_filter(self, source: str, group_filter: str = "") -> Playlist:
        """Coordina la carga de canales y aplica el filtro de grupo."""
        channels = self._repository.get_channels(source)
        full_playlist = Playlist(channels)
        return full_playlist.filter_by_group(group_filter)
