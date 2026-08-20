from abc import ABC, abstractmethod
from typing import List
from ..entities.channel import Channel

class IPlaylistRepository(ABC):
    """Puerto de salida (Driven Port) para el acceso a datos de listas M3U."""
    
    @abstractmethod
    def get_channels(self, source: str) -> List[Channel]:
        """Recupera la lista de canales desde una fuente (archivo o URL)."""
        pass
