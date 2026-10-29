# ODD Task: view-modes

> Documento único de feature (contrato ODD de gentle-pi: `odd/tasks/<feature-name>.md`).
> Espejo de recuperación en Engram: topic `odd/view-modes/tasks`.
>
> **Migrado desde OpenSpec** (`openspec/changes/view-modes/`: proposal.md, spec.md,
> design.md, tasks.md, apply-progress.md, verify-report.md, archive-report.md —
> eliminados tras la migración; recuperables del historial de git).
> Estado original OpenSpec: **archivado COMPLETE** (2026-08-24).

## Objective

Tres modos de layout exclusivos — **Normal** (`Alt+1`), **Compact** (`Alt+2`),
**Video** (`Alt+3`) — más un eje ortogonal de fullscreen, zapping por teclado con
wrap-around, y una ventana PIP (picture-in-picture) desprendida siempre-on-top.
El modo de vista, la geometría del splitter y la geometría del PIP persisten entre
sesiones; el estado de fullscreen y la visibilidad del PIP no. Los atajos de menú
(p. ej. `Ctrl+G` EPG) permanecen activos en todos los modos.

## Problem

`IPTVMainWindow` solo ofrecía un layout: `QSplitter` horizontal con tabla de 3
columnas (Canal / Logo / Programación) a la izquierda y `video_widget` embebido a
la derecha, más barra de menú permanente:

- Ver un canal con la tabla ocupando media pantalla desperdicia espacio y distrae.
- Una experiencia "solo video" era imposible sin hackear la ventana.
- En fullscreen el cursor quedaba visible tras unos segundos (molesto en uso tipo TV).
- Zapear exigía clic en la tabla: imposible con la tabla oculta o con foco en el video.
- No existía ventana PIP desprendida para ver el stream en overlay mientras se hace
  otra cosa en el escritorio.

## Why

Valor declarado en la propuesta original: adaptar la UI al momento de uso con tres
modos explícitos, fullscreen cómodo, zapping por teclado universal y un overlay PIP
flotante — sin opciones de configuración innecesarias, todo por atajos.

## Scope

**Incluye:**
- Controlador de modos de vista puro (Qt-free) + mapeo de layout en la ventana.
- Eje fullscreen ortogonal con auto-ocultación del cursor (3 s).
- Zapping por teclado (↑/↓) con wrap-around en todos los modos.
- Ventana PIP desprendida, siempre-on-top, arrastrable y redimensionable, con
  persistencia de geometría.
- Persistencia de modo/splitter/PIP-geometry en `main.py` load/save config.
- Re-targeting del display del player tras cada cambio de visibilidad.

**Excluye:**
- Segunda instancia de player (modelo DETACH: un solo output re-parentado).
- Auto-apertura del PIP al arrancar.
- Desactivar atajos de menú en ningún modo (REQ-9: nunca `setEnabled(False)`).

## Constraints

- `view_mode_controller.py` sin imports de `PyQt6` (testeable con pytest puro).
- REQ-9: los QActions de menú permanecen habilitados en Compact/Video.
- El PIP nunca se abre solo al lanzar la app, aunque se cerrara con él abierto.
- Un solo output de video: el widget se re-parenta, no se duplica.
- `winId()` se relee en cada llamada (cambia con `setParent`/hide-show).

## Decisiones de diseño (D1–D9, de design.md)

| ID | Decisión | Req |
|----|----------|-----|
| D1 | `ViewModeController` Qt-free: enum `ViewMode` + `parse()` con fallback a NORMAL sin lanzar; `activate()` idempotente; listeners reciben `(old, new)` solo en cambio real; `resolve_zap_index` puro | REQ-1, REQ-8 |
| D2 | Persistencia: `load_config`/`save_config` en `main.py` con parámetro opcional `config_path` para tests herméticos | REQ-8 |
| D3 | Mapeo de layout en `IPTVMainWindow`: la ventana aplica el mapeo, nunca decide estado. NORMAL: panel de una columna variante normal + video + menú; COMPACT: panel de una columna variante compacta + video + menú; VIDEO: solo video, sin menú. **Actualizado 2026-10-21**: el panel pasó de 3 columnas a una sola y COMPACT ya no oculta columnas ni el menú (ver `odd/tasks/channel-panel-single-column.md`, D8–D11) | REQ-2, REQ-10 |
| D4 | Splitter: debounce `QTimer` single-shot 300 ms en `splitterMoved`; snapshot síncrono pre-hide al entrar en VIDEO; el debounce se salta con la tabla oculta | REQ-8 |
| D5 | Fullscreen: `F` toggle; timer 3 s oculta el cursor; `eventFilter` restaura al mover ratón; única salida por `_exit_fullscreen()` (F-off/Esc/close) | REQ-4 |
| D6 | Re-target: `initialize_display(int(video_widget.winId()))` al final de cada cambio de modo (exactamente una vez) y tras abrir/cerrar PIP | REQ-7 |
| D7 | PIP: `pip_window.py` con `ResizeGrip`; flags `Tool|FramelessWindowHint|WindowStaysOnTopHint`; drag por el cuerpo, grip inferior-derecho | REQ-6 |
| D8 | Despacho de teclas: dos rutas complementarias (QShortcut + `keyPressEvent` fallback) funneladas a una tabla única; guarda anti doble-dispacho con `event.isAccepted()` | REQ-3, REQ-5, REQ-6 |
| D9 | Zapping: `resolve_zap_index` puro con `(index ± 1) % len`; playlist vacía → no-op | REQ-5 |

**Revisiones resueltas con el usuario (ronda de preguntas, 2026-08-24):**

| # | Propuesta original | Decisión resuelta |
|---|---|---|
| 1 | PIP v1 detach (Q1) | DETACH confirmado — un solo output re-parentado |
| 2 | Zap en bordes = parar | WRAP-AROUND (↑ en el primero → último; ↓ en el último → primero) |
| 3 | Atajos de menú desactivados en Compact/Video | MANTENER ACTIVOS — nunca deshabilitar QActions |
| 4 | Visibilidad PIP persistida | El PIP NUNCA se auto-abre al arrancar; solo se persiste geometría |
| 5 | Forwarding de foco del PIP | Reenviar teclas a la ventana principal; PIP siempre-on-top |

## Checklist

| ID | Tarea (WU original) | Estado |
|----|---------------------|--------|
| T1 | WU 1.1 — `ViewMode` enum + `parse()` (TDD RED→GREEN→REFACTOR) | ✅ done (`134f8f1`) |
| T2 | WU 1.2 — Máquina de estados `ViewModeController` (idempotencia, listeners) | ✅ done (`134f8f1`) |
| T3 | WU 1.3 — `resolve_zap_index` puro con wrap-around | ✅ done (`134f8f1`) |
| T4 | WU 1.4 — Helpers de geometría/splitter (encode/decode base64) | ✅ done (`134f8f1`) |
| T5 | WU 2.1 — Round-trip config: `view_mode`, `splitter_state`, `pip_geometry` en `main.py` | ✅ done (`61aaeef`) |
| T6 | WU 3.1 — Scaffolding pytest-qt (fakes `PlaybackManager`, `_pump_events`) | ✅ done (`3543ee8`) |
| T7 | WU 3.2 — `_apply_layout`: mapeo por modo + context menu + menú | ✅ done (`3543ee8`) |
| T8 | WU 3.3 — Registro de atajos Alt+1/2/3, P/Alt+4, ↑/↓, F, Esc, Ctrl+G | ✅ done (`3543ee8`) |
| T9 | WU 3.4 — Fullscreen: toggle, timer cursor, eventFilter, `_exit_fullscreen` único | ✅ done (`3543ee8`) |
| T10 | WU 3.5 — Splitter: debounce, snapshot pre-hide VIDEO, restore | ✅ done (`3543ee8`) |
| T11 | WU 4.1 — `PIPWindow`: flags, drag cuerpo, grip resize, forwarding de teclas | ✅ done (`135766e`) |
| T12 | WU 4.2 — `_open_pip`/`_close_pip`: re-parent + re-target | ✅ done (`135766e`) |
| T13 | WU 4.3 — Persistencia de geometría PIP (move/resize → debounce → config) | ✅ done (remediación `dd22668`) |
| T14 | WU 4.4 — Re-target en PIP open/close | ✅ done (remediación `dd22668`) |
| T15 | WU 4.5 — Despacho de teclas con foco en PIP | ✅ done (remediación `dd22668`) |
| T16 | WU 5.1 — Smoke test manual motor real (VLC + mpv) | ⬜ **pending** |

> **T16 se ejecuta con el checklist compartido** [`odd/manual-smoke-test-checklist.md`](../manual-smoke-test-checklist.md) — una sola pasada cubre T16 (esta feature) y T7 (pip-hides-main-window).

## Acceptance Criteria and Checks

Estado final (tras remediación `dd22668`; tabla completa de verify-report):

| AC | Comportamiento | Test(s) de evidencia |
|----|----------------|----------------------|
| AC-1 | Arranque en NORMAL (panel de una columna variante normal, video, menú) | `test_startup_default_is_normal_layout` |
| AC-2 | Compact: panel de una columna variante compacta, tabla+video visibles, menú **visible** y ancho mínimo 252 px | `test_compact_layout_uses_compact_delegate_and_keeps_menubar` |
| AC-3 | Video: tabla oculta, video visible, menú oculto | `test_video_layout_hides_table_and_menubar` |
| AC-4 | Vuelta a Normal; re-activar modo activo es no-op | `test_alt1_returns_to_normal`, `test_repressing_active_mode_shortcut_is_noop` |
| AC-5 | Fullscreen + cursor auto-hide 3 s, restaurar al mover | `test_f_toggles_fullscreen_on/off`, `test_cursor_timeout_hides_cursor`, `test_mouse_move_restores_cursor_and_restarts_timer` |
| AC-6 | Esc solo sale de fullscreen si se está en fullscreen | `test_escape_exits_fullscreen_only_when_fullscreen` |
| AC-7 | Round-trip persistencia de modo | `test_new_keys_survive_round_trip`, `test_startup_applies_persisted_compact_mode` |
| AC-8 | Round-trip persistencia de splitter | `test_splitter_move_flush_persists_state`, `test_entering_video_writes_prehide_snapshot_synchronously`, `test_restart_in_video_returns_to_normal_restores_splitter` |
| AC-9 | Zap ↓/↑ en todos los modos, incl. Video | `test_zap_down_plays_next_channel`, `test_zap_up_in_video_mode` |
| AC-10 | **REV** wrap-around en bordes; playlist vacía no-op | `test_zap_down_at_last_wraps_to_first`, `test_zap_up_at_first_wraps_to_last`, `test_zap_empty_playlist_is_noop`, `test_zap_with_no_current_channel_plays_first` |
| AC-11 | PIP: frameless siempre-on-top, placeholder principal oculto | `test_pip_window_has_detached_flags`, `test_p_opens_pip_and_hides_main_placeholder` |
| AC-12 | Toggle PIP: widget vuelve al splitter | `test_p_closes_pip_and_widget_returns_to_splitter`, `test_alt4_toggles_the_same_pip_instance` |
| AC-13 | Persistencia Y restauración de geometría PIP | tests de remediación (persist on move/resize + restore + garbage→default) |
| AC-14 | **REV** Atajos de menú ACTIVOS; `Ctrl+G` funciona; `isEnabled()==True` | `test_all_menu_actions_enabled_in_compact_and_video`, `test_ctrl_g_opens_epg_grid_in_compact_and_video`, `test_ctrl_g_works_after_returning_to_normal` |
| AC-15 | Sin context menu en Compact/Video | assertions de `_apply_layout` (NoContextMenu/DefaultContextMenu) |
| AC-16 | Re-target tras cada cambio de modo y PIP open/close | `test_mode_switch_retargets_video_exactly_once` (+ tests de remediación para PIP cycle) |

REQ-11 (smoke manual con VLC+mpv) = T16, pendiente — no es fallo de entrega: se
escopeó desde el inicio como verificación manual.

## Edge cases (de design.md §8)

- Zap con playlist vacía/obsoleta → `resolve_zap_index` → `None` → no-op.
- Zap sin canal actual → índice 0.
- Arranque en VIDEO persistido → tabla oculta desde el inicio; volver a NORMAL
  restaura el `splitter_state` persistido (camino fallback).
- Cerrar PIP en VIDEO → área principal vacía, video de vuelta al splitter.
- Geometría PIP fuera de pantalla tras cambiar de monitor → heurística v1 de clamp
  (documentada, sin AC; **no implementada**, ver desviación 2).
- Fullscreen + PIP → el PIP permanece encima (aceptado en v1).
- Fullscreen + cerrar app → `closeEvent` pasa por `_exit_fullscreen()` (timer
  cancelado, cursor restaurado).
- Config corrupta (base64/geometry malformada) → helpers devuelven `None`, defaults,
  sin crash.
- Doble-dispacho entre QShortcut y teclas reenviadas → guard con `event.isAccepted()`.

## Risks and mitigations (de design.md §9)

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| `winId()` cambia con setParent/hide-show | Alta | Re-leer en cada re-target (D6); tests con fake asserting counts; smoke manual obligatorio |
| Splitter pisado por layout colapsado VIDEO | Alta | Snapshot síncrono pre-hide + saltar debounce con tabla oculta (D4) |
| Menú oculto manteniendo atajos es comportamiento REQUERIDO | Media | REQ-9: nunca `setEnabled(False)`; tests de `isEnabled()` |
| `Alt+1..4` tragados por el menú nativo Windows | Baja | Test con menú visible; contingencia `ApplicationShortcut` (D8) |
| Cursor invisible tras salir de fullscreen | Media | Ruta única `_exit_fullscreen()` (F-off/Esc/close) |
| Offscreen no ejercita fullscreen/flags completa | Baja | Espejo de estado + spies de `showFullScreen`/`showNormal` |
| Diálogo EPG modal (`exec()`) | Baja | Tests parchean `EPGGridDialog` con stub |
| PIP `Tool` window puede ocultarse al perder foco (quirk de plataforma) | Baja | Documentado; verificar en smoke manual |
| Navegación de tabla por flechas sustituida por zapping | Baja | Intencional (REQ-5); click-to-play preservado |

## Desviaciones del diseño (registradas en apply-progress)

1. **WU 4.3**: tests usan `pip.move()`/`pip.resize()` en vez de `QTest.mouseDrag` —
   los drags sintetizados crashean nativamente en offscreen; disparan el mismo
   wiring de `moveEvent`/`resizeEvent` y la mecánica de ratón está cubierta por
   `test_pip_body_drag_moves_window` / `test_pip_grip_drag_resizes_with_minimum`.
2. **Clamp off-screen del PIP (design §8) no implementado** — heurística v1 sin AC.
3. **WU 4.5**: el `keyPressEvent` fallback de D8 NO se añadió entonces — el PIP era
   hijo del main window, así que Qt resolvía los WindowShortcuts. Añadirlo habría
   sido código especulativo sin test que lo pidiera (strict-TDD).
   **⚠️ Evolución posterior:** la feature `pip-hides-main-window` convirtió el PIP
   en top-level (`parent=None`), lo que invalidó esa resolución — los QShortcut del
   main ya no disparan con foco en el PIP. El fallback `keyPressEvent` en el main
   window SÍ existe ahora (ver `odd/tasks/pip-hides-main-window.md`, T4).
4. **Flush de debounce en tests** usa `_pump_events()` (bucle processEvents+sleep)
   en vez de `qtbot.wait(350)` — el nested `QEventLoop` crashea en este entorno;
   comportamiento observable idéntico.

## Verification Evidence

- Fase original (verify): `QT_QPA_PLATFORM=offscreen pytest tests/ -q` → 130 passed;
  verdict **FAIL** con 3 bloqueantes CRITICAL (AC-13 geometría PIP nunca persistida,
  marcadores WU sin check, falta apply-progress con evidencia TDD).
- Remediación (`dd22668`): +10 tests; suite final del cambio → **140 passed**;
  los 3 CRITICAL resueltos; `grep "setEnabled(False)" main_window.py` → sin match.
- Archive: **COMPLETE** 2026-08-24, con REQ-11 (smoke manual) como único ítem abierto.
- Estado actual del repo: la suite es **204 passed** (creció con features posteriores,
  incluida `pip-hides-main-window`).
- Nota de entorno (preexistente): la suite completa sale con código Windows 139
  (access violation en teardown Qt offscreen, PyQt6 6.11 + pytest-qt 4.5) — verificado
  en worktree pristine; la señal de gate es el resumen de pytest, no el exit code.

## Files Touched (histórico del cambio)

- `src/application/services/view_mode_controller.py` (nuevo, Qt-free)
- `src/infrastructure/ui/main_window.py` (layout, shortcuts, fullscreen, splitter, PIP, re-target)
- `src/infrastructure/ui/components/pip_window.py` (nuevo)
- `main.py` (persistencia `view_mode` / `splitter_state` / `pip_geometry`)
- `tests/test_view_mode_controller.py`, `tests/test_config_roundtrip.py`, `tests/test_main_window.py`

## Next Step

T16 (REQ-11): smoke test manual con motor real — reproducir un canal en VLC y luego
en mpv; alternar NORMAL→COMPACT→VIDEO→NORMAL; abrir/arrastrar/redimensionar/cerrar
PIP; togglear fullscreen y esperar 3 s para el cursor; mover el ratón para
restaurarlo; verificar que `Alt+1..4` atraviesan la barra de menú nativa de Windows.
Registrar resultado y añadirlo a este documento como evidence.

**Nota:** este ítem se solapa con T7 de `pip-hides-main-window.md` (mismo smoke de
re-targeting tras hide/show) — se ejecuta como una única sesión de prueba manual
que cubre ambas features, usando el checklist punto a punto
[`odd/manual-smoke-test-checklist.md`](../manual-smoke-test-checklist.md).
