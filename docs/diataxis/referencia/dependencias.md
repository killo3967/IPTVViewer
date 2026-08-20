# Dependencias

> **Respuesta corta**: 7 dependencias directas en `requirements.txt`. Los esenciales son PyQt6, python-vlc, mpv, torpy y requests. El resto son de desarrollo (pytest).

---

## Dependencias directas (`requirements.txt`)

> `requirements.txt` se reescribió en 2026-07-04 para listar solo dependencias directas, sin transitivas.

| Paquete | Requisito | Rol |
|---|---|---|
| `PyQt6` | `>=6.5` | Framework de interfaz gráfica |
| `python-vlc` | `>=3.0` | Binding del motor VLC |
| `mpv` | `>=1.0` | Binding del motor MPV |
| `requests` | `>=2.28` | Peticiones HTTP (M3U remoto, EPG) |
| `torpy` | `>=1.0` | Cliente Tor en Python puro |
| `pytest` | `>=8.0` | Framework de testing |
| `pytest-qt` | `>=4.2` | Testing de widgets Qt |

---

## Dependencias nativas (no Python)

| Componente | Ubicación | Obligatorio |
|---|---|---|
| `libmpv-2.dll` (y `mpv-1.dll`) | `bin/` | ✅ Solo para motor MPV |
| VLC (sistema) | Instalación estándar | ✅ Solo para motor VLC |

---

## Dependencias de empaquetado (PyInstaller)

| Componente | Rol |
|---|---|
| `pyinstaller` | Genera el `.exe` standalone a partir de `IPTVViewer.spec` |
| `gh` (GitHub CLI) | Publica el `.exe` en releases de GitHub vía `release.bat` |

> `pyinstaller` no está en `requirements.txt`; se instala en el entorno de build antes de ejecutar `build.bat`.

---

## Notas

- El binding `mpv` se importa dinámicamente dentro de `mpv_player_adapter.py`; requiere `libmpv-2.dll` en `bin/`.
- En el `.exe` empaquetado, `bin/` y `resources/` se incluyen como datos de PyInstaller (ver `IPTVViewer.spec`).
