import logging

from src.domain.entities.playlist import Playlist
from src.domain.ports.i_playlist_repo import IPlaylistRepository


class PlaylistLoader:
    """Servicio de aplicación para gestionar la carga y filtrado de listas."""
    
    def __init__(self, repository: IPlaylistRepository):
        self._repository = repository

    def load_and_filter(self, source: str, group_filter: str = "") -> Playlist:
        """Coordina la carga de canales y aplica el filtro de grupo."""
        channels = self._repository.get_channels(source)
        full_playlist = Playlist(channels)
        filtrada = full_playlist.filter_by_group(group_filter)
        if group_filter:
            logging.info(
                "Lista: %d canales en la descarga, %d tras el filtro %r",
                len(channels), len(filtrada), group_filter,
            )
        else:
            logging.info("Lista: %d canales en la descarga, sin filtro", len(channels))
        return filtrada
