import json
import os
from datetime import datetime
from pathlib import Path
import time

class ChannelLogger:
    """
    Sistema de logging para el escaneo de canales IPTV.
    Guarda la información en formato JSON con detalles completos sobre cada canal.
    """
    
    def __init__(self, m3u_file, comments="", app_version="1.0.0", config=None):
        """
        Inicializa el sistema de logging.
        
        Args:
            m3u_file (str): Ruta al archivo M3U que se está escaneando
            comments (str): Comentarios adicionales sobre el archivo M3U
            app_version (str): Versión de la aplicación
            config (dict): Configuración utilizada para el escaneo
        """
        self.start_time = datetime.now()
        timestamp = self.start_time.strftime('%Y%m%d_%H%M%S')
        
        # Crear directorio de logs si no existe
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Nombre del archivo de log
        self.log_file = log_dir / f"channel_scanner_log_{timestamp}.json"
        
        # Configuración por defecto si no se proporciona
        if config is None:
            config = {
                "timeout_ms": 3000,
                "max_attempts": 3,
                "workers": 10,
                "exclude_filters": [],
                "include_filters": []
            }
        
        # Estructura inicial del log
        self.log_data = {
            "metadata": {
                "filename": os.path.basename(m3u_file),
                "file_path": str(m3u_file),
                "file_comments": comments,
                "app_version": app_version,
                "scan_start": self.start_time.isoformat(),
                "scan_end": None,
                "scan_duration_seconds": 0,
                "total_channels": 0,
                "config": config,
                "status": "in_progress"
            },
            "statistics": {
                "working_channels": 0,
                "failed_channels": 0,
                "excluded_channels": 0,
                "success_rate": 0,
                "average_response_time_ms": 0,
                "by_group": {}
            },
            "channels": []
        }
        
        # Guardar estructura inicial
        self._save_log()
        print(f"Archivo de log creado en: {self.log_file}")
    
    def add_channel(self, channel_info, is_included=True):
        """
        Añade un canal al log antes de su verificación.
        
        Args:
            channel_info (dict): Información del canal
            is_included (bool): Indica si el canal está incluido en la verificación
        
        Returns:
            int: Índice del canal en el array de canales
        """
        channel_entry = {
            "id": len(self.log_data["channels"]) + 1,
            "name": channel_info.get('tvg-name', 'Sin nombre'),
            "url": channel_info.get('url', ''),
            "group": channel_info.get('group-title', 'Sin grupo'),
            "logo_url": channel_info.get('tvg-logo', ''),
            "test_start": None,
            "test_end": None,
            "duration_ms": 0,
            "attempts": 0,
            "worker_id": None,
            "http_code": None,
            "content_type": None,
            "error": None,
            "message": "Pendiente de verificación",
            "is_working": None,
            "is_included": is_included
        }
        
        self.log_data["channels"].append(channel_entry)
        self.log_data["metadata"]["total_channels"] += 1
        
        if not is_included:
            self.log_data["statistics"]["excluded_channels"] += 1
            
        # Actualizar el log
        self._save_log()
        
        return len(self.log_data["channels"]) - 1  # Índice del canal añadido
    
    def start_channel_test(self, channel_index, worker_id):
        """
        Registra el inicio de la prueba de un canal.
        
        Args:
            channel_index (int): Índice del canal en el array
            worker_id (int): ID del worker que está procesando el canal
        """
        if 0 <= channel_index < len(self.log_data["channels"]):
            channel = self.log_data["channels"][channel_index]
            channel["test_start"] = datetime.now().isoformat()
            channel["worker_id"] = worker_id
            self._save_log()
    
    def update_channel_status(self, channel_index, is_working, http_code=None, 
                             content_type=None, error=None, message=None, attempts=1):
        """
        Actualiza el estado de un canal después de su verificación.
        
        Args:
            channel_index (int): Índice del canal en el array
            is_working (bool): Indica si el canal funciona correctamente
            http_code (int): Código de respuesta HTTP
            content_type (str): Tipo de contenido de la respuesta
            error (str): Mensaje de error si lo hay
            message (str): Mensaje descriptivo del estado
            attempts (int): Número de intentos realizados
        """
        if 0 <= channel_index < len(self.log_data["channels"]):
            channel = self.log_data["channels"][channel_index]
            
            # Actualizar información del canal
            end_time = datetime.now()
            channel["test_end"] = end_time.isoformat()
            
            # Calcular duración si hay tiempo de inicio
            if channel["test_start"]:
                start_time = datetime.fromisoformat(channel["test_start"])
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                channel["duration_ms"] = duration_ms
            
            channel["is_working"] = is_working
            channel["http_code"] = http_code
            channel["content_type"] = content_type
            channel["error"] = error
            channel["message"] = message
            channel["attempts"] = attempts
            
            # Actualizar estadísticas solo si el canal está incluido
            if channel["is_included"]:
                if is_working:
                    self.log_data["statistics"]["working_channels"] += 1
                else:
                    self.log_data["statistics"]["failed_channels"] += 1
                
                # Actualizar estadísticas por grupo
                group = channel["group"]
                if group not in self.log_data["statistics"]["by_group"]:
                    self.log_data["statistics"]["by_group"][group] = {"total": 0, "working": 0}
                
                self.log_data["statistics"]["by_group"][group]["total"] += 1
                if is_working:
                    self.log_data["statistics"]["by_group"][group]["working"] += 1
            
            # Actualizar tasa de éxito
            included_channels = self.log_data["metadata"]["total_channels"] - self.log_data["statistics"]["excluded_channels"]
            if included_channels > 0:
                verified_channels = self.log_data["statistics"]["working_channels"] + self.log_data["statistics"]["failed_channels"]
                if verified_channels > 0:
                    success_rate = (self.log_data["statistics"]["working_channels"] / verified_channels) * 100
                    self.log_data["statistics"]["success_rate"] = round(success_rate, 2)
            
            # Actualizar tiempo de respuesta promedio
            response_times = [ch["duration_ms"] for ch in self.log_data["channels"] 
                             if ch["is_included"] and ch["duration_ms"] > 0]
            if response_times:
                self.log_data["statistics"]["average_response_time_ms"] = round(sum(response_times) / len(response_times), 2)
            
            self._save_log()
    
    def finalize(self, status="completed"):
        """
        Finaliza el log con estadísticas completas.
        
        Args:
            status (str): Estado final del escaneo ('completed', 'interrupted', etc.)
        """
        end_time = datetime.now()
        self.log_data["metadata"]["scan_end"] = end_time.isoformat()
        self.log_data["metadata"]["scan_duration_seconds"] = int((end_time - self.start_time).total_seconds())
        self.log_data["metadata"]["status"] = status
        
        self._save_log()
        print(f"Log finalizado con estado: {status}")
        return self.log_file
    
    def export_to_csv(self, output_file=None):
        """
        Exporta los datos del log a formato CSV.
        
        Args:
            output_file (str): Ruta al archivo CSV de salida
        
        Returns:
            str: Ruta al archivo CSV generado
        """
        import csv
        
        if output_file is None:
            output_file = str(self.log_file).replace('.json', '.csv')
        
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'id', 'name', 'url', 'group', 'is_included', 'is_working', 
                'http_code', 'message', 'attempts', 'duration_ms', 'worker_id'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for channel in self.log_data["channels"]:
                # Crear un diccionario con solo los campos necesarios
                row = {field: channel.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        print(f"Datos exportados a CSV: {output_file}")
        return output_file
    
    def _save_log(self):
        """Guarda los datos actuales en el archivo de log."""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.log_data, f, ensure_ascii=False, indent=2)
    
    def get_log_file(self):
        """Retorna la ruta al archivo de log."""
        return self.log_file
    
    def get_statistics(self):
        """Retorna las estadísticas actuales."""
        return self.log_data["statistics"]

# Función auxiliar para extraer comentarios de un archivo M3U
def extract_m3u_comments(m3u_file):
    """
    Extrae los comentarios de la cabecera de un archivo M3U.
    
    Args:
        m3u_file (str): Ruta al archivo M3U
    
    Returns:
        str: Comentarios encontrados en la cabecera
    """
    comments = []
    try:
        with open(m3u_file, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                # Si la línea comienza con # pero no es una directiva M3U, es un comentario
                if line.startswith('#') and not line.startswith('#EXT'):
                    comments.append(line)
                # Si encontramos la primera entrada de canal, terminamos
                elif line.startswith('#EXTINF'):
                    break
    except Exception as e:
        print(f"Error al extraer comentarios: {e}")
    
    return "\n".join(comments)

# Ejemplo de uso:
if __name__ == "__main__":
    # Este código se ejecuta solo si se ejecuta el archivo directamente
    # Sirve como ejemplo y para pruebas
    
    m3u_file = "example.m3u"
    comments = "Archivo de ejemplo para pruebas"
    
    # Configuración de ejemplo
    config = {
        "timeout_ms": 3000,
        "max_attempts": 3,
        "workers": 5,
        "exclude_filters": ["adult", "xxx"],
        "include_filters": ["sports", "news"]
    }
    
    # Crear logger
    logger = ChannelLogger(m3u_file, comments, config=config)
    
    # Simular añadir canales
    channel1_index = logger.add_channel({
        'tvg-name': 'Canal Deportes',
        'url': 'http://example.com/stream1',
        'group-title': 'Deportes',
        'tvg-logo': 'http://example.com/logo1.png'
    })
    
    channel2_index = logger.add_channel({
        'tvg-name': 'Canal Adultos',
        'url': 'http://example.com/stream2',
        'group-title': 'Adultos',
        'tvg-logo': 'http://example.com/logo2.png'
    }, is_included=False)
    
    # Simular inicio de prueba
    logger.start_channel_test(channel1_index, worker_id=1)
    
    # Simular espera
    time.sleep(1)
    
    # Simular actualización de estado
    logger.update_channel_status(
        channel1_index, 
        is_working=True,
        http_code=200,
        content_type="application/vnd.apple.mpegurl",
        message="Stream directo",
        attempts=1
    )
    
    # Finalizar log
    logger.finalize()
    
    # Exportar a CSV
    logger.export_to_csv()
    
    print("Ejemplo completado.")
