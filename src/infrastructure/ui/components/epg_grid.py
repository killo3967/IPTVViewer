from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
    QHeaderView, QLabel, QWidget, QHBoxLayout
)
from PyQt6.QtCore import Qt, QDateTime
from src.application.services.epg_manager import EPGManager
from src.domain.entities.playlist import Playlist
from datetime import datetime, timedelta

class EPGGridDialog(QDialog):
    """Diálogo que muestra la parrilla de programación completa."""
    
    def __init__(self, epg_manager: EPGManager, playlist: Playlist, parent=None):
        super().__init__(parent)
        self._epg_manager = epg_manager
        self._playlist = playlist
        
        self.setWindowTitle("Parrilla de Programación (EPG)")
        self.resize(1000, 600)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Cabecera con Info
        info_label = QLabel("Guía de programación para las próximas 24 horas")
        info_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(info_label)
        
        # Tabla de Parrilla
        self.table = QTableWidget()
        layout.addWidget(self.table)
        
        self._populate_grid()

    def _populate_grid(self):
        # Definir el rango de tiempo (ahora + 24 horas en bloques de 30 min)
        start_time = datetime.now().replace(minute=0, second=0, microsecond=0)
        time_slots = []
        for i in range(48): # 24 horas
            time_slots.append(start_time + timedelta(minutes=30 * i))
            
        self.table.setColumnCount(len(time_slots))
        self.table.setRowCount(len(self._playlist))
        
        # Cabeceras Horizontales (Tiempo)
        headers = [t.strftime("%H:%M") for t in time_slots]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Cabeceras Verticales (Canales)
        channel_names = [channel.name for channel in self._playlist]
        self.table.setVerticalHeaderLabels(channel_names)
        
        # Rellenar Datos
        for row, channel in enumerate(self._playlist):
            programs = self._epg_manager.get_program_schedule(channel.tvg_id, channel.name)
            if not programs:
                continue
                
            for col, slot_time in enumerate(time_slots):
                # Buscar programa que coincida con este slot
                prog = self._find_program_at(programs, slot_time)
                if prog:
                    item = QTableWidgetItem(prog.title)
                    item.setToolTip(f"{prog.title}\n{prog.start_time.strftime('%H:%M')} - {prog.end_time.strftime('%H:%M')}\n\n{prog.description or ''}")
                    self.table.setItem(row, col, item)

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def _find_program_at(self, programs, time_slot):
        """Busca si hay un programa emitiéndose en un momento dado."""
        for p in programs:
            if p.start_time <= time_slot < p.end_time:
                return p
        return None
