import os
import hashlib
from pathlib import Path
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QUrl, Qt, pyqtSignal, QObject

class QtLogoLoaderAdapter(QObject):
    """Adaptador de infraestructura para la carga asíncrona de logos con caché en disco."""
    
    logo_loaded = pyqtSignal(str, QPixmap)  # URL, Pixmap

    def __init__(self, cache_dir: str = "cache/logos"):
        super().__init__()
        self._nam = QNetworkAccessManager()
        self._memory_cache = {}
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, url: str) -> Path:
        """Genera una ruta única en disco basada en el hash de la URL."""
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        return self._cache_dir / f"{url_hash}.png"

    def get_logo(self, url: str):
        """Devuelve el logo desde memoria, disco o descarga asíncronamente."""
        if not url:
            return

        # 1. Intentar memoria
        if url in self._memory_cache:
            self.logo_loaded.emit(url, self._memory_cache[url])
            return

        # 2. Intentar disco
        cache_path = self._get_cache_path(url)
        if cache_path.exists():
            pixmap = QPixmap(str(cache_path))
            if not pixmap.isNull():
                self._memory_cache[url] = pixmap
                self.logo_loaded.emit(url, pixmap)
                return

        # 3. Descargar si no está en ningún sitio
        request = QNetworkRequest(QUrl(url))
        # Algunos servidores requieren User-Agent para servir imágenes
        request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "IPTVViewer/1.0")
        
        reply = self._nam.get(request)
        reply.finished.connect(lambda: self._handle_response(reply, url, cache_path))

    def _handle_response(self, reply: QNetworkReply, url: str, cache_path: Path):
        """Procesa la respuesta, escala el logo y lo guarda en disco."""
        if reply.error() == QNetworkReply.NetworkError.NoError:
            data = reply.readAll()
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                # Escalar para el nuevo tamaño de celda (más grande)
                pixmap = pixmap.scaled(
                    100, 75, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Guardar en disco para futuras ejecuciones
                pixmap.save(str(cache_path), "PNG")
                
                # Guardar en memoria para esta sesión
                self._memory_cache[url] = pixmap
                self.logo_loaded.emit(url, pixmap)
        
        reply.deleteLater()
