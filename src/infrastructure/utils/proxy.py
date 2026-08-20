import os
import logging
import threading
import ssl

_SSL_CONTEXT_FALLBACK_EXCEPTIONS = (TypeError, ValueError, ssl.SSLError)
_SOCKET_CLOSE_EXCEPTIONS = (AttributeError, OSError)

# Parche de compatibilidad para Python 3.12+ (torpy usa ssl.wrap_socket que fue eliminado)
if not hasattr(ssl, 'wrap_socket'):
    def wrap_socket_compat(sock, *args, **kwargs):
        # Mapeo básico de argumentos antiguos a la nueva API SSLContext
        ssl_version = kwargs.get('ssl_version', ssl.PROTOCOL_TLSv1_2)
        try:
            context = ssl.SSLContext(ssl_version)
        except _SSL_CONTEXT_FALLBACK_EXCEPTIONS:
            context = ssl.create_default_context()

        context.check_hostname = False
        context.verify_mode = kwargs.get('cert_reqs', ssl.CERT_NONE)

        # Eliminar argumentos no soportados por wrap_socket de SSLContext
        clean_kwargs = {k: v for k, v in kwargs.items()
                       if k in ['server_side', 'do_handshake_on_connect', 'suppress_ragged_eofs', 'server_hostname']}

        return context.wrap_socket(sock, **clean_kwargs)

    ssl.wrap_socket = wrap_socket_compat
    logging.info("Aplicado parche de compatibilidad ssl.wrap_socket para Python 3.12+")

# --- PARCHE DE COMPATIBILIDAD TORPY (CellPadding Error) ---
try:
    from torpy.circuit import CellHandlerManager
    from torpy.cells import CellPadding, TorCellEmpty

    # 1. Ignorar CellPadding en el manejador de celdas (Evita ERROR en log)
    _orig_handle = CellHandlerManager.handle
    def _patched_handle(self, cell, from_node=None, orig_cell=None):
        if isinstance(cell, CellPadding):
            return # Simplemente ignorar padding
        return _orig_handle(self, cell, from_node, orig_cell)
    CellHandlerManager.handle = _patched_handle

    # 2. Silenciar advertencias de TorCellEmpty (Evita WARNING en log)
    _orig_empty_init = TorCellEmpty.__init__
    def _patched_empty_init(self, data=None, circuit_id=0):
        # Llamamos al abuelo directamente para saltar el log.warning del padre
        super(TorCellEmpty, self).__init__(circuit_id)
        self._data = data or b''
    TorCellEmpty.__init__ = _patched_empty_init

    logging.info("Aplicado parche para silenciar ruidos de CellPadding en torpy.")
except Exception as e:
    logging.debug(f"No se pudo aplicar parche de ruidos Tor: {e}")

# Silenciar tracebacks de torpy durante bootstrap (timeouts de conexión son normales)
logging.getLogger('torpy').setLevel(logging.WARNING)
# ---------------------------------------------------------

# No usaremos patching global de socket.socket para evitar bucles con torpy.
# En su lugar, confiaremos en:
# 1. Variables de entorno (os.environ) que respetan requests, VLC y mpv.
# 2. Configuración explícita en PyQt6 (QNetworkProxy).
# 3. Paso de parámetros directos a los adaptadores de vídeo.

class TorpyProxyManager:
    """Gestiona una instancia interna de Tor usando la librería torpy."""
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.tor = None
        self.server = None
        self.thread = None
        self.running = False
        self.port = 0

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def start(self, port: int = 9050):
        """Inicia el proxy SOCKS5 interno de torpy en un hilo."""
        with self._lock:
            if self.running or (self.thread and self.thread.is_alive()):
                if self.port == port:
                    return True
                self.stop()

            self.port = port
            self.running = False # Aún no está listo para servir

        try:
            # Importar fuera del hilo para verificar disponibilidad
            try:
                from torpy.cli.socks import SocksServer
            except ImportError:
                from torpy.socks import TorProxyServer as SocksServer

            def run_proxy():
                # En este hilo, borramos temporalmente las variables de proxy del entorno
                env_backup = {}
                for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy']:
                    if var in os.environ:
                        env_backup[var] = os.environ.pop(var)

                try:
                    from torpy.client import TorClient

                    logging.info("Torpy: Descargando consenso de red Tor (puede tardar 30-60s la primera vez)...")
                    self.tor = TorClient()
                    logging.info("Torpy: Consenso descargado. Creando circuito de 3 saltos...")

                    with self.tor.create_circuit(3) as circuit:
                        with SocksServer(circuit, "127.0.0.1", port) as socks_serv:
                            self.server = socks_serv
                            # APLICAR AQUÍ: Primero restaurar entorno, luego marcar como listos
                            for var, val in env_backup.items():
                                if var not in os.environ:
                                    os.environ[var] = val

                            self.running = True # AHORA el servidor está listo para recibir conexiones
                            logging.info(f"Torpy: Servidor SOCKS5 ACTIVADO en 127.0.0.1:{port}")

                            try:
                                socks_serv.start()
                            except Exception:
                                if self.running:
                                    logging.debug("Torpy: El servidor SOCKS se detuvo inesperadamente.")
                except Exception as e:
                    logging.error(f"Torpy: Error fatal en el hilo: {e}")
                finally:
                    for var, val in env_backup.items():
                        if var not in os.environ:
                            os.environ[var] = val
                    self.running = False
                    self.server = None
                    self.tor = None

            self.thread = threading.Thread(target=run_proxy, name="TorpyProxyThread", daemon=True)
            self.thread.start()
            return True
        except Exception as e:
            logging.error(f"Torpy: Error preparando arranque: {e}")
            return False

    def stop(self):
        """Detiene el proxy de torpy."""
        if not self.running:
            return
        self.running = False
        if self.server:
            try:
                if hasattr(self.server, 'listen_socket') and self.server.listen_socket:
                    # Esto forzará la salida de socks_serv.start()
                    self.server.listen_socket.close()
            except _SOCKET_CLOSE_EXCEPTIONS:
                logging.debug("Torpy: El socket de escucha ya estaba cerrado durante stop().")

        # Esperar un poco a que el hilo limpie todo
        import time
        time.sleep(0.5)
        self.server = None
        self.tor = None
        logging.info("Torpy: Detenido.")

    def restart(self):
        """Reinicia el circuito de Tor para obtener una nueva identidad."""
        if not self.running:
            return
        p = self.port
        self.stop()
        import time
        time.sleep(1) # Pequeña pausa para asegurar cierre de sockets
        self.start(p)

def get_standardized_proxy_config(proxy_cfg: dict) -> dict:
    """
    Retorna una copia de la configuración normalizada para motores externos (VLC/mpv).
    Convierte tipos como 'tor' en 'socks5' apuntando al local.
    """
    if not proxy_cfg or not proxy_cfg.get('enabled'):
        return {"enabled": False}

    cfg = proxy_cfg.copy()
    ptype = cfg.get('type', 'http').lower()

    if ptype == 'tor':
        cfg['type'] = 'socks5'
        cfg['server'] = '127.0.0.1'
        cfg['username'] = ''
        cfg['password'] = ''

    return cfg

def _reset_qt_proxy():
    try:
        from PyQt6.QtNetwork import QNetworkProxy
    except ImportError:
        logging.debug("QtNetwork no disponible; se omite el reseteo de proxy Qt.")
        return

    QNetworkProxy.setApplicationProxy(QNetworkProxy(QNetworkProxy.ProxyType.NoProxy))


def _apply_qt_proxy(ptype: str, server: str, port: int, user: str, pwd: str):
    try:
        from PyQt6.QtNetwork import QNetworkProxy
    except ImportError:
        logging.debug("QtNetwork no disponible; se omite la configuración de proxy Qt.")
        return

    q_proxy = QNetworkProxy()
    if 'socks5' in ptype:
        q_proxy.setType(QNetworkProxy.ProxyType.Socks5Proxy)
    elif 'socks4' in ptype:
        q_proxy.setType(QNetworkProxy.ProxyType.Socks4Proxy)
    else:
        q_proxy.setType(QNetworkProxy.ProxyType.HttpProxy)

    q_proxy.setHostName(server)
    q_proxy.setPort(port)
    if user:
        q_proxy.setUser(user)
    if pwd:
        q_proxy.setPassword(pwd)
    QNetworkProxy.setApplicationProxy(q_proxy)


def setup_proxy(proxy_cfg: dict):
    """
    Aplica la configuración de proxy de forma global (Variables de entorno y Qt).
    """
    manager = TorpyProxyManager.get_instance()

    if not proxy_cfg or not proxy_cfg.get('enabled'):
        manager.stop()
        # Limpiar entorno
        for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy', 'NO_PROXY', 'no_proxy']:
            if var in os.environ:
                del os.environ[var]

        # Resetear Qt
        _reset_qt_proxy()
        return

    # 1. Tor Interno
    ptype_orig = proxy_cfg.get('type', 'http').lower()
    is_tor = (ptype_orig == 'tor')

    if is_tor:
        port = proxy_cfg.get('port', 9050)
        if not manager.start(port):
            logging.error("No se pudo iniciar Tor: torpy no está disponible o falló la preparación del arranque")
            return
    else:
        manager.stop()

    # 2. Normalizar para el resto del sistema
    norm_cfg = get_standardized_proxy_config(proxy_cfg)
    ptype = norm_cfg.get('type')
    server = norm_cfg.get('server')
    port = norm_cfg.get('port', 8080)
    user = norm_cfg.get('username', '')
    pwd = norm_cfg.get('password', '')

    if not server:
        return

    # 3. Variables de Entorno y Qt
    auth = f"{user}:{pwd}@" if user and pwd else ""
    actual_ptype = 'socks5h' if is_tor else ptype
    proxy_url = f"{actual_ptype}://{auth}{server}:{port}"

    def apply_now():
        # Variables de Entorno (respetadas por requests, VLC, mpv)
        for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy']:
            os.environ[var] = proxy_url

        # Bypass
        no_proxy_parts = []
        if proxy_cfg.get('bypass_local', True):
            no_proxy_parts.append("localhost,127.0.0.1,::1")
        if proxy_cfg.get('bypass_local_subnet', False):
            no_proxy_parts.append("10.0.0.0/8,172.16.0.0/12,192.168.0.0/16")
        custom = proxy_cfg.get('custom_bypass', '').strip()
        if custom:
            no_proxy_parts.append(custom)

        if no_proxy_parts:
            no_proxy_val = ",".join(no_proxy_parts).replace(" ", "")
            os.environ['NO_PROXY'] = no_proxy_val
            os.environ['no_proxy'] = no_proxy_val

        # Soporte para Qt (PyQt6)
        _apply_qt_proxy(ptype, server, port, user, pwd)
        logging.info(f"Proxy global ACTIVADO: {proxy_url}")

    if is_tor:
        # Esperar a que torpy esté listo antes de activar las variables globales
        # para evitar el bucle de "consenshus download" intentando usar el proxy
        def wait_and_apply():
            import time
            start_t = time.time()
            # Máximo 600 segundos de espera (10 min, el primer bootstrap puede ser muy lento)
            while not manager.running and time.time() - start_t < 600:
                time.sleep(1)
            if manager.running:
                apply_now()
            else:
                thread_alive = manager.thread and manager.thread.is_alive()
                if thread_alive:
                    logging.warning(
                        "No se pudo activar el proxy Tor (Timeout de bootstraping tras 600s). "
                        "El hilo de Tor sigue ejecutándose — posiblemente la descarga de consenso es lenta."
                    )
                else:
                    logging.error(
                        "No se pudo activar el proxy Tor: el hilo de bootstraping terminó "
                        "inesperadamente. Revisa los logs anteriores para ver el error."
                    )

        threading.Thread(target=wait_and_apply, daemon=True).start()
        logging.info("Proxy Tor en espera de bootstraping...")
    else:
        apply_now()

