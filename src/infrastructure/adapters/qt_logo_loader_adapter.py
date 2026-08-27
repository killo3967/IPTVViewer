import hashlib
import time
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

MAX_CONCURRENT_LOGOS = 4
LOGO_CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 días


class QtLogoLoaderAdapter(QObject):
    """Adaptador de infraestructura para la carga asíncrona de logos con caché en disco.

    Limita la concurrencia de descargas (``MAX_CONCURRENT_LOGOS``) y deduplica URLs
    en cola para no saturar la red con listas de miles de canales (p. ej. iptv-org).
    La caché en disco expira a los 30 días (``LOGO_CACHE_TTL_SECONDS``).
    """

    logo_loaded = pyqtSignal(str, QPixmap)  # URL, Pixmap

    def __init__(self, cache_dir: str = "cache/logos"):
        super().__init__()
        self._nam = QNetworkAccessManager()
        self._memory_cache: dict[str, QPixmap] = {}
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._pending: list[str] = []
        self._active: set[str] = set()
        self._queued: set[str] = set()

    def _get_cache_path(self, url: str) -> Path:
        """Genera una ruta única en disco basada en el hash de la URL."""
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        return self._cache_dir / f"{url_hash}.png"

    def get_logo(self, url: str):
        """Sirve el logo desde memoria/disco o lo encola para descarga asíncrona."""
        if not url:
            return

        # 1. Intentar memoria
        if url in self._memory_cache:
            self.logo_loaded.emit(url, self._memory_cache[url])
            return

        # 2. Intentar disco (solo si la caché no ha expirado)
        cache_path = self._get_cache_path(url)
        if cache_path.exists() and self._is_cache_fresh(cache_path):
            pixmap = QPixmap(str(cache_path))
            if not pixmap.isNull():
                self._memory_cache[url] = pixmap
                self.logo_loaded.emit(url, pixmap)
                return

        # 3. Encolar (evita duplicados en cola o en descarga activa)
        if url in self._queued or url in self._active:
            return
        self._queued.add(url)
        self._pending.append(url)
        self._process_queue()

    def _is_cache_fresh(self, cache_path: Path) -> bool:
        """True si el fichero cacheado tiene menos de ``LOGO_CACHE_TTL_SECONDS``."""
        try:
            age = time.time() - cache_path.stat().st_mtime
        except OSError:
            return False
        return age < LOGO_CACHE_TTL_SECONDS

    def _process_queue(self):
        """Arranca descargas pendientes hasta el tope de concurrencia."""
        while self._pending and len(self._active) < MAX_CONCURRENT_LOGOS:
            url = self._pending.pop(0)
            self._queued.discard(url)
            self._active.add(url)
            cache_path = self._get_cache_path(url)
            request = QNetworkRequest(QUrl(url))
            # Algunos servidores requieren User-Agent para servir imágenes
            request.setHeader(QNetworkRequest.KnownHeaders.UserAgentHeader, "IPTVViewer/1.0")
            reply = self._nam.get(request)
            reply.finished.connect(
                lambda r=reply, u=url, p=cache_path: self._handle_response(r, u, p)
            )

    def _handle_response(self, reply: QNetworkReply, url: str, cache_path: Path):
        """Procesa la respuesta, escala el logo, lo guarda y sigue drenando la cola."""
        self._active.discard(url)
        try:
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
        finally:
            reply.deleteLater()
            self._process_queue()
