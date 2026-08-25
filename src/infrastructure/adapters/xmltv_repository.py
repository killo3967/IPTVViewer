import gzip
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

import requests

from src.domain.entities.epg import EPGData, Program
from src.domain.ports.i_epg_repo import IEPGRepository


class XMLTVRepository(IEPGRepository):
    """Adaptador de infraestructura para cargar datos EPG desde archivos XMLTV."""

    def load_epg(self, source: str) -> EPGData:
        """Carga, descarga y parsea una fuente XMLTV."""
        try:
            content = self._get_content(source)
            if not content:
                return EPGData()
            return self._parse_xmltv(content)
        except Exception as e:
            logging.error(f"Error cargando EPG desde {source}: {e}")
            return EPGData()

    def _get_content(self, source: str) -> bytes:
        """Descarga el contenido, gestionando archivos comprimidos .gz."""
        if source.startswith('http'):
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(source, headers=headers, timeout=20)
                response.raise_for_status()
                data = response.content
            except Exception as e:
                logging.error(f"Error descargando EPG remota: {e}")
                return b""
        else:
            path = Path(source)
            if not path.exists():
                return b""
            with open(path, 'rb') as f:
                data = f.read()

        # Descomprimir si es GZIP
        if source.endswith('.gz') or data.startswith(b'\x1f\x8b'):
            try:
                return gzip.decompress(data)
            except Exception as e:
                logging.error(f"Error descomprimiendo GZIP: {e}")
                return b""
        
        return data

    def _parse_xmltv(self, content: bytes) -> EPGData:
        """Parsea la estructura XMLTV."""
        programs = []
        channel_names = {}
        try:
            root = ET.fromstring(content)
            
            # 1. Mapear IDs de canales a nombres
            for chan_elem in root.findall('channel'):
                chan_id = chan_elem.get('id')
                display_name = chan_elem.find('display-name')
                if chan_id and display_name is not None:
                    channel_names[chan_id] = display_name.text or ""

            # 2. Parsear programas
            for prog_elem in root.findall('programme'):
                channel_id = prog_elem.get('channel')
                start_str = prog_elem.get('start')
                end_str = prog_elem.get('stop')
                
                if not channel_id or not start_str or not end_str:
                    continue

                title_elem = prog_elem.find('title')
                title = (title_elem.text or "Sin título") if title_elem is not None else "Sin título"
                
                desc_elem = prog_elem.find('desc')
                description = desc_elem.text if desc_elem is not None else ""
                
                cat_elem = prog_elem.find('category')
                category = cat_elem.text if cat_elem is not None else "Otros"

                programs.append(Program(
                    title=title,
                    start_time=self._parse_date(start_str),
                    end_time=self._parse_date(end_str),
                    channel_id=channel_id,
                    description=description,
                    category=category
                ))
            
            logging.info(f"EPG parseada: {len(programs)} programas y {len(channel_names)} canales mapeados.")
            return EPGData(programs, channel_names)
        except Exception as e:
            logging.error(f"Error parseando XMLTV: {e}")
            return EPGData()

    def _parse_date(self, date_str: str) -> datetime:
        """Convierte fechas estándar XMLTV (YYYYMMDDHHMMSS +HHMM) a datetime."""
        # Ejemplo: 20260305110000 +0100
        # Tomamos los primeros 14 carácteres para simplificar (ignorando zona horaria por ahora)
        clean_date = date_str.split(' ')[0][:14]
        return datetime.strptime(clean_date, "%Y%m%d%H%M%S")
