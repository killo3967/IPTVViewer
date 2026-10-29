import logging
from datetime import datetime

from src.domain.entities.epg import EPGData, Program, normalize_name
from src.domain.ports.i_epg_repo import IEPGRepository


class EPGManager:
    """Servicio de aplicación para gestionar la guía de programación (EPG)."""
    
    def __init__(self, repository: IEPGRepository):
        self._repository = repository
        self._epg_data = EPGData()

    def update_epg(self, source: str):
        """Descarga y actualiza los datos de la EPG desde la fuente configurada."""
        if not source:
            return
        logging.info(f"Actualizando EPG desde: {source}")
        self._epg_data = self._repository.load_epg(source)

    def get_currently_airing(self, tvg_id: str, channel_name: str = "") -> Program | None:
        """Obtiene el programa actual con fallback por nombre normalizado."""
        if not tvg_id and not channel_name: return None
        
        # 1. Intentar por ID
        program = self._epg_data.get_current_program(tvg_id)
        if program:
            return program
            
        # 2. Fallback por nombre normalizado
        if channel_name:
            norm_name = normalize_name(channel_name)
            return self._epg_data.get_current_program_by_normalized_name(norm_name)
            
        return None

    def get_program_schedule(self, tvg_id: str, channel_name: str = "") -> list[Program]:
        """Obtiene la lista de programas con fallback por nombre normalizado."""
        if not tvg_id and not channel_name: return []
        
        # 1. Intentar por ID
        programs = self._epg_data.get_programs_for_channel(tvg_id)
        if programs:
            return programs
            
        # 2. Fallback por nombre normalizado
        if channel_name:
            norm_name = normalize_name(channel_name)
            return self._epg_data.get_programs_by_normalized_name(norm_name)
            
        return []

    def get_next_program(self, tvg_id: str, channel_name: str = "") -> Program | None:
        """Obtiene el siguiente programa, el primero que empieza después de ahora.

        Devuelve ``None`` si la guía no cubre más horas que la actual.
        """
        return self.get_current_and_next(tvg_id, channel_name)[1]

    def get_current_and_next(
        self, tvg_id: str, channel_name: str = ""
    ) -> tuple[Program | None, Program | None]:
        """Devuelve ``(programa en curso, siguiente)`` con una sola consulta.

        La ventana pide los dos datos por fila y cada 30 s: resolverlos en dos
        llamadas recorrería y ordenaría la lista del canal dos veces. Aquí se
        recorre una sola vez ``get_program_schedule()``, que ya viene ordenada y
        con el fallback por nombre normalizado.
        """
        now = datetime.now()
        current: Program | None = None
        upcoming: Program | None = None

        for program in self.get_program_schedule(tvg_id, channel_name):
            if current is None and program.start_time <= now <= program.end_time:
                current = program
                continue
            if program.start_time > now:
                upcoming = program
                break

        return current, upcoming

    @property
    def has_data(self) -> bool:
        return len(self._epg_data.programs) > 0
