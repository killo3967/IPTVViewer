import sys
import re
import vlc
import logging
import queue  
import gc
from datetime import datetime
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QMutex  # Añade QMutex aquí
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QSplitter, QWidget, QVBoxLayout, QLabel, QProgressBar  # Añade QLabel y QProgressBar
from PyQt6.QtGui import QColor, QPixmap  
from PyQt6.QtCore import QTimer
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtCore import QObject, QUrl

SCRIPT_DIR = Path(__file__).parent.absolute()
M3U_FILE = SCRIPT_DIR / 'm3u/tv_channel_410339009578.ozcAEX04CT.m3u'
FILTER_GROUP = "SPAIN"  # Puedes cambiarlo a "" para no aplicar ningún filtro
# Configuración del número máximo de hilos trabajadores
NUM_WORKER_THREADS = 5  # Temporalmente para diagnóstico

# Configuración de timeout y reintentos
TIMEOUT_MS = 20000  # Timeout general en ms (10 segundos)
RETRY_DELAY_MS = 1000  # Delay entre reintentos en ms (1 segundo)
MAX_ATTEMPTS = 10 # Limitado a 5 intentos para acelerar el proceso

def setup_logger():
    # Usamos SCRIPT_DIR que ya tenemos definido
    log_file = SCRIPT_DIR / f"channel_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logging.basicConfig(
        filename=str(log_file),  # Convertimos a string para logging
        level=logging.INFO,
        format='%(message)s',
        encoding='utf-8'
    )
    print(f"Archivo de log creado en: {log_file}")  # Informamos al usuario
    return log_file

class ChannelWorker(QThread):
    channel_checked = pyqtSignal(int, bool, str)
    worker_finished = pyqtSignal(int)  # Señal para indicar que el worker ha terminado
    
    def __init__(self, channel_queue, worker_id):
        super().__init__()
        self.channel_queue = channel_queue
        self.worker_id = worker_id
        self.running = True
        print(f"Trabajador {worker_id} inicializado")
        
    def run(self):
        print(f"Worker {self.worker_id} iniciando ejecución")
        print(f"Tamaño de la cola: {self.channel_queue.qsize()} canales")

        while self.running:
            try:
                # Intentar obtener un canal de la cola
                try:
                    row, channel_info, url = self.channel_queue.get(timeout=0.5)
                    print(f"Worker {self.worker_id} obtuvo canal {row} de la cola: {url[:50]}...")
                except queue.Empty:
                    print(f"Worker {self.worker_id}: Cola vacía, terminando")
                    break
                
                # Verificar que la URL sea válida
                if not url or url.startswith('#'):
                    print(f"URL no válida para canal {row}: {url}")
                    self.channel_checked.emit(row, False, "URL no válida")
                    self.channel_queue.task_done()
                    continue
                    
                print(f"Trabajador {self.worker_id} verificando canal en fila {row}: {channel_info['tvg-name']}")
                
                # Crear un checker para este canal
                checker = ChannelChecker(url, row)
                
                # Variables para controlar la verificación
                verification_done = False
                max_verification_time = 30  # Tiempo máximo en segundos
                start_time = datetime.now()
                
                # Conectar señales
                def on_channel_checked(row, is_working, message):
                    nonlocal verification_done
                    print(f"Trabajador {self.worker_id}: Canal {row} verificado con resultado: {is_working}")
                    verification_done = True
                
                checker.channel_checked.connect(self.forward_result)
                checker.channel_checked.connect(on_channel_checked)
                
                # Iniciar verificación
                checker.check()
                
                # Esperar hasta que termine la verificación o se alcance el tiempo máximo
                while not verification_done and (datetime.now() - start_time).total_seconds() < max_verification_time and self.running:
                    QThread.msleep(100)  # Dormir para no consumir CPU
                    QApplication.processEvents()  # Procesar eventos de la cola de eventos
                
                # Si no terminó por sí mismo, forzar timeout
                if not verification_done:
                    print(f"Forzando timeout para canal {row} después de {max_verification_time} segundos")
                    checker.handle_timeout()
                
                # Limpiar el checker
                checker.cleanup()
                
                # Marcar la tarea como completada
                self.channel_queue.task_done()
                    
            except Exception as e:
                print(f"Error en trabajador {self.worker_id}: {e}")

        print(f"Trabajador {self.worker_id} finalizado")
        self.worker_finished.emit(self.worker_id)
        
    def forward_result(self, row, is_working, message):
        self.channel_checked.emit(row, is_working, message)
        
    def stop(self):
        self.running = False

class ChannelChecker(QObject):
    channel_checked = pyqtSignal(int, bool, str)
    
    def __init__(self, url, row):
        super().__init__()
        self.url = url
        self.row = row
        self.nam = QNetworkAccessManager()
        self.timeout_timer = QTimer()                              
        self.timeout_timer.setSingleShot(True)                    
        self.timeout_timer.timeout.connect(self.handle_timeout)    
        self.response_processed = False
    
        # Configuración de tiempos (usando variables globales)
        self.timeout = TIMEOUT_MS
        self.retry_delay = RETRY_DELAY_MS
        self.max_attempts = MAX_ATTEMPTS
    
        # Contadores e inicialización
        self.current_attempt = 0
        self.retry_timer = QTimer()
        self.retry_timer.setSingleShot(True)  
        self.retry_timer.timeout.connect(self.check)
    
        print(f"Canal {row}: Configurado con {self.max_attempts} intentos máximos (timeout={self.timeout}ms, delay={self.retry_delay}ms)")        

    def check(self):
        # Si existe una solicitud anterior, intenta cancelarla de manera segura
        try:
            if hasattr(self, 'current_reply') and self.current_reply:
                try:
                    if not self.current_reply.isFinished():
                        self.current_reply.abort()
                except RuntimeError:
                    pass
            
                try:
                    self.current_reply.deleteLater()
                except RuntimeError:
                    pass
            
                # Eliminamos la referencia en Python
                self.current_reply = None
        except Exception as e:
            print(f"Error al limpiar solicitud anterior: {e}")

        # Solo reinicia el contador si es un nuevo chequeo (no un reintento)
        if self.response_processed:
            self.current_attempt = 0

        # Preparación de estado y solicitud:    
        self.response_processed = False

        # Crea una solicitud HTTP con la URL del canal
        try:
            url = QUrl(self.url)
            if not url.isValid():
                print(f"URL no válida para canal {self.row}: {self.url}")
                self.response_processed = True
                self.channel_checked.emit(self.row, False, "URL no válida")
                return
                
            request = QNetworkRequest(url)
            request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, 'VLC/3.0.0')
            request.setRawHeader(b"Accept", b"*/*")

            print(f"\nVerificando canal en fila {self.row} - Intento {self.current_attempt + 1}")
            print(f"URL: {self.url}")

            # Ejecuta la solicitud GET
            self.current_reply = self.nam.get(request)
            
            # Asegurarse de limpiar conexiones previas
            try:
                self.current_reply.finished.disconnect()
            except Exception:
                pass
            
            # Establecer la conexión y confirmar
            self.current_reply.finished.connect(self.handle_response)
            print(f"Conexión establecida para respuesta HTTP - Canal {self.row}")
            
            # Iniciar el timer de timeout y confirmar
            self.timeout_timer.start(self.timeout)
            print(f"Timer de timeout iniciado ({self.timeout}ms) - Canal {self.row}")
            
        except Exception as e:
            print(f"Error al crear solicitud HTTP para canal {self.row}: {e}")
            self.response_processed = True
            self.channel_checked.emit(self.row, False, f"Error: {str(e)}")

    def handle_response(self):
        if self.response_processed:
            return
        
        print(f"Procesando respuesta: Intento {self.current_attempt + 1} para canal {self.row}")
        
        self.timeout_timer.stop()
        
        # Verificar que el reply aún existe y es válido
        if not hasattr(self, 'current_reply') or not self.current_reply:
            print(f"Error: El objeto reply ya no existe para el canal {self.row}")
            self.response_processed = True
            self.channel_checked.emit(self.row, False, "Error interno: objeto de respuesta no disponible")
            return
            
        reply = self.current_reply
        
        # Capturar todos los datos necesarios del reply antes de cualquier operación que pueda eliminarlo
        try:
            status_code = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            content_type = reply.header(QNetworkRequest.KnownHeaders.ContentTypeHeader)
            
            # Guardar una copia local de los datos que necesitamos
            status_code = status_code if status_code is not None else 0
            content_type = content_type if content_type is not None else "Desconocido"
            
            print(f"Status: {status_code}, Content-Type: {content_type}")
            
            is_valid = False
            
            # Clasificación por rangos de códigos HTTP
            if 100 <= status_code < 200:
                is_valid = True
                message = "Respuesta informativa"
            elif 200 <= status_code < 300:
                is_valid = True
                message = "Stream directo"
            elif 300 <= status_code < 400:
                is_valid = True
                message = "Redirección"
            elif 400 <= status_code < 500:
                # Excepciones para errores de cliente que consideramos válidos
                if status_code == 406:
                    is_valid = True
                    message = "Requiere configuración especial"
                else:
                    message = f"Error del cliente: {status_code}"
            elif 500 <= status_code < 600:
                # Excepciones para errores de servidor que consideramos válidos
                if status_code in [502, 503]:
                    is_valid = True
                    message = "Servidor ocupado"
                else:
                    message = f"Error del servidor: {status_code}"
            else:
                message = f"Estado desconocido: {status_code}"
                
        except RuntimeError as e:
            print(f"Error al acceder al objeto reply para canal {self.row}: {e}")
            self.response_processed = True
            self.channel_checked.emit(self.row, False, f"Error: {str(e)}")
            # Asegurarse de limpiar el reply si aún existe
            try:
                if hasattr(self, 'current_reply') and self.current_reply:
                    self.current_reply.deleteLater()
            except Exception:
                pass
            return
        
        # Aumentar contador de intentos
        self.current_attempt += 1
        
        # Decidir si reintentar o finalizar
        if is_valid or self.current_attempt >= self.max_attempts:
            # No más reintentos: emitir señal con resultado final
            self.response_processed = True
            log_message = f"Canal {self.row:03d} | Estado: {status_code:03d} | Tipo: {str(content_type)[:20]:<20} | {message} | Intentos: {self.current_attempt}"
            logging.info(log_message)
            
            print(f"EMITIENDO SEÑAL FINAL: Canal {self.row} | is_valid={is_valid} | message={message}")
            self.channel_checked.emit(self.row, is_valid, message)
        else:
            # Programar otro intento después del delay
            print(f"Intento {self.current_attempt} fallido para canal {self.row}, reintentando en {self.retry_delay}ms...")
            self.retry_timer.start(self.retry_delay)
        
        # Asegurarse de limpiar el reply correctamente
        try:
            reply.deleteLater()
        except Exception as e:
            print(f"Error al eliminar reply: {e}")
        
            
    def handle_timeout(self):
        print(f"TIMEOUT EJECUTADO para canal {self.row}")
        
        if self.response_processed:
            print(f"Canal {self.row}: Respuesta ya procesada, ignorando timeout")
            return
        
        self.response_processed = True
        print(f"TIMEOUT para canal {self.row} después de {self.current_attempt + 1} intentos")
        self.channel_checked.emit(self.row, False, f"Timeout después de {self.current_attempt + 1} intentos")
        
        try:
            if hasattr(self, 'current_reply') and self.current_reply:
                if not self.current_reply.isFinished():
                    print(f"Abortando solicitud HTTP para canal {self.row}")
                    self.current_reply.abort()
        except Exception as e:
            print(f"Error al abortar solicitud HTTP: {e}")
                
    def cleanup(self):
        print(f"Limpiando recursos para canal {self.row}")
        
        # Detener timers
        if hasattr(self, 'timeout_timer') and self.timeout_timer:
            self.timeout_timer.stop()
            self.timeout_timer.deleteLater()
            self.timeout_timer = None
            
        if hasattr(self, 'retry_timer') and self.retry_timer:
            self.retry_timer.stop()
            self.retry_timer.deleteLater()
            self.retry_timer = None
        
        # Limpiar reply
        if hasattr(self, 'current_reply') and self.current_reply:
            try:
                self.current_reply.finished.disconnect()
            except Exception:
                pass
                
            try:
                if not self.current_reply.isFinished():
                    self.current_reply.abort()
                self.current_reply.deleteLater()
            except Exception as e:
                print(f"Error al limpiar reply: {e}")
            
            self.current_reply = None
        
        # Limpiar network manager
        if hasattr(self, 'nam') and self.nam:
            self.nam.deleteLater()
            self.nam = None

            
            
class IPTVViewer(QMainWindow):
    def __init__(self):
        print("Iniciando IPTVViewer...")
        super().__init__()
        log_file = setup_logger()
    
        # Inicializaciones importantes primero
        self.logo_cache = {}
        self.max_cached_logos = 50
        self.checkers = []  # Inicialización de la lista de checkers
    
        # Variables para el sistema multihilo
        self.workers = []
        self.channel_queue = queue.Queue()
        self.active_workers = 0  # Contador de trabajadores activos
        self.total_channels = 0
        self.verified_channels = 0
        self.queue_mutex = QMutex()
    
        self.setWindowTitle("IPTV España Checker")
        print("Configurando ventana principal...")

        # Primero crea el widget central
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        # Luego crea un único layout principal
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Crea y añade el splitter primero (antes de la barra de progreso)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_layout.addWidget(self.splitter, 1) # Le damos más espacio con stretch factor 1
    
        
        print("Layout configurado...")

        # Tabla
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Canal", "Logo", "Estado"])
        self.splitter.addWidget(self.table)

        # Configuración de las columnas
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    
        # Configuración adicional de la tabla
        self.table.setWordWrap(True)
        self.table.verticalHeader().setDefaultSectionSize(50)
        print("Tabla configurada...")
        
        # Añadir conexión de señales para la tabla
        self.table.itemClicked.connect(self.play_channel)

        # Configuración del reproductor VLC
        self.instance = vlc.Instance()
        self.player = self.instance.media_player_new()
        
        # Widget para el reproductor
        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background-color: black;")
        self.splitter.addWidget(self.video_widget)
        
        # Importante: establecer el widget de video después de crear el player
        if sys.platform == "win32":
            self.player.set_hwnd(int(self.video_widget.winId()))
        else:
            self.player.set_xwindow(int(self.video_widget.winId()))
            
            
        # Ahora añade la barra de progreso al final (abajo) y más estrecha
        self.progress_layout = QVBoxLayout()
        self.progress_layout.setContentsMargins(10, 0, 10, 5)  # Márgenes reducidos
        self.progress_label = QLabel("Verificando canales...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setMaximumHeight(15)  # Altura reducida para la barra
        self.progress_label.setMaximumHeight(20)  # Altura reducida para la etiqueta
        
        # Añadir widgets al layout de progreso
        self.progress_layout.addWidget(self.progress_label)
        self.progress_layout.addWidget(self.progress_bar)
        
        # Añadir el layout de progreso al layout principal con stretch factor 0 (no se expande)
        self.main_layout.addLayout(self.progress_layout, 0)

        # Configuración explícita de visibilidad
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setGeometry(100, 100, 1200, 600)

        if not M3U_FILE.exists():
            print(f"Archivo no encontrado: {M3U_FILE}")
            self.show_error_message()
            return
        
        print("Cargando canales...")
        self.load_channels()
        print("Canales cargados...")

    def closeEvent(self, event):
        print("Iniciando cierre de aplicación...")

        # Detener workers
        for worker in self.workers:
            if worker.isRunning():
                worker.stop()
                worker.wait(1000)  # Esperar máximo 1 segundo
    
        # Limpiar workers
        self.workers.clear()
    
        # Detener checkers
        for checker in self.checkers[:]:
            checker.cleanup()
    
        # Limpiar checkers
        self.checkers.clear()
    
        # Limpiar VLC
        if self.player:
            self.player.stop()
            self.player.release()
            self.player = None
    
        if self.instance:
            self.instance.release()
            self.instance = None
    
        super().closeEvent(event)
        print("Aplicación cerrada correctamente")

    def update_status(self, row, is_working, message):
        print(f"ACTUALIZANDO UI: Fila {row} | is_working={is_working} | message={message}")
    
        try:
            # Actualizar el contador de canales verificados
            self.verified_channels += 1
            progress = int((self.verified_channels / self.total_channels) * 100)
            self.progress_bar.setValue(progress)
            self.progress_label.setText(f"Verificando {self.verified_channels}/{self.total_channels} canales")
        
            # Actualizar estado en la tabla
            status_item = self.table.item(row, 2)  # Obtiene el item de la columna de estado
    
            # Verifica si el item existe antes de modificarlo
            if status_item is None:
                return
    
            if is_working:
                status_item.setText("Funcionando")
                status_item.setBackground(QColor(144, 238, 144))  # Verde claro
            else:
                if "Sin señal" in message:
                    status_item.setText("Sin señal")
                    status_item.setBackground(QColor(255, 255, 0))  # Amarillo
                else:
                    status_item.setText("No funciona")
                    status_item.setBackground(QColor(255, 99, 71))  # Rojo
        except Exception as e:
            print(f"Error actualizando estado: {e}")
            
    def play_channel(self, item):
        print("=== Iniciando reproducción ===")
        row = item.row()
        url = self.table.item(row, 1).data(Qt.ItemDataRole.UserRole)  # Obtener URL del UserRole
        channel_name = self.table.item(row, 0).text()
        print(f"Reproduciendo canal: {channel_name}")
        print(f"URL: {url}")

        # Detener reproducción actual y limpiar
        self.player.stop()
        self.player.release()
    
        # Crear nueva instancia para cada reproducción
        self.player = self.instance.media_player_new()
    
        # Reconectar al widget
        if sys.platform == "win32":
            self.player.set_hwnd(int(self.video_widget.winId()))
        else:
            self.player.set_xwindow(int(self.video_widget.winId()))

        # Crear y configurar media
        media = self.instance.media_new(url)
        media.add_option(":network-caching=3000")  # Buffer más grande
        media.add_option(":live-caching=3000")
        media.add_option(":file-caching=3000")
        media.add_option(":no-video-title-show")
        media.add_option(":input-repeat=0")
        media.add_option(":rtsp-tcp")  # Forzar TCP para RTSP
        media.add_option(":http-reconnect")  # Reconexión automática
    
        # Asignar media y reproducir
        self.player.set_media(media)
    
        # Reproducir y verificar resultado
        result = self.player.play()
        print(f"Estado de reproducción: {result}")
    
        # Verificar estado después de un breve delay
        QTimer.singleShot(1000, self.check_playback_status)

   
    def check_playback_status(self):
        state = self.player.get_state()
        print(f"Estado del reproductor: {state}")
        if state == vlc.State.Error:
            print("Error en la reproducción")
        elif state == vlc.State.Playing:
            print("Reproducción iniciada correctamente")
            
            
    def load_channels(self):
        channels = []
    
        with open(M3U_FILE, 'r', encoding='utf-8') as file:
            content = file.readlines()
        
        # Limpiar la tabla
        self.table.setRowCount(0)

        # En lugar de verificar inmediatamente, guardar los canales a verificar
        pending_channels = []
    
        # Procesar el archivo para extraer URLs reales, ignorando las opciones
        i = 0
        while i < len(content):
            line = content[i].strip()
            if line.startswith('#EXTINF'):
                channel_info = {}
                fields = {
                    'tvg-id': r'tvg-id="(.*?)"',
                    'tvg-name': r'tvg-name="(.*?)"',
                    'tvg-logo': r'tvg-logo="(.*?)"',
                    'group-title': r'group-title="(.*?)"'
                }
        
                for field, pattern in fields.items():
                    match = re.search(pattern, line)
                    channel_info[field] = match.group(1) if match else ""
            
                # Buscar la URL real (saltando líneas EXTVLCOPT)
                url = ""
                j = i + 1
                while j < len(content) and (content[j].strip().startswith('#') or not content[j].strip()):
                    j += 1
                
                if j < len(content):
                    url = content[j].strip()
                
                # Aplicar el filtro por grupo
                if not FILTER_GROUP or channel_info['group-title'] == FILTER_GROUP:
                    if url and not url.startswith('#EXTVLCOPT'):
                        print(f"Canal encontrado: {channel_info['tvg-name']} - Grupo: {channel_info['group-title']}")
                        # Añadir a la lista pendiente en lugar de verificar
                        pending_channels.append((channel_info, url))
                    else:
                        print(f"Saltando canal {channel_info['tvg-name']} - URL no válida: {url}")
            
                i = j
            else:
                i += 1

        print(f"Encontrados {len(pending_channels)} canales del grupo {FILTER_GROUP}")

        # Inicializar la barra de progreso
        self.total_channels = len(pending_channels)
        self.verified_channels = 0
        self.progress_bar.setValue(0)
        self.progress_label.setText(f"Verificando 0/{self.total_channels} canales")
    
        # Añadir todos los canales a la tabla primero
        for index, (channel_info, url) in enumerate(pending_channels):
            self.add_channel_to_table(channel_info, url, index)

        # Ahora añadir todos los canales a la cola para verificación
        for index, (channel_info, url) in enumerate(pending_channels):
            self.channel_queue.put((index, channel_info, url))

        # Iniciar los workers
        self.start_workers()
    
    def start_workers(self):
        """Inicia los hilos trabajadores para verificar canales"""
        print(f"Iniciando {NUM_WORKER_THREADS} trabajadores para verificación de canales")
        
        # Limpia los workers anteriores si existen
        for worker in self.workers:
            if worker.isRunning():
                worker.stop()
                worker.wait()
        
        self.workers = []
        self.active_workers = 0
        
        # Crea y arranca nuevos workers
        for i in range(NUM_WORKER_THREADS):
            worker = ChannelWorker(self.channel_queue, i)
            worker.channel_checked.connect(self.update_status, Qt.ConnectionType.QueuedConnection)
            worker.worker_finished.connect(self.on_worker_finished)
            self.workers.append(worker)
            worker.start()
            self.active_workers += 1
    
    def on_worker_finished(self, worker_id):
        """Maneja la finalización de un trabajador"""
        print(f"Trabajador {worker_id} ha finalizado")
        self.active_workers -= 1
        
        # Si todos los workers han terminado, mostrar mensaje
        if self.active_workers == 0:
            print("Todos los canales han sido verificados")
            self.progress_label.setText(f"Verificación completada: {self.verified_channels}/{self.total_channels} canales")
            # Forzar recolección de basura
            gc.collect()    
    
    
    def add_channel_to_table(self, channel_info, url, row):
      self.table.setRowCount(row + 1)

      # Nombre del canal
      display_name = channel_info['tvg-name'] or channel_info['tvg-id'] or "Sin nombre"
      channel_item = QTableWidgetItem(display_name)
      self.table.setItem(row, 0, channel_item)
    
      # Logo en columna 1
      logo_url = channel_info.get('tvg-logo', '')
      logo_item = QTableWidgetItem()
      logo_item.setData(Qt.ItemDataRole.UserRole, url)  # Store stream URL
      self.table.setItem(row, 1, logo_item)
    
      # Cargar el logo si existe
      if logo_url:
          self.load_logo(logo_url, row, 1)
    
      # Estado en columna 2
      status_item = QTableWidgetItem("Pendiente...")
      status_item.setBackground(QColor(255, 255, 224))
      self.table.setItem(row, 2, status_item)
      
    def load_logo(self, logo_url, row, column):
        if logo_url in self.logo_cache:
            pixmap = self.logo_cache[logo_url]
            self.set_logo_in_table(pixmap, row, column)
            return

        request = QNetworkRequest(QUrl(logo_url))
        nam = QNetworkAccessManager()
        reply = nam.get(request)

        def handle_logo_response():
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = reply.readAll()
                pixmap = QPixmap()
                pixmap.loadFromData(data)

                if not pixmap.isNull():
                    pixmap = pixmap.scaled(40, 30, Qt.AspectRatioMode.KeepAspectRatio, 
                                         Qt.TransformationMode.SmoothTransformation)
                    
                    if len(self.logo_cache) >= self.max_cached_logos:
                        self.logo_cache.pop(next(iter(self.logo_cache)))
                    self.logo_cache[logo_url] = pixmap
                    
                    self.set_logo_in_table(pixmap, row, column)
            reply.deleteLater()
            
        reply.finished.connect(handle_logo_response)

    def set_logo_in_table(self, pixmap, row, column):
        if not pixmap.isNull():
            item = self.table.item(row, column)
            if item:
                url = item.data(Qt.ItemDataRole.UserRole)
                item.setData(Qt.ItemDataRole.DecorationRole, pixmap)
                item.setData(Qt.ItemDataRole.UserRole, url)
    def show_error_message(self):
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText("Error al cargar el archivo")
        msg.setInformativeText(f"Archivo no encontrado en:\n{M3U_FILE}\n\nPor favor, verifica que:")
        msg.setDetailedText(f"""
        1. El archivo existe en: {M3U_FILE}
        2. El nombre es exactamente: tv_channel.m3u
        3. Directorio actual: {Path.cwd()}
        4. Archivos en el directorio:
        {'\n'.join(str(f) for f in Path(SCRIPT_DIR).iterdir())}
        """)
        msg.exec()
        
def main():
    app = QApplication(sys.argv)
    print("Creando viewer...")
    viewer = IPTVViewer()
    
    # Forzar la visualización
    viewer.setWindowState(Qt.WindowState.WindowActive)
    viewer.activateWindow()
    viewer.raise_()
    viewer.show()
    
    print("Mostrando viewer...")
    return app.exec()

if __name__ == '__main__':
    print("Iniciando programa")
    sys.exit(main())

