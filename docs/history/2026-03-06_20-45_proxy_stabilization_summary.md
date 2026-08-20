# Historial Completo de Sesión: Sistema Universal de Proxy e Integración Tor
**Fecha:** 2026-03-06
**Timestamp:** 20:55:00

## 1. Visión General
Esta sesión ha cubierto la implementación integral de un sistema de proxy dinámico para IPTV Viewer, permitiendo el enrutamiento de todo el tráfico (EPG, logos y streaming de video) a través de servidores HTTP, HTTPS, SOCKS5 e integración nativa con la red Tor.

## 2. Implementaciones Realizadas

### A. Core de Infraestructura de Proxy (`src/infrastructure/utils/proxy.py`)
- **Sistema Multiproxy**: Soporte para protocolos HTTP, HTTPS, SOCKS4 y SOCKS5.
- **Enrutamiento Universal**: Implementación de la función `setup_proxy` que configura:
    - **Variables de Entorno**: `HTTP_PROXY`, `HTTPS_PROXY` y `ALL_PROXY` (para `requests`, VLC y mpv).
    - **Reglas de Bypass**: Soporte para ignorar la red local, subredes locales (`192.168.x.x`, etc.) y dominios personalizados mediante `NO_PROXY`.
    - **Configuración de Qt**: Aplicación de `QNetworkProxy` a nivel de toda la aplicación PyQt6 para asegurar que los componentes de la interfaz (logos, EPG) usen el tunnel.
- **TorpyProxyManager (Nodo Tor Interno)**:
    - Integración de `torpy` para un nodo SOCKS5 interno sin dependencias externas.
    - Sistema de **Nueva Identidad** para forzar la rotación del circuito y la IP de salida.

### B. Interfaz de Usuario (`src/infrastructure/ui/components/proxy_config_dialog.py`)
- **Gestión de Configuración**: Diálogo completo con persistencia en `config.ini`.
- **Panel Tor Avanzado**: Monitoreo en tiempo real de IP externa, País y estado de conexión (basado en señales de Qt hilos-seguras).
- **Test de Conexión Inteligente**: Verificador de red que incluye pre-chequeo de puerto físico y reintentos automáticos.

### C. Dependencias Instaladas
- **`torpy`**: Implementación pura de Python del protocolo Tor.
- **`cryptography`**: Necesaria para el cifrado de los circuitos de Tor.
- **`PySide6/PyQt6`**: (Actualizados/Verificados para el soporte de proxy).

---

## 3. Desafíos Técnicos y Errores Solucionados

| Error / Desafío | Explicación Técnica | Solución Implementada |
| :--- | :--- | :--- |
| **Invisibilidad de Tráfico Tor** | El tráfico de bootstraping de Tor intentaba usar su propio proxy aún no iniciado, creando un bucle infinito (deadlock). | Se implementó el vaciado temporal de variables de entorno durante el inicio de Tor y su restauración posterior. |
| **Sintaxis de MPV/VLC** | Ciertos parámetros de proxy en los adaptadores causaban errores según la versión de las DLLs. | Se eliminó el paso de parámetros directos en favor de las variables de entorno (`ALL_PROXY`), que son capturadas de forma nativa y robusta por los motores de video. |
| **Compatibilidad SSL (Py 3.12+)** | `torpy` usaba `ssl.wrap_socket`, eliminado en Python 3.12, causando un crash inmediato. | Se aplicó un **monkey-patch** de compatibilidad en `proxy.py` que emula la API antigua usando `SSLContext`. |
| **Ruido de Celdas Tor** | `torpy` inundaba la consola con `ERROR: torpy.cells: CellPadding...`. | Se aplicó otro monkey-patch a `CellHandlerManager` para ignorar silenciosamente las celdas de relleno (padding) típicas de la red Tor. |
| **WinError 10061** | Al cambiar de circuito, el test de proxy fallaba porque el puerto SOCKS aún no estaba bindeado. | Creación de un ciclo de espera con **"Port Ping"** que monitoriza el socket físico hasta que responde realmente. |
| **Thread-Safety Crash** | La actualización de IP desde el hilo de Tor hacia labels de PyQt6 cerraba la app. | Uso de `pyqtSignal` (`tor_info_received`) para delegar la actualización al hilo principal de la UI. |
| **NameError / Log stuck** | Errores de importación y logs que dejaban de actualizarse. | Refactorización de `setup_logger` en `main.py` con `force=True` y revisión exhaustiva de imports en todos los módulos. |

---

## 4. Estado de Enrutamiento de Tráfico
- **Tráfico de Aplicación**: Enrutado vía `QNetworkProxy` (EPG, API de logos, tests).
- **Tráfico de Video (VLC/MPV)**: Enrutado vía variables de entorno configuradas dinámicamente por la aplicación antes de la reproducción.
- **Tráfico DNS**: Configurado para resolverse vía Proxy (SOCKS5h) cuando se usa Tor para evitar fugas de DNS (*DNS leaks*).

---

## 5. Próximos Pasos
- Monitorización de latencia del circuito Tor.
- Opción de "Modo Sigiloso" para entornos restringidos.
