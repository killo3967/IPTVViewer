# Auditoría Forense — IPTVViewer

> Modo: **Forensic** · Fecha: 2026-08-27 · Herramienta: codebase-memory-mcp (1376 nodos, 3237 aristas)
> Estado: solo lectura sobre `src/`. No se modificaron docs canónicos.

---

## Resumen ejecutivo

IPTVViewer está **funcional y en verde** (187 tests, ruff y mypy limpios). Arquitectura hexagonal en 3 capas coherente, con el doble motor VLC/MPV como abstracción bien justificada. La deuda principal es **acumulativa, no crítica**: directorios vacíos, scripts de diagnóstico no integrados y documentación que deriva del estado real.

---

## Arquitectura

| Capa | Rol | Métricas |
|---|---|---|
| `domain` | Entidades + puertos (sin acoplamiento) | core · fan-in 27 |
| `application` | Servicios de orquestación | core · fan-in 71 |
| `infrastructure` | Adaptadores + UI + utils | internal · fan-in 55 / fan-out 61 |
| `main` | Punto de entrada único | entry |

**Punto de entrada**: `main.main()` (único).

**Hotspots** (mayor fan-in):
| Símbolo | fan-in | Archivo |
|---|---|---|
| `TorpyProxyManager.start` | 15 | `infrastructure/utils/proxy.py` |
| `ensure_libmpv_dll` | 10 | `infrastructure/utils/mpv_dll_bootstrap.py` |
| `ViewModeController.activate` / `resolve_zap_index` | 10 | `application/services/view_mode_controller.py` |
| `IPlayer.release` | 10 | `domain/ports/i_player.py` |

**Observación**: el proxy Tor (`proxy.py`) es el componente más caliente y también el que más errores generó en los logs (`[socks] Some error`, `ConnectionResetError`). Es el candidato nº 1 a simplificar o a hacer más robusto.

---

## Deriva de documentación

- Los docs canónicos (`docs/history/`) siguen describiendo el empaquetado de DLLs en el `.exe`, **obsoleto** desde que la descarga es en runtime.
- La documentación derivada (`docs/diataxis/`) se actualizó en esta sesión para reflejar: descarga runtime (`bin/`, `bin-v3/`, `vlc/`), extracción vía `tar.exe`/7-Zip y el abandono de `py7zr`.
- Los docs canónicos **no se tocaron** (regla de auditoría).

---

## Deuda y código muerto

| Hallazgo | Severidad | Detalle |
|---|---|---|
| `src/application/dtos/` vacío | WARNING | Directorio creado y nunca poblado |
| `src/infrastructure/config/` vacío | WARNING | Ídem |
| `pruebas/` (6 scripts) | INFO | Diagnóstico ad-hoc (`channel_test.py` 31 KB, `channel_logger.py` 12,6 KB, etc.), sin importar desde la app |
| `except Exception` (22 usos) | INFO | Defensas amplias en adaptadores/UI/utils; mayoritariamente intencionales |
| `docs/history/` vs realidad | INFO | Deriva documental pendiente de migración |

**Sin**: TODOs/FIXMEs, stubs `NotImplementedError`, ramas `if False`, imports marcados como no usados, ni `__init__.py` vacíos.

---

## Evidencia de validación

| Herramienta | Comando | Resultado |
|---|---|---|
| Pytest | `python -m pytest tests/` | **187 passed** |
| Ruff | `python -m ruff check .` | **All checks passed** |
| Mypy | `python -m mypy src main.py` | **Success: no issues (32 archivos)** |

> Nota: la suite completa termina con `access violation 0xC0000005` en el teardown de PyQt6 (preexistente); los tests sin Qt salen limpios (`exit 0`).

---

## Cambios recientes relevantes (últimos 60 días)

31 commits. Destacados de esta sesión:

- `2098d16` — extracción BCJ2 con `tar.exe`/7-Zip vía `sevenzip.py` (se elimina `py7zr`).
- `30f4106` — `wasCanceled()` leído antes de `close()` (aviso falso "no se pudo descargar").
- `fe5d642` — `.gitignore` de `bin-v3/`.

---

## Gaps y recomendaciones

1. **Migrar docs canónicos** (`docs/history/`) al estado actual, o marcar `docs/diataxis/` como única fuente vigente (handoff a `diataxis-v2`).
2. **Eliminar o poblar** `src/application/dtos/` y `src/infrastructure/config/`.
3. **Decidir el destino de `pruebas/`**: integrarlo en `tests/` o etiquetarlo explícitamente como herramientas de diagnóstico.
4. **Proxy Tor**: alto fan-in + alta tasa de fallos en runtime; candidato a endurecer o aislar.
