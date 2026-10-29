import hashlib
import logging
import time
from pathlib import Path
from urllib.parse import urlsplit

from PyQt6.QtCore import QObject, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from src.infrastructure.utils.log_safe import safe_url

MAX_CONCURRENT_LOGOS = 4
#: Tiempo máximo por descarga (conexión + lectura). Sin él, un host que no
#: responde (IP apagada, red de contenedor) ocupa un hueco de la cola para
#: siempre y ningún logo llega a pintarse.
LOGO_TRANSFER_TIMEOUT_MS = 8000
#: Avisos por host antes de bajar el resto a DEBUG. Una lista de miles de
#: canales contra un CDN que responde 429 genera miles de fallos iguales.
MAX_WARNINGS_PER_HOST = 3
LOGO_CACHE_TTL_SECONDS = 30 * 24 * 3600  # 30 días
FAILED_RETRY_SECONDS = 60 * 60  # 1 hora (caché negativa de URLs rotas)


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
        # Caché negativa: URLs que fallaron y no se reintentan hasta que expire el TTL.
        self._failed: dict[str, float] = {}
        # Fallos acumulados por host: se avisa de los primeros y se resume
        # el resto cuando la cola se vacía.
        self._failed_by_host: dict[str, int] = {}

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

        # 3. Caché negativa: no reintentar URLs que fallaron hace poco.
        #    Los CDNs de logos IPTV suelen estar rotos; reintentarlos en cada
        #    re-render de la tabla genera cientos de conexiones SSL abortadas
        #    ("QSslSocket: device not open", errores HTTP/2).
        failed_at = self._failed.get(url)
        if failed_at is not None and time.time() - failed_at < FAILED_RETRY_SECONDS:
            return
        self._failed.pop(url, None)

        # 4. Encolar (evita duplicados en cola o en descarga activa)
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
            # HTTP/2 de Qt falla con muchos CDNs de IPTV ("HTTP/2 protocol error",
            # "Too many redirects" y sockets SSL abortados). Forzamos HTTP/1.1.
            request.setAttribute(
                QNetworkRequest.Attribute.Http2AllowedAttribute, False
            )
            # Sin este límite un host mudo bloquea la cola entera indefinidamente.
            request.setTransferTimeout(LOGO_TRANSFER_TIMEOUT_MS)
            reply = self._nam.get(request)
            reply.finished.connect(
                lambda r=reply, u=url, p=cache_path: self._handle_response(r, u, p)
            )

        if not self._pending and not self._active:
            self._log_failure_summary()

    @staticmethod
    def _failure_reason(reply: QNetworkReply) -> str:
        """Motivo del fallo corto y sin URLs.

        ``errorString()`` repite la URL completa con su query y sus tokens
        (los CDNs de logos las usan), así que el log acabaría con líneas de
        cientos de caracteres y datos ajenos al fallo: el nombre del error y
        el código HTTP bastan para diagnosticar.
        """
        error = reply.error()
        reason = getattr(error, "name", str(error))
        status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        return f"{reason} (HTTP {status})" if isinstance(status, int) else reason

    def _log_failure(self, url: str, reason: str) -> None:
        """Registra un fallo de logo sin inundar el log.

        Se avisa de los primeros ``MAX_WARNINGS_PER_HOST`` fallos de cada host;
        el resto queda en DEBUG y se resume cuando la cola termina.
        """
        host = urlsplit(url).netloc or url
        count = self._failed_by_host.get(host, 0) + 1
        self._failed_by_host[host] = count
        level = logging.WARNING if count <= MAX_WARNINGS_PER_HOST else logging.DEBUG
        logging.log(level, "Logo no descargado (%s): %s", reason, safe_url(url))

    def _log_failure_summary(self) -> None:
        """Resume los fallos de la tanda y reinicia los contadores.

        Se llama cuando la cola se queda sin trabajo: una sola línea en vez de
        una por canal.
        """
        if not self._failed_by_host:
            return

        hosts = sorted(self._failed_by_host.items(), key=lambda kv: kv[1], reverse=True)
        total = sum(count for _, count in hosts)
        palabra = "host" if len(hosts) == 1 else "hosts"
        detalle = ", ".join(f"{host} ({count})" for host, count in hosts[:3])
        logging.info("Logos: %d fallos en %d %s: %s", total, len(hosts), palabra, detalle)
        self._failed_by_host.clear()

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
                    self._failed.pop(url, None)
                    self.logo_loaded.emit(url, pixmap)
                else:
                    # La respuesta llegó pero no es una imagen válida.
                    self._log_failure(url, "no es una imagen")
                    self._failed[url] = time.time()
            else:
                # Error de red/HTTP o tiempo de espera agotado: se cachea el
                # fallo para no repetir la descarga en cada repintado.
                self._log_failure(url, self._failure_reason(reply))
                self._failed[url] = time.time()
        finally:
            reply.deleteLater()
            self._process_queue()
