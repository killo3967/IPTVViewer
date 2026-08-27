# Entorno de Desarrollo

> **Respuesta corta**: Necesitas Python 3.11+ y VLC 64-bit. La DLL del motor MPV (`libmpv-2.dll`) se descarga automáticamente en runtime. El resto con `pip install -r requirements.txt`.

---

## Requisitos

| Componente | Obligatorio | Notas |
|---|---|---|
| Python 3.11+ | ✅ | Probado en 3.12 |
| VLC Media Player 64-bit | ✅ (motor VLC) | Instalar en ubicación por defecto |
| libmpv-2.dll | ✅ (motor MPV) | Descargada automáticamente en runtime |
| Tor (externo) | ❌ | El proyecto usa torpy (integrado) |

---

## Instalación rápida

```powershell
# 1. Clonar o copiar el proyecto
cd K:\IPTVViewer

# 2. Crear entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar (descarga libmpv-2.dll automáticamente si falta)
python main.py
```

---

## Configuración de motores

### VLC

- Requiere VLC instalado en el sistema (el binding `python-vlc` busca la DLL automáticamente)
- Configuración técnica en `config.ini` → sección `[VLC]`

### MPV

- `libmpv-2.dll` se descarga automáticamente en runtime a `bin/` (genérica) o `bin-v3/` (AVX2)
- El adaptador carga la DLL automáticamente al inicio
- Configuración técnica en `config.ini` → sección `[MPV]`

---

## Archivos de configuración

| Archivo | Propósito |
|---|---|
| `config.ini` | Fuente M3U, EPG, motor activo, proxy, opciones técnicas |
| `requirements.txt` | Dependencias directas (10 paquetes) |
| `pyproject.toml` | Configuración de Ruff (linter) y Mypy (tipado) |
| `skills-lock.json` | Versiones bloqueadas de skills del agente |

---

## Verificación de código (ruff + mypy)

El proyecto usa **Ruff** (linter) y **Mypy** (tipado estático), configurados en `pyproject.toml`:

| Herramienta | Comando | Qué verifica |
|---|---|---|
| Ruff | `.\\.venv\\Scripts\\ruff.exe check .` | Lint: estilo, imports, bugs |
| Mypy | `.\\.venv\\Scripts\\mypy.exe src main.py tests` | Tipado estático |
| Pytest | `.\\.venv\\Scripts\\python.exe -m pytest` | Tests (187) |

> Ruff también incluye un formateador (`ruff format .`) que unifica el estilo visual. Aún no está aplicado al árbol completo; consúltalo antes de lanzarlo.

---

## Estructura de directorios relevante

| Directorio | Contenido |
|---|---|
| `src/` | Código fuente (domain, application, infrastructure) |
| `pruebas/` | Scripts de diagnóstico y experimentos |
| `bin/`, `bin-v3/`, `vlc/` | DLLs de motor descargadas en runtime |
| `m3u/` | Archivos M3U locales |
| `logs/` | Salida de logs (iptv_viewer.log, vlc.log, mpv.log) |
| `docs/` | Documentación canónica y auditoría |
| `docs/diataxis/` | Documentación derivada (este conjunto) |
| `build.bat` / `release.bat` | Scripts de empaquetado y publicación |
| `IPTVViewer.spec` | Configuración de PyInstaller |

---

## Empaquetado (PyInstaller)

Para generar el ejecutable standalone:

```powershell
# Genera un único .exe (onefile, sin consola) en dist\IPTVViewer.exe
.\build.bat

# Publica el .exe en una release de GitHub (requiere gh autenticado)
.\release.bat v1.1
```

- `IPTVViewer.spec` define el build: **onefile**, `console=False`, `upx=True`, incluye `resources/` como dato.
- El `.exe` resultante (~183 MB) es autónomo; no requiere Python instalado. VLC sigue siendo externo para el motor VLC.
- `libmpv-2.dll` no se empaqueta: se descarga en runtime y se extrae con `tar.exe` de Windows o 7-Zip.
- En modo congelado, `config.ini` y `logs/` se crean junto al `.exe` (`SCRIPT_DIR = Path(sys.executable).parent`).
