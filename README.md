# IPTVViewer

Reproductor IPTV de escritorio para Windows: reproduce listas M3U con guía EPG, motores de reproducción intercambiables (mpv/VLC) y proxy Tor integrado. Se distribuye como un único `.exe` autocontenido, sin instalación.

## Empezar (sin compilar nada)

1. Descarga `IPTVViewer.exe` desde la [última release](https://github.com/killo3967/IPTVViewer/releases/latest).
2. Colócalo en una carpeta con permisos de escritura (evita `C:\Program Files`).
3. Ejecútalo. En el primer arranque se crean `config.ini` y `logs/` junto al ejecutable.

> **Windows SmartScreen**: el ejecutable no está firmado digitalmente, por lo que Windows mostrará un aviso. Pulsa **"Más información" → "Ejecutar de todos modos"**.

## Características

| Área | Detalle |
|------|---------|
| Reproducción | Motores **mpv** (incluido en el `.exe`) y **VLC** (requiere instalación) |
| Listas | Fuentes M3U por nombre, con filtro y EPG independientes por fuente |
| EPG | XMLTV, con soporte de archivos comprimidos `.gz` |
| Anonimato | Proxy Tor integrado (torpy), sin dependencias externas |
| Interfaz | PyQt6 |

## Requisitos

| Motor | Requisito |
|-------|-----------|
| **mpv** (predeterminado) | Ninguno: va dentro del `.exe` |
| **VLC** | VLC Media Player 64-bit instalado |

## Uso

1. Arranca la aplicación.
2. Añade o edita fuentes M3U desde la interfaz (o edita `config.ini`).
3. Selecciona el motor de reproducción (mpv o VLC).
4. Opcional: activa el proxy Tor desde la configuración.

> La plantilla incluye una fuente de ejemplo local (`TU_SERVIDOR`). Sustitúyela por tu propia lista M3U.

## Configuración

Copia `config.ini.example` a `config.ini` (la aplicación lo crea sola en el primer arranque). Secciones:

| Sección | Contenido |
|---------|-----------|
| `[SETTINGS]` | Fuente activa, motor de reproducción, aceleración por hardware |
| `[source.N]` | Una entrada por fuente: nombre, URL M3U, filtro y EPG |
| `[VLC]` | Parámetros del motor VLC (buffer, jitter, sincronización) |
| `[MPV]` | Parámetros del motor mpv (caché, user-agent, demuxer) |
| `[PROXY]` | Proxy Tor (servidor, puerto, reglas de bypass) |

## Desarrollo (desde fuente)

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

1. Descarga libmpv para Windows desde la web oficial de mpv (<https://mpv.io/installation/>) o desde un build comunitario que incluya `libmpv-2.dll`.
2. Coloca las DLLs en la carpeta `bin/` del proyecto:

   ```
   bin/mpv-1.dll
   bin/libmpv-2.dll
   ```

3. Ejecuta de nuevo `pyinstaller IPTVViewer.spec`.

Sin estas DLLs, el motor **mpv** no arrancará (el motor **VLC** sí funcionará si VLC está instalado). El código **no** las descarga automáticamente.

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

## Solución de problemas

| Síntoma | Causa probable |
|---------|----------------|
| Un canal no carga | URL M3U inválida o filtro/EPG mal configurado |
| El motor mpv no arranca (solo al compilar) | Faltan las DLLs en `bin/` |
| El motor VLC no funciona | VLC Media Player no está instalado |

Los registros en `logs/iptv_viewer.log` ayudan a diagnosticar errores.
