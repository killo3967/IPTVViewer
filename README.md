# IPTVViewer

Reproductor IPTV para Windows con interfaz gráfica (PyQt6), soporte de múltiples motores de reproducción (mpv y VLC), gestión de fuentes M3U/EPG y proxy Tor integrado.

## Características

- Interfaz gráfica con **PyQt6**.
- Motores de reproducción: **mpv** (autocontenido) y **VLC** (requiere instalación).
- Fuentes M3U por nombre con filtros y EPG independientes.
- EPG (XMLTV) con soporte de archivos comprimidos `.gz`.
- Proxy Tor integrado (torpy) para navegación anónima, sin dependencias externas.

## Estructura

```
IPTVViewer/
├── main.py                 # Punto de entrada
├── src/
│   ├── application/        # Servicios de aplicación
│   ├── domain/             # Entidades y puertos (arquitectura hexagonal)
│   └── infrastructure/     # Adaptadores (UI, reproductores, repositorios)
├── tests/                  # Tests (pytest)
├── pruebas/                # Scripts de diagnóstico
├── docs/                   # Documentación
├── resources/              # Recursos (logo)
├── openspec/               # Artefactos SDD/OpenSpec
├── config.ini.example      # Plantilla de configuración
└── requirements.txt
```

## Requisitos

- Windows 10/11 de 64 bits.
- Python 3.11+.
- VLC Media Player 64-bit (solo si se usa el motor VLC).

## Instalación y ejecución

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Compilación (PyInstaller)

El ejecutable se genera con PyInstaller a partir de `IPTVViewer.spec`:

```powershell
.\.venv\Scripts\pip.exe install pyinstaller
.\.venv\Scripts\pyinstaller.exe IPTVViewer.spec
```

Esto produce `dist\IPTVViewer.exe` (modo *onefile*, autocontenido).

### DLLs de mpv (no versionadas)

Las DLLs del motor mpv **no están incluidas en este repositorio** (`bin/mpv-1.dll` y `bin/libmpv-2.dll`): son binarios externos de ~112 MB cada uno que superan el límite de GitHub. El `.exe` ya compilado las lleva dentro, pero para **recompilar** desde este código necesitas obtenerlas:

1. Descarga libmpv para Windows desde la web oficial de mpv (<https://mpv.io/installation/>) o desde un build comunitario de libmpv que incluya `libmpv-2.dll`.
2. Coloca las DLLs en la carpeta `bin/` del proyecto:

   ```
   bin/mpv-1.dll
   bin/libmpv-2.dll
   ```

3. Ejecuta de nuevo `pyinstaller IPTVViewer.spec`.

Sin estas DLLs, el motor **mpv** no arrancará (el motor **VLC** sí funcionará si VLC está instalado). El código **no** las descarga automáticamente.

## Configuración

Copia `config.ini.example` a `config.ini` y edítalo, o configura las fuentes desde la interfaz. El archivo `config.ini` no se versiona (contiene configuración local).
