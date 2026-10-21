# ODD Task: pip-hides-main-window

> Documento único de feature (contrato ODD de gentle-pi: `odd/tasks/<feature-name>.md`).
> Espejo de recuperación en Engram: topic `odd/pip-hides-main-window/tasks`.

## Objective

Que el modo PIP sea una experiencia de "mini-TV flotante": al abrirlo, la ventana
principal desaparece por completo (también de la barra de tareas) y solo queda la
ventanita siempre-on-top con el video. Al cerrarlo, la principal reaparece.

## Problem

Con el comportamiento anterior, al activar PIP la ventana principal seguía visible
(con la lista de canales, sin video). El usuario quiere PIP para ver cuándo empieza
un programa mientras juega o trabaja: una ventana pequeña que no moleste, no dos
ventanas abiertas.

## Why

- Caso de uso principal declarado por el usuario: ver la tele en una ventanita
  mientras se usa el ordenador para otra cosa.
- El spec `view-modes` (REQ-6) ya definía el PIP como ventana detach siempre-on-top;
  este cambio completa la experiencia: la principal no solo "se queda sin video",
  desaparece.

## Scope

**Incluye:**
- Ocultar la ventana principal al abrir PIP; restaurarla al cerrarlo (por atajo,
  botón nativo o Alt+F4 sobre el PIP).
- Mantener todos los atajos operativos con el foco en el PIP (forwarding).
- Tests del nuevo comportamiento.

**Excluye:**
- Opción de configuración (decisión: siempre ocultar).
- Cambios en la persistencia de geometría (REQ-8, ya existente).

## Constraints

- La app no debe morir mientras el PIP está abierto (la principal se oculta, no se cierra).
- No debe existir estado en el que el PIP se cierre y la principal quede oculta para siempre.
- El re-targeting del motor de video (winId) debe re-ejecutarse en cada transición
  (open/close) — `_retarget_video()`.
- Comportamiento de doble disparo: las teclas reenviadas no deben activar los
  QShortcut de la principal.

## Decisión de diseño (con rationale)

Pregunta al usuario: (a) siempre ocultar, (b) clave en config.ini, (c) solo en modo
Normal. **Elección: siempre ocultar.** Rationale: el caso de uso es único y claro
(jugar con solo la ventanita visible); una opción de config añade superficie sin
valor; en Compact/Video la principal ya es mínima y el usuario no distinguió casos.

## Checklist

| ID | Tarea | Estado |
|----|-------|--------|
| T1 | `PIPWindow` top-level: constructor con `parent=None` (evita que hide() de la principal oculte el PIP) | ✅ done |
| T2 | `_open_pip()`: ocultar principal tras mostrar PIP + foco en la ventanita | ✅ done |
| T3 | `_close_pip()`: restaurar principal (`show`/`raise_`/`activateWindow` si oculta) | ✅ done |
| T4 | `MainWindow.keyPressEvent`: manejar teclas reenviadas (P, Alt+4, ↑/↓, F, Esc, Ctrl+G, Alt+1/2/3) | ✅ done |
| T5 | Señal `closed` en `PIPWindow.closeEvent` conectada a `_close_pip` (cubre Alt+F4) | ✅ done |
| T6 | Tests: ocultar al abrir, restaurar al cerrar, cierre nativo, PIP top-level | ✅ done |
| T7 | Smoke test manual con motor real (VLC/mpv): winId tras hide/show | ⬜ pending |

> **T7 se ejecuta con el checklist compartido** [`odd/manual-smoke-test-checklist.md`](../manual-smoke-test-checklist.md) — una sola pasada cubre T7 (esta feature) y T16 (view-modes).

## Acceptance Criteria and Checks

- **AC-1**: Al abrir PIP (`P`/`Alt+4`), `window.isVisible() is False` y el PIP es
  visible y top-level. → `test_opening_pip_hides_main_window`, `test_pip_window_is_top_level`.
- **AC-2**: Al cerrar PIP por tecla, la principal reaparece. →
  `test_closing_pip_restores_main_window`.
- **AC-3**: Cierre nativo (close()/Alt+F4) del PIP restaura la principal (sin app zombi). →
  `test_pip_native_close_via_closed_signal_restores_main`.
- **AC-4**: Con el foco en el PIP funcionan: zap ↑/↓, toggle P (P/Alt+4), modos
  Alt+1/2/3, fullscreen F/Esc, EPG Ctrl+G. → suite PIP existente (20 tests) en verde.
- **AC-5**: Suite completa en verde: **204 passed**
  (`.venv\Scripts\python.exe -m pytest tests/ -q`).

## Progress

- Fases ODD ejecutadas: exploring (lectura de `_open_pip`/`_close_pip`/`PIPWindow`/
  tests) → deciding (pregunta al usuario, elección "siempre ocultar") →
  implementing (T1–T6) → checking (suite completa 204/204).
- Nota: las fases no se etiquetaron en tiempo real con `gentle_odd_phase`; a partir
  de ahora se etiquetarán en cada transición real.

## Verification Evidence

- `pytest tests/ -q` → `204 passed in 5.11s` (tras los cambios; la suite previa era 200).
- 4 tests nuevos en `tests/test_main_window.py`:
  - `test_opening_pip_hides_main_window`
  - `test_closing_pip_restores_main_window`
  - `test_pip_native_close_via_closed_signal_restores_main`
  - `test_pip_window_is_top_level`
- `python -m py_compile` OK en ambos ficheros modificados.
- El usuario confirmó: "Perfecto ha funcionado" (verificación manual en su entorno).

## Gotchas técnicos (registro para el futuro)

| Problema | Solución aplicada |
|----------|-------------------|
| PIP hija de la principal → `hide()` de la principal la oculta también | `PIPWindow` top-level (`parent=None`) |
| Con la principal oculta, los `QShortcut` registrados en ella mueren | El PIP reenvía el `QKeyEvent` crudo vía `QApplication.sendEvent`; se maneja en `keyPressEvent`. `sendEvent` no activa atajos → sin doble disparo |
| `hide()` no dispara `closeEvent` → Alt+F4 sobre el PIP deja la principal oculta para siempre | Señal `closed` en `closeEvent` de `PIPWindow`, conectada a `_close_pip` |
| Tests existentes exigían Alt+2/Ctrl+G/Alt+4 con foco en el PIP | `keyPressEvent` ampliado a todas las teclas reenviadas |

## Files Touched

- `src/infrastructure/ui/main_window.py` (CRLF)
- `src/infrastructure/ui/components/pip_window.py` (LF)
- `tests/test_main_window.py` (CRLF)

## Next Step

T7: smoke test manual con motor real (VLC o mpv) — abrir PIP desde reproducción
real, mover/redimensionar, cerrar con P y con Alt+F4, confirmar que el video nunca
se congela y que la principal reaparece reproduciendo.
