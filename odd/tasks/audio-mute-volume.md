# ODD Task: audio-mute-volume

> Documento único de feature (contrato ODD de gentle-pi: `odd/tasks/<feature-name>.md`).
> Espejo de recuperación en Engram: topic `odd/audio-mute-volume/tasks`.

## Objective

Control de audio por teclado: **Ctrl+S** alterna silenciado/audible y
**Shift+↑/↓** suben/bajan el volumen (pasos de 5, rango 0–100). Funciona en
todos los modos de vista, en fullscreen y con el foco en la ventana PIP.

## Problem

La aplicación no toca el audio: los adaptadores VLC/mpv solo reproducen, paran y
asignan la ventana de salida. El volumen solo puede controlarse desde el mixer del
sistema, lo que interrumpe el uso "sofá/teclado" del visor.

## Why

Uso tipo TV: zapear y ajustar sonido sin salir de la app ni usar el ratón. El
usuario lo pidió explícitamente tras la feature de PIP.

## Scope

**Incluye:**
- Nuevo método en el puerto `IPlayer` + implementación en adaptadores VLC y mpv.
- Delegación en `PlaybackManager` (con re-aplicación al cambiar de motor).
- Atajos: Ctrl+S (mute toggle), Shift+↑ (vol +5), Shift+↓ (vol −5).
- Manejo de teclas reenviadas desde el PIP (mismas tres combinaciones).
- Estado de sesión en la ventana principal (sin persistencia en config).

**Excluye:**
- Persistencia del mute/volumen entre sesiones (decisión del usuario).
- OSD/indicador visual en pantalla (el feedback es el propio audio).
- Control por menú contextual o botones de ratón.

## Constraints

- ↑/↓ sin modificador siguen siendo zapping (no se toca ese comportamiento).
- Los métodos nuevos del puerto son abstractos: los fakes concretos de tests deben
  actualizarse o la suite se rompe.
- Llamadas de audio seguras cuando el motor aún no está inicializado (`None` guard).
- Volumen acotado a 0–100 en ambos motores.

## Decisiones de diseño

| ID | Decisión | Rationale |
|----|----------|-----------|
| D1 | **Ctrl+S** para mute — elección del usuario; libre (no choca con Alt+1..4, P, F, Esc, Ctrl+G). Nota: Ctrl+S suele ser "guardar" en apps de escritorio, pero esta app no tiene guard con atajo | Usuario |
| D2 | **Shift+↑/↓** para volumen — ↑/↓ están ocupados por zapping; el usuario eligió mantener el zap en flechas planas y mover el volumen a Shift | Resolución de conflicto |
| D3 | Estado de sesión en `IPTVMainWindow` (`_muted`, `_volume=100`); `PlaybackManager` recuerda el último valor aplicado y lo re-aplica en `switch_player_engine` para que un cambio de motor no restaure el sonido | Cambiar de motor no debe alterar lo que oye el usuario |
| D4 | Puerto: `set_muted(enabled: bool)` y `set_volume(level: int)` — primitivas simples; el toggle lo hace la ventana | El puerto no debe conocer semántica de UI |
| D5 | Sin persistencia ni OSD | Decisiones del usuario (sesión); feedback auditivo |

## Checklist

| ID | Tarea | Estado |
|----|-------|--------|
| T1 | Tests: `PlaybackManager.set_muted/set_volume` delegan; `switch_player_engine` re-aplica estado de audio | ✅ done |
| T2 | `IPlayer`: métodos abstractos `set_muted`, `set_volume`; fakes concretos actualizados | ✅ done |
| T3 | `vlc_player_adapter`: `audio_set_mute` / `audio_set_volume` con guard `None` | ✅ done |
| T4 | `mpv_player_adapter`: propiedades `mute` / `volume` con guard `None` | ✅ done |
| T5 | `PlaybackManager`: delegación + re-aplicación en switch | ✅ done |
| T6 | Tests ventana: Ctrl+S alterna mute; Shift+↑/↓ ajustan volumen con clamping | ✅ done |
| T7 | `main_window`: atajos (Ctrl+S) + rama en `keyPressEvent` para teclas reenviadas del PIP | ✅ done |
| T8 | Suite completa en verde | ✅ done (212 passed) |
| T9 | Añadir los 3 puntos de audio al checklist de smoke manual | ✅ done (bloque 9) |
| T10 | Verificación manual del usuario en Alt+1/2/3, fullscreen y PIP | ✅ done (2026-08-24) |

## Acceptance Criteria and Checks

- **AC-1**: Ctrl+S alterna `set_muted(True)`/`set_muted(False)` en el manager
  (toggle correcto en llamadas sucesivas).
- **AC-2**: Shift+↑ sube el volumen de 5 en 5 con techo en 100; Shift+↓ lo baja con
  suelo en 0 (sin valores fuera de rango ni excepciones).
- **AC-3**: ↑/↓ sin Shift siguen zapeando — sin regresión (tests de zap existentes).
- **AC-4**: Con foco en el PIP, Ctrl+S/Shift+↑/Shift+↓ reenviadas producen el mismo
  efecto (rama `keyPressEvent`).
- **AC-5**: Tras `switch_player_engine`, el nuevo motor recibe el estado de audio
  vigente.
- **AC-6**: Suite completa verde.

## Verification Evidence

- 8 tests nuevos: 3 en `tests/test_playback_manager.py` (delegación + re-aplicación
  en switch), 5 en `tests/test_main_window.py` (toggle mute, volumen con clamping,
  límites 0/100, Shift+↓ no zapea / ↓ plano sí zapea, Ctrl+S reenviado desde PIP).
- 1 test existente actualizado: `test_switch_player_engine_releases_old_player_...`
  — su secuencia exacta de llamadas ahora incluye `set_muted:False`/`set_volume:100`
  (re-aplicación de estado de audio, D3).
- Suite completa: `pytest tests/ -q` → **212 passed** (previa: 204).
- `py_compile` OK en los 5 ficheros tocados.
- **Verificación manual (usuario, 2026-08-24):** sonido probado en Alt+1, Alt+2,
  Alt+3, fullscreen y modo PIP — funciona en todas las presentaciones.

## Gotchas técnicos (registro para el futuro)

- **Qt matchea Shift+Down contra el QShortcut plano "Down"** (los modificadores
  horizontales no anulan el match de un atajo base). Un atajo separado "Shift+Down"
  nunca recibe el evento. Solución: un único atajo por flecha (`Up`/`Down`) que
  discrimina Shift en el handler con `QApplication.queryKeyboardModifiers()`.
- Testear `keyClick(window, Key, ShiftModifier)` sobre el volumen exige partir de
  un valor intermedio (el default es 100, ya en el techo).

## Next Step

Verificación en el smoke manual: puntos 9.1–9.3 del checklist
(`odd/manual-smoke-test-checklist.md`, bloque 9 de audio).
