# Dependencias

> **Respuesta corta**: 39 paquetes listados en `requirements.txt`. Los esenciales son PyQt6, python-vlc, mpv, torpy, y requests. El resto son transitivas o de desarrollo.

---

## Dependencias directas (esenciales)

| Paquete | Versión | Rol |
|---|---|---|
| `PyQt6` | 6.8.1 | Framework de interfaz gráfica |
| `PyQt6-Qt6` | 6.8.2 | Binarios Qt6 para PyQt6 |
| `PyQt6_sip` | 13.10.0 | Binding SIP para PyQt6 |
| `python-vlc` | 3.0.21203 | Binding del motor VLC |
| `mpv` | (via libmpv.dll) | Binding del motor MPV |
| `torpy` | 1.1.6 | Cliente Tor en Python puro |
| `requests` | 2.32.3 | Peticiones HTTP (M3U remoto, EPG) |
| `cryptography` | ≥3.0.0 | Criptografía para Tor |

## Dependencias de desarrollo

| Paquete | Versión | Rol |
|---|---|---|
| `pytest` | 9.0.2 | Framework de testing |
| `pytest-qt` | 4.5.0 | Testing de widgets Qt |

## Dependencias transitivas y utilidades

| Paquete | Rol |
|---|---|
| `certifi`, `urllib3`, `charset-normalizer`, `idna` | Stack HTTP de requests |
| `boolean.py`, `pyparsing` | Parseo de expresiones |
| `defusedxml` | Parseo seguro de XML (EPG) |
| `filelock`, `platformdirs` | Utilidades de sistema |
| `rich`, `Pygments`, `markdown-it-py`, `mdurl` | Formateo de terminal |
| `pip-audit`, `pip-requirements-parser`, `pip-api`, `cyclonedx-python-lib`, `packageurl-python`, `py-serializable`, `sortedcontainers`, `tomli`, `tomli_w` | Herramientas de auditoría de dependencias |
| `CacheControl`, `msgpack` | Caché HTTP |
| `iniconfig`, `pluggy` | Dependencias de pytest |
| `packaging`, `typing_extensions`, `colorama` | Compatibilidad |

---

## Dependencias nativas (no Python)

| Componente | Ubicación | Obligatorio |
|---|---|---|
| `libmpv-2.dll` | `bin/` | ✅ Solo para motor MPV |
| VLC (sistema) | Instalación estándar | ✅ Solo para motor VLC |

---

## Notas

- `mpv` (el binding Python) se importa dinámicamente dentro de `mpv_player_adapter.py`, no está en `requirements.txt`. Requiere `libmpv-2.dll` en `bin/`.
- Los paquetes de auditoría (`pip-audit`, `cyclonedx-python-lib`, etc.) son solo para CI/desarrollo, no necesarios en runtime.
- `pip-requirements-parser` v32.0.1 es el encargado de leer `requirements.txt`.
