# Entorno de Desarrollo y Construcción (IPTV Viewer)

Este proyecto está escrito en **Python 3.11+** y utiliza **PyQt6** para la interfaz de usuario y **python-vlc** / **mpv** como motores de reproducción multimedia.

## Instalación del Entorno (Windows 11)

### Requisitos Previos
1. **Python 3.12 (u otra versión compatible)**.
2. **VLC Media Player (64-bit)** instalado en el sistema (solo si se usa el motor VLC).

### Configuración del Entorno Virtual
```powershell
# Crear el entorno virtual en PowerShell
python -m venv .venv

# Activar el entorno virtual
.\.venv\Scripts\Activate.ps1

# Instalar dependencias
.\.venv\Scripts\pip.exe install -r requirements.txt
```

### Dependencias Principales
*   `PyQt6`: Framework de interfaz gráfica.
*   `python-vlc`: Binding oficial para el motor de VLC.
*   `mpv`: Binding para el motor mpv (alternativa robusta a VLC).
*   `requests`: Gestión de peticiones HTTP para listas remotas y EPG.
*   `torpy`: Cliente Tor en Python para navegación anónima sin dependencias externas.
*   `pytest` / `pytest-qt`: Framework de tests.

## Gestión de la Configuración (`config.ini`)

El proyecto utiliza un archivo de configuración `.ini` para persistir la sesión:
*   **[SETTINGS]**: Fuentes de canales, EPG, filtros y estado general.
*   **[VLC]**: Parámetros técnicos específicos del motor de reproducción (buffer, jitter, sincronización, etc.).

## Ejecución del Proyecto
Para lanzar el visualizador, ejecuta el archivo central:
```powershell
.\.venv\Scripts\python.exe main.py
```

## Empaquetado (PyInstaller)

El ejecutable se genera con **PyInstaller** en modo *onefile* a partir del archivo de configuración `IPTVViewer.spec`:

```powershell
.\.venv\Scripts\pyinstaller.exe IPTVViewer.spec
```

Esto produce `dist\IPTVViewer.exe` (~183 MB). El spec se encarga de:
*   Empaquetar `bin/` (DLLs de mpv: `mpv-1.dll`, `libmpv-2.dll`) y `resources/`.
*   Recopilar todo el framework Qt mediante `collect_all('PyQt6')`.
*   Declarar los *hidden imports* de `torpy`, `mpv` y `PyQt6.QtNetwork`.
*   Generar un único `.exe` autocontenido (`exclude_binaries=False`, modo *onefile*) y sin consola (`console=False`).

Notas:
*   El tamaño (~183 MB) se debe principalmente a PyQt6 y a las dos DLLs de mpv (~112 MB cada una).
*   En el bundle, los recursos y DLLs se resuelven mediante `sys._MEIPASS`; en desarrollo, mediante las rutas relativas normales.
*   Los logs y el `config.ini` se generan junto al `.exe` (el código usa `sys.executable` para resolver `SCRIPT_DIR`).
