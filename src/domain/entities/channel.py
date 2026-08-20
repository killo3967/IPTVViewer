from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)
class Channel:
    """Entidad que representa un canal de IPTV."""
    name: str
    url: str
    group: str = "Otros"
    logo_url: Optional[str] = None
    tvg_id: Optional[str] = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("El nombre del canal no puede estar vacío")
        if not self.url:
            raise ValueError("La URL del canal no puede estar vacía")
