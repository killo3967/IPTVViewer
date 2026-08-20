import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict

def normalize_name(name: str) -> str:
    """Normaliza un nombre para facilitar el matching (minúsculas, sin espacios ni caracteres especiales)."""
    if not name:
        return ""
    # Convertir a minúsculas, eliminar caracteres no alfanuméricos y espacios
    normalized = re.sub(r'[^a-zA-Z0-9]', '', name.lower())
    return normalized

@dataclass(frozen=True)
class Program:
    """Entidad que representa un programa individual en la EPG."""
    title: str
    start_time: datetime
    end_time: datetime
    channel_id: str  # Referencia al tvg-id del canal
    description: Optional[str] = None
    category: Optional[str] = None

    def is_currently_airing(self) -> bool:
        """Verifica si el programa se está emitiendo en este momento."""
        now = datetime.now()
        return self.start_time <= now <= self.end_time

class EPGData:
    """Agregado que gestiona la colección de programas."""
    def __init__(self, programs: List[Program] = None, channel_names: Dict[str, str] = None):
        self._programs = programs or []
        # Mapa de channel_id -> nombre normalizado (opcional, para ayudar al matching)
        self._channel_id_to_normalized_name = {
            cid: normalize_name(name) for cid, name in (channel_names or {}).items()
        }
        
        # Mapeo rápido de channel_id -> lista de programas
        self._programs_by_channel: Dict[str, List[Program]] = {}
        for p in self._programs:
            if p.channel_id not in self._programs_by_channel:
                self._programs_by_channel[p.channel_id] = []
            self._programs_by_channel[p.channel_id].append(p)
            
        # Mapeo por nombre normalizado (para fallback)
        self._programs_by_normalized_name: Dict[str, List[Program]] = {}
        if channel_names:
            for channel_id, name in channel_names.items():
                norm_name = normalize_name(name)
                if norm_name:
                    if norm_name not in self._programs_by_normalized_name:
                        self._programs_by_normalized_name[norm_name] = []
                    # Añadimos los programas asociados a ese ID a este nombre normalizado
                    self._programs_by_normalized_name[norm_name].extend(
                        self._programs_by_channel.get(channel_id, [])
                    )

    def get_programs_for_channel(self, channel_id: str) -> List[Program]:
        """Devuelve todos los programas para un canal específico, ordenados por tiempo."""
        filtered = self._programs_by_channel.get(channel_id, [])
        return sorted(filtered, key=lambda p: p.start_time)

    def get_programs_by_normalized_name(self, normalized_name: str) -> List[Program]:
        """Devuelve los programas buscando por el nombre normalizado del canal."""
        filtered = self._programs_by_normalized_name.get(normalized_name, [])
        return sorted(filtered, key=lambda p: p.start_time)

    def get_current_program(self, channel_id: str) -> Optional[Program]:
        """Devuelve el programa que se está emitiendo ahora para un canal."""
        programs = self._programs_by_channel.get(channel_id, [])
        for p in programs:
            if p.is_currently_airing():
                return p
        return None

    def get_current_program_by_normalized_name(self, normalized_name: str) -> Optional[Program]:
        """Devuelve el programa actual buscando por nombre normalizado."""
        programs = self._programs_by_normalized_name.get(normalized_name, [])
        for p in programs:
            if p.is_currently_airing():
                return p
        return None

    @property
    def programs(self) -> List[Program]:
        return list(self._programs)
