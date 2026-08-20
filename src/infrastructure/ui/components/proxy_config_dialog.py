import logging
import requests
import threading
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QCheckBox, QSpinBox, QLineEdit, QPushButton,
    QGroupBox, QComboBox, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


def _fetch_tor_info(request_get, proxy_url: str):
    proxies = {'http': proxy_url, 'https': proxy_url}
    try:
        resp = request_get('http://ip-api.com/json', proxies=proxies, timeout=5)
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None

    if data.get('status') != 'success':
        return None

    return data.get('query'), data.get('country')


def _is_local_port_open(socket_factory, host: str, port: int) -> bool:
    sock = socket_factory()
    try:
        sock.settimeout(1.0)
        sock.connect((host, port))
        sock.close()
        return True
    except OSError:
        return False


def _fetch_proxy_test_ip(request_get, proxies: dict, timeout: int) -> str:
    primary_url = 'http://api.ipify.org?format=json'
    try:
        resp = request_get(primary_url, proxies=proxies, timeout=timeout)
        payload = resp.json()
        return payload.get('ip')
    except (requests.RequestException, ValueError, AttributeError):
        fallback_url = 'http://ident.me'
        logging.info(f"Test Proxy: Reintentando fallback en {fallback_url}")
        resp = request_get(fallback_url, proxies=proxies, timeout=timeout)
        return resp.text.strip()


class ProxyConfigDialog(QDialog):
    """Diálogo independiente para la configuración del Proxy."""
    tor_info_received = pyqtSignal(str, str) # ip, country

    def __init__(self, proxy_config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración del Proxy")
        self.setMinimumWidth(400)
        self._proxy_config = proxy_config.copy()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        proxy_group = QGroupBox("Servidor Proxy")
        proxy_form = QFormLayout(proxy_group)

        self.proxy_enabled = QCheckBox("Activar uso de proxy")
        self.proxy_enabled.setChecked(self._proxy_config.get("enabled", False))
        self.proxy_enabled.toggled.connect(self._on_type_changed)
        proxy_form.addRow(self.proxy_enabled)

        self.proxy_type = QComboBox()
        self.proxy_type.addItems(["http", "https", "socks4", "socks5", "tor"])
        self.proxy_type.setCurrentText(self._proxy_config.get("type", "http"))
        self.proxy_type.currentTextChanged.connect(self._on_type_changed)
        proxy_form.addRow("Tipo de protocolo:", self.proxy_type)

        self.proxy_server = QLineEdit()
        self.proxy_server.setText(self._proxy_config.get("server", ""))
        self.proxy_server.setPlaceholderText("ej: 127.0.0.1 o proxy.ejemplo.com")
        proxy_form.addRow("Servidor/IP:", self.proxy_server)

        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(1, 65535)
        self.proxy_port.setValue(self._proxy_config.get("port", 8080))
        proxy_form.addRow("Puerto:", self.proxy_port)

        layout.addWidget(proxy_group)

        auth_group = QGroupBox("Autenticación (Opcional)")
        auth_form = QFormLayout(auth_group)

        self.proxy_user = QLineEdit()
        self.proxy_user.setText(self._proxy_config.get("username", ""))
        auth_form.addRow("Usuario:", self.proxy_user)

        self.proxy_pass = QLineEdit()
        self.proxy_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.proxy_pass.setText(self._proxy_config.get("password", ""))
        auth_form.addRow("Contraseña:", self.proxy_pass)

        self.proxy_bypass = QCheckBox("Excluir localhost (127.0.0.1)")
        self.proxy_bypass.setChecked(self._proxy_config.get("bypass_local", True))
        auth_form.addRow(self.proxy_bypass)

        self.bypass_local_subnet = QCheckBox("Excluir subred local (auto-detectar)")
        self.bypass_local_subnet.setChecked(self._proxy_config.get("bypass_local_subnet", False))
        auth_form.addRow(self.bypass_local_subnet)

        self.custom_bypass = QLineEdit()
        self.custom_bypass.setText(self._proxy_config.get("custom_bypass", ""))
        self.custom_bypass.setPlaceholderText("ej: 192.168.1.0/24, 10.0.0.0/8")
        auth_form.addRow("Excluir subredes (CIDR):", self.custom_bypass)

        self.auth_group = auth_group
        layout.addWidget(auth_group)



        # Botón de Test
        test_btn = QPushButton("Probar Conexión Proxy")
        test_btn.clicked.connect(self._on_test_connection)
        layout.addWidget(test_btn)

        # Botones
        btns = QHBoxLayout()
        save_btn = QPushButton("Guardar")
        save_btn.clicked.connect(self.accept)
        save_btn.setDefault(True)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)

        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(save_btn)
        layout.addLayout(btns)

        # --- Grupo: Información de Tor (Dinámico) ---
        self.info_group = QGroupBox("Estado de la Red (Tor)")
        info_form = QFormLayout(self.info_group)

        from PyQt6.QtWidgets import QLabel
        self.lbl_tor_status = QLabel("Desconectado")
        self.lbl_tor_ip = QLabel("-")
        self.lbl_tor_country = QLabel("-")

        info_form.addRow("Estado:", self.lbl_tor_status)
        info_form.addRow("IP externa:", self.lbl_tor_ip)
        info_form.addRow("País:", self.lbl_tor_country)

        self.btn_new_identity = QPushButton("Nueva Identidad / Cambiar Circuito")
        self.btn_new_identity.clicked.connect(self._on_new_identity)
        info_form.addRow(self.btn_new_identity)

        self.btn_refresh_info = QPushButton("Actualizar Info")
        self.btn_refresh_info.clicked.connect(self._update_tor_info)
        info_form.addRow(self.btn_refresh_info)

        layout.addWidget(self.info_group)
        self.info_group.setVisible(False)

        self.info_timer = QTimer(self)
        self.info_timer.timeout.connect(self._update_tor_info)

        # Conectar señal de info hilos-segura
        self.tor_info_received.connect(self._on_tor_info_received)

        # Disparar actualización inicial de UI AHORA que todo existe
        self._on_type_changed()

    def _on_type_changed(self):
        """Habilita o deshabilita campos según el tipo de proxy seleccionado."""
        is_tor = self.proxy_type.currentText() == "tor"
        is_enabled = self.proxy_enabled.isChecked()

        # Si es Tor interno, IP y Puerto no son editables (se gestionan solos)
        self.proxy_server.setEnabled(is_enabled and not is_tor)
        self.proxy_port.setEnabled(is_enabled and not is_tor)
        self.proxy_type.setEnabled(is_enabled)

        # Autenticación y bypass no suelen aplicar a torpy directamente modo "simple"
        self.auth_group.setVisible(not is_tor)

        # Mostrar panel de info solo si es Tor
        self.info_group.setVisible(is_tor and is_enabled)
        if is_tor and is_enabled:
            if not self.info_timer.isActive():
                self.info_timer.start(10000) # Cada 10s
                self._update_tor_info()
        else:
            self.info_timer.stop()

        # Ajustar placeholders si es Tor
        if is_tor:
            self.proxy_server.setText("127.0.0.1 (Interno)")
            self.proxy_port.setValue(9050)
        elif self.proxy_server.text() == "127.0.0.1 (Interno)":
            self.proxy_server.setText("")

    def _update_tor_info(self):
        """Intenta obtener la IP y país actual a través del proxy Tor."""
        from src.infrastructure.utils.proxy import TorpyProxyManager
        manager = TorpyProxyManager.get_instance()

        if not manager.running:
            self.lbl_tor_status.setText("<span style='color: #ff5555;'>Desconectado / Iniciando</span>")
            self.lbl_tor_ip.setText("-")
            self.lbl_tor_country.setText("-")
            return

        self.lbl_tor_status.setText("<span style='color: #55ff55;'>Conectado (Tor)</span>")

        # Lanzar hilo para no bloquear la UI
        def fetch():
            proxy_url = f"socks5h://127.0.0.1:{manager.port}"
            info = _fetch_tor_info(requests.get, proxy_url)
            if info is not None:
                ip, country = info
                self.tor_info_received.emit(ip, country)

        threading.Thread(target=fetch, daemon=True).start()

    def _on_new_identity(self):
        """Reinicia el motor de Tor para forzar un nuevo circuito."""
        from src.infrastructure.utils.proxy import TorpyProxyManager
        manager = TorpyProxyManager.get_instance()

        if not manager.running:
            return

        self.lbl_tor_status.setText("<span style='color: #orange;'>Reconectando...</span>")
        self.lbl_tor_ip.setText("---")
        self.lbl_tor_country.setText("---")

        manager.restart()

        # Iniciar actualización de info en unos segundos
        QTimer.singleShot(5000, self._update_tor_info)

    def _on_tor_info_received(self, ip: str, country: str):
        """Actualiza los labels de la UI de forma segura en el hilo principal."""
        self.lbl_tor_ip.setText(f"<b>{ip}</b>")
        self.lbl_tor_country.setText(f"<b>{country}</b>")


    def _on_test_connection(self):
        """Prueba una petición simple usando el proxy configurado (aplicando cambios primero)."""
        from src.infrastructure.utils.proxy import setup_proxy, TorpyProxyManager

        # 1. Obtener config actual de la UI y APLICARLA inmediatamente
        current_cfg = self.get_results()
        setup_proxy(current_cfg)

        ptype = current_cfg.get('type')

        # 2. Preparar URL de test según el tipo
        if ptype == "tor":
            test_ptype = "socks5h"
            server = "127.0.0.1"
            user = ""
            pwd = ""
        else:
            test_ptype = ptype
            server = current_cfg.get('server')
            user = current_cfg.get('username')
            pwd = current_cfg.get('password')

        port = current_cfg.get('port')
        auth = f"{user}:{pwd}@" if user and pwd else ""
        proxy_url = f"{test_ptype}://{auth}{server}:{port}"

        proxies = {'http': proxy_url, 'https': proxy_url}

        try:
            # Mostrar mensaje de espera ya que Tor puede ser lento al testear
            self.setCursor(Qt.CursorShape.WaitCursor)

            # Si es Tor, esperar a que el puerto esté FÍSICAMENTE abierto y listo
            if ptype == "tor":
                from PyQt6.QtCore import QCoreApplication
                import socket
                import time
                manager = TorpyProxyManager.get_instance()
                wait_start = time.time()
                port_ready = False

                logging.info(f"Test Proxy: Iniciando ciclo de espera técnica para puerto {port}...")
                while time.time() - wait_start < 60:
                    QCoreApplication.processEvents()
                    if manager.running and _is_local_port_open(
                        lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),
                        "127.0.0.1",
                        port,
                    ):
                        port_ready = True
                        logging.info("Test Proxy: ¡Puerto 9050 detectado abierto y respondiendo!")
                        break
                    time.sleep(0.5)

                if not port_ready:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
                    QMessageBox.warning(self, "Test Proxy", f"El puerto {port} no responde.\n\nVerifica que no tengas otro cliente Tor abierto o que un Firewall no esté bloqueando el programa.")
                    return

                # Un pequeño margen extra para que el protocolo SOCKS se asiente
                time.sleep(1.0)

            # Definir timeout: 60s para Tor para evitar cortes prematuros
            timeout = 60 if ptype == "tor" else 20

            # Usamos HTTP en lugar de HTTPS para el test para ser más rápidos y evitar líos de certificados en Tor
            test_url = 'http://api.ipify.org?format=json'
            logging.info(f"Test Proxy: Lanzando GET a {test_url} vía {proxy_url} (timeout={timeout}s)")

            ip = _fetch_proxy_test_ip(requests.get, proxies, timeout)

            self.setCursor(Qt.CursorShape.ArrowCursor)
            QMessageBox.information(self, "Test Proxy", f"¡Conexión exitosa!\nIP detectada: {ip}")

        except Exception as e:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            err_msg = str(e)

            # Captura universal de 'Conexión rechazada' (10061)
            if "10061" in err_msg or "Connection refused" in err_msg or "10054" in err_msg:
                if ptype == "tor":
                    user_msg = "El servidor Proxy Tor todavía no está aceptando conexiones.\n\nEspera unos segundos a que el túnel esté listo (panel en verde) e inténtalo de nuevo."
                else:
                    user_msg = f"No se pudo alcanzar el servidor Proxy en:\n{proxy_url}\n\nVerifica que la dirección y el puerto sean correctos."
                QMessageBox.critical(self, "Test Proxy", user_msg)
            elif "timeout" in err_msg.lower():
                note = "\n\nNota: Si es Tor, el proceso inicial puede tardar hasta 1 minuto." if ptype == "tor" else ""
                QMessageBox.warning(self, "Test Proxy", f"Tiempo de espera agotado.{note}")
            else:
                import traceback
                logging.error(f"Error detallado en el test de proxy: {traceback.format_exc()}")
                QMessageBox.critical(self, "Test Proxy", f"Error inesperado en el test:\n{e}\n\n(Consulta el log para más detalles)")

    def get_results(self) -> dict:
        ptype = self.proxy_type.currentText()
        return {
            "enabled": self.proxy_enabled.isChecked(),
            "type": ptype,
            "server": "127.0.0.1" if ptype == "tor" else self.proxy_server.text(),
            "port": self.proxy_port.value(),
            "username": "" if ptype == "tor" else self.proxy_user.text(),
            "password": "" if ptype == "tor" else self.proxy_pass.text(),
            "bypass_local": self.proxy_bypass.isChecked(),
            "bypass_local_subnet": self.bypass_local_subnet.isChecked(),
            "custom_bypass": self.custom_bypass.text()
        }
