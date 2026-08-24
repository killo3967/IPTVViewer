# View Modes — Task Breakdown

**Change:** `view-modes` · **Backend:** OpenSpec · **Strict TDD:** enabled (pytest 9.0.2 + pytest-qt 4.5.0)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1,250–1,500 (3 new source/test files, 2 modified files) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Qt-free service) → PR 2 (config persistence) → PR 3 (main-window core) → PR 4 (PIP window) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

```text
Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High
```

**Sizing signals:** 7 files (3 new production, 3 new test, 1 modified test dir); 10 requirements with 30+ scenarios; pytest-qt window tests for layout/shortcuts/fullscreen/PIP; config round-trip tests; mandatory `main.py` persistence companion change. PR 3 is the largest slice (layout + shortcuts + zapping + fullscreen + splitter + menu liveness); it may need to be split further during apply if its diff approaches 400 lines — this is a decision point for the parent at apply time.

**Verification gates per PR:** each PR must keep `pytest tests/ -q` green plus its own new tests before it is pushed.

---

## Dependency order

```
WU 1.1–1.4 (Qt-free service, plain pytest) ──┐
                                              ├─► WU 2.1 (config persistence) ──► WU 3.x (window core) ──► WU 4.x (PIP) ──► WU 5.1 (smoke)
WU 2.1 needs helpers from WU 1.4 (geometry/splitter encoders) ──┘
```

Rules: never start a pytest-qt WU before WU 1.1–1.4 exist (window code imports the controller). Never write the PIP integration WUs before WU 4.1 (the `PIPWindow` component). Run the full suite after every REFACTOR step.

---

## PR 1 — Qt-free service layer (`src/application/services/view_mode_controller.py`)

### WU 1.1 — `ViewMode` enum and `parse()` (REQ-1)

**Files:**
- Create: `src/application/services/view_mode_controller.py`
- Create: `tests/test_view_mode_controller.py`

**AC:** REQ-1 — serialization round-trip (`normal|compact|video`), unknown persisted string falls back to `NORMAL` without raising.

- [x] RED: in `tests/test_view_mode_controller.py` write plain-pytest tests asserting `ViewMode.NORMAL.value == "normal"` (and `compact`/`video`), and `ViewMode.parse("normal"|"compact"|"video")` round-trips, while `ViewMode.parse("cinema")`, `parse(None)`, `parse("")` return `NORMAL` and never raise; run `pytest tests/test_view_mode_controller.py -v` and confirm FAIL (module does not exist). <!-- sdd-owner: implementation -->
- [x] GREEN: implement `class ViewMode(Enum)` with the three members and a `parse(cls, raw)` classmethod (unknown/`None` → `NORMAL`, never raises) in `src/application/services/view_mode_controller.py`, keeping the module free of any `PyQt6` import; run the test file and confirm PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: tidy `parse()` (single fallback path, no duplicated branches) and run `pytest tests/ -q` to confirm the whole suite is green. <!-- sdd-owner: implementation -->

**Verify:** `pytest tests/test_view_mode_controller.py -v` green. **Rollback:** delete the new module and test file; nothing else depends on it yet.

### WU 1.2 — `ViewModeController` state machine (REQ-1)

**Files:**
- Modify: `src/application/services/view_mode_controller.py`
- Modify: `tests/test_view_mode_controller.py`

**AC:** REQ-1 — exactly one active mode; new controller starts `NORMAL`; `activate()` idempotent (already-active mode returns `False`, no layout-change notification); listeners get `(old, new)` only on real changes.

- [x] RED: add tests: default mode is `NORMAL`; `activate(COMPACT)` → `COMPACT`; re-activating `COMPACT` returns `False` and a spy listener records no call; `activate(VIDEO)` notifies the spy with `(COMPACT, VIDEO)`; run and confirm the controller tests FAIL (class missing). <!-- sdd-owner: implementation -->
- [x] GREEN: implement `ViewModeController` with `__init__(initial=ViewMode.NORMAL)`, `mode` property, `register_listener(callable)`, and `activate(mode) -> bool` that notifies listeners only on change and returns `False` on no-op; confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: extract a private `_notify(old, new)` helper; assert no `PyQt6` import in the module (grep); full suite green. <!-- sdd-owner: implementation -->

**Verify:** controller tests green. **Rollback:** revert additions to the module/test file; independent of all other work.

### WU 1.3 — `resolve_zap_index` pure function (REQ-5)

**Files:**
- Modify: `src/application/services/view_mode_controller.py`
- Modify: `tests/test_view_mode_controller.py`

**AC:** REQ-5 (AC-9, AC-10) — pure index resolution with wrap-around; empty playlist → `None`; no current channel → `0`; current not found → `0`; URL-first then full-dataclass-equality matching.

- [x] RED: with a `Playlist([c1, c2, c3])` fixture (use `src.domain.entities.channel.Channel` frozen dataclass), write tests: `resolve_zap_index(channels, c1, +1) == 1`; down at last wraps to `0`; up at first wraps to `2`; empty list → `None`; `current=None` → `0`; current not in list → `0`; matching by URL when two channels share a URL; run and confirm FAIL (function missing). <!-- sdd-owner: implementation -->
- [x] GREEN: implement `resolve_zap_index(channels, current_channel, direction) -> Optional[int]` per D1 (empty → `None`; no/not-found current → `0`; modulo wrap for both directions; match by URL first, then full equality); confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: confirm `direction` is normalized to ±1 and the wrap formula is shared for both directions; full suite green. <!-- sdd-owner: implementation -->

**Verify:** controller tests green. **Rollback:** revert function + tests; no consumers yet.

### WU 1.4 — Geometry and splitter-state string helpers (REQ-8)

**Files:**
- Modify: `src/application/services/view_mode_controller.py`
- Modify: `tests/test_view_mode_controller.py`

**AC:** REQ-8 — `geometry_to_str`/`str_to_geometry` (`"x,y,w,h"`; negative x/y allowed; `w<=0`/`h<=0`/wrong count/non-int/empty → `None`; never raises); `encode_splitter_state`/`decode_splitter_state` (base64 round-trip; garbage → `None`; never raises).

- [x] RED: write tests for all four helpers covering the cases above, including round-trip (`str_to_geometry(geometry_to_str(1280, 40, 480, 270))` returns the tuple) and base64 with `+`, `/`, `=` characters; run and confirm FAIL. <!-- sdd-owner: implementation -->
- [x] GREEN: implement the four pure helpers (tuples/str/bytes only, no Qt types) per D1; confirm PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: verify `str_to_geometry` and `decode_splitter_state` share a safe-parse pattern (try/except, `None` on failure); full suite green. <!-- sdd-owner: implementation -->

**Verify:** controller tests green. **Rollback:** revert helpers + tests; nothing else consumes them yet.

**PR 1 boundary:** push as its own PR — pure service layer, zero Qt, independently reviewable and merges to main without behavior change.

---

## PR 2 — Config persistence (REQ-8)

### WU 2.1 — `load_config`/`save_config` keys + `config_path` parameter

**Files:**
- Modify: `main.py` (`load_config()` at ~line 46; `save_config(config_data)` at ~line 189)
- Create: `tests/test_config_roundtrip.py`

**AC:** REQ-8 (AC-7, AC-8, AC-13) — `view_mode`/`splitter_state`/`pip_geometry` survive a temp-file round-trip; legacy file without the keys loads with defaults, no error; invalid persisted `view_mode` normalized to `'normal'`; values `%`-safe for `ConfigParser`.

- [x] RED: in `tests/test_config_roundtrip.py` (uses `tmp_path`): write round-trip tests calling `load_config(path)`/`save_config(config_data, path)` — save a dict with the three new keys and reload to assert equality; legacy config (no keys) loads with `view_mode == 'normal'`, `splitter_state == ''`, `pip_geometry == ''`; an invalid persisted `view_mode = "cinema"` loads normalized to `'normal'`; a `splitter_state` containing `+`, `/`, `=` survives save/load unchanged; run and confirm FAIL (no `config_path` parameter, keys dropped). <!-- sdd-owner: implementation -->
- [x] GREEN: in `main.py` add optional `config_path` param to both functions (default `CONFIG_FILE`), read the three keys in `load_config` with `fallback=''` (normalize `view_mode` through `ViewMode.parse(...).value`), and write them in `save_config` (`config_data.get('view_mode', 'normal')`, `('splitter_state', '')`, `('pip_geometry', '')` — always `str`, never `None`); confirm round-trip tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: confirm existing in-file callers of `load_config()`/`save_config()` still work with the default param (no signature break), and run the full suite. <!-- sdd-owner: implementation -->

**Verify:** `pytest tests/test_config_roundtrip.py -v` plus full suite green. **Rollback:** revert the two `main.py` functions and delete the test file; behavior unchanged for existing keys.

**PR 2 boundary:** push as its own PR — hermetic config round-trips, no UI change.

---

## PR 3 — Main-window core (pytest-qt; `tests/test_main_window.py`)

### WU 3.1 — pytest-qt scaffolding and fakes

**Files:**
- Create: `tests/test_main_window.py`

**AC:** none (test infrastructure) — but required before any widget test.

- [x] RED/GREEN: create `tests/test_main_window.py` with module-level fakes mirroring the existing `FakePlayer` style — `FakePlaylistLoader` (returns a fixed `Playlist`), `FakePlaybackManager` (records `play_channel`/`initialize_display`, settable `current_channel`), `FakeEPGManager` (`has_data`), `FakeLogoLoader` (QObject exposing the `logo_loaded` signal), a recorder-stub for `EPGGridDialog`, and a `make_window(config=None, ...)` helper that injects fakes into `IPTVMainWindow(playlist_loader, playback_manager, epg_manager, logo_loader, config, save_callback)` (constructor at `src/infrastructure/ui/main_window.py:61`); one trivial smoke test (window constructs, `qtbot.addWidget`, table has 3 columns) — no production code changes yet. <!-- sdd-owner: implementation -->
- [x] REFACTOR: confirm the fakes stay minimal (no production-code imports beyond `Channel`/`Playlist`/`IPTVMainWindow`) and `pytest tests/test_main_window.py -v` runs headless (`QT_QPA_PLATFORM=offscreen`). <!-- sdd-owner: implementation -->

**Verify:** scaffolding smoke test green. **Rollback:** delete `tests/test_main_window.py`; nothing else changed.

### WU 3.2 — `_apply_layout` mapping + startup mode (REQ-2, REQ-10)

**Files:**
- Modify: `src/infrastructure/ui/main_window.py` (`IPTVMainWindow`)
- Modify: `tests/test_main_window.py`

**AC:** AC-1, AC-2, AC-3, AC-4, AC-15 (REQ-2 table/columns/video/menubar mapping; REQ-10 context-menu policy: `NoContextMenu` in COMPACT/VIDEO, `DefaultContextMenu` restored in NORMAL).

- [x] RED: write widget tests: default config → NORMAL (table visible, columns 0–2 visible, video visible, menu bar visible, `DefaultContextMenu` on table and video); `_apply_layout(COMPACT)` → columns 1–2 hidden, column 0 visible, menu bar hidden, `NoContextMenu` on table/video; `_apply_layout(VIDEO)` → table hidden, menu bar hidden, `NoContextMenu`; back to NORMAL → columns and menu bar visible again with `DefaultContextMenu`; startup from `config['view_mode'] == 'compact'` → window starts in COMPACT; run and confirm FAIL (method missing). <!-- sdd-owner: implementation -->
- [x] GREEN: implement `_apply_layout(mode: ViewMode)` in `IPTVMainWindow` per D3 (NORMAL: show table, unhide columns 0–2, `menuBar().show()`, set `DefaultContextMenu`; COMPACT: show table, hide columns 1–2, `menuBar().hide()`, `NoContextMenu`; VIDEO: hide table, `menuBar().hide()`, `NoContextMenu`); instantiate the controller in `__init__`, register a listener calling `_apply_layout`, and call `_apply_layout(controller.mode)` after `_setup_ui`/`_create_menus` so persisted modes apply at startup; confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: ensure `_apply_layout` never touches QAction `setEnabled` (REQ-9 constraint), and run the full suite. <!-- sdd-owner: implementation -->

**Verify:** layout tests green. **Rollback:** revert layout code in `main_window.py` + the layout tests; fakes from WU 3.1 remain.

### WU 3.3 — Mode shortcuts `ALT+1..4` and idempotent no-op (REQ-3)

**Files:**
- Modify: `src/infrastructure/ui/main_window.py`
- Modify: `tests/test_main_window.py`

**AC:** AC-4, REQ-3 — window-level shortcuts switch modes from any state; re-pressing the active mode's shortcut is a no-op (no layout re-apply, no `save_callback`).

- [x] RED: with the menu bar visible, `qtbot.keyClick(window, Qt.Key.Key_2, Qt.KeyboardModifier.AltModifier)` → mode becomes COMPACT; `Alt+3` → VIDEO; `Alt+1` → NORMAL; re-pressing the active mode's shortcut → no listener re-apply (spy on `_apply_layout` or controller listener) and no `save_callback`; run and confirm FAIL. <!-- sdd-owner: implementation -->
- [x] GREEN: register `QShortcut(self, QKeySequence("Alt+1"), ...)` for `1..3` → `view_controller.activate(...)`, and `Alt+4` → the PIP toggle hook (stub `_toggle_pip()` that raises/records until WU 4.2 — register the shortcut now, implement the body in WU 4.2); on a real mode change persist `config['view_mode'] = mode.value` and invoke `save_callback`; confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: centralize the key table in a single `_register_shortcuts()` method; full suite green. <!-- sdd-owner: implementation -->

**Verify:** shortcut tests green. **Rollback:** revert shortcut registration + tests.

### WU 3.4 — Re-target after mode switch (REQ-7)

**Files:**
- Modify: `src/infrastructure/ui/main_window.py`
- Modify: `tests/test_main_window.py`

**AC:** AC-16 (first half) — exactly one `initialize_display(int(video_widget.winId()))` per mode switch, `winId()` re-read at call time.

- [x] RED: with `FakePlaybackManager` recording, switch NORMAL→COMPACT via `Alt+2` and assert exactly one `initialize_display` recorded whose id equals `int(window.video_widget.winId())` at that moment; run and confirm FAIL (no re-target yet). <!-- sdd-owner: implementation -->
- [x] GREEN: call `self._playback_manager.initialize_display(int(self.video_widget.winId()))` as the final step of the mode-change listener (D6), always re-reading `winId()`; confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: extract `_retarget_video()` used by both the mode-change listener and (later) PIP open/close; full suite green. <!-- sdd-owner: implementation -->

**Verify:** re-target tests green. **Rollback:** revert the re-target call + tests.

### WU 3.5 — Zapping: `↑`/`↓` in every mode (REQ-5)

**Files:**
- Modify: `src/infrastructure/ui/main_window.py`
- Modify: `tests/test_main_window.py`

**AC:** AC-9, AC-10 — zap up/down in NORMAL/COMPACT/VIDEO (incl. table hidden); wrap at both edges; empty playlist no-op; no current channel → first channel; target played via `play_channel`.

- [x] RED: with `FakePlaylistLoader` returning `[c1, c2, c3]` and `FakePlaybackManager.current_channel` set: `Key_Down` from `c1` → `play_channel(c2)` recorded; `Key_Up` in VIDEO mode from `c2` → `play_channel(c1)`; `Key_Down` from `c3` wraps to `c1`; `Key_Up` from `c1` wraps to `c3`; empty playlist → no call; `current_channel=None` → `play_channel(c1)`; arrows fire while the table has focus; run and confirm FAIL. <!-- sdd-owner: implementation -->
- [x] GREEN: add `QShortcut` for `Up`/`Down` → `_zap(-1)`/`_zap(+1)`, implementing `_zap(direction)` per D9 (`resolve_zap_index(self._last_playlist.channels, self._playback_manager.current_channel, direction)` → `play_channel(channels[idx])` when not `None`); confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: ensure no path re-targets the video on zap (playback re-attaches itself); full suite green. <!-- sdd-owner: implementation -->

**Verify:** zap tests green. **Rollback:** revert shortcuts + `_zap` + tests.

### WU 3.6 — Fullscreen axis + cursor auto-hide (REQ-4)

**Files:**
- Modify: `src/infrastructure/ui/main_window.py`
- Modify: `tests/test_main_window.py`

**AC:** AC-5, AC-6 — `F` toggles fullscreen from any mode; `Esc` exits only when fullscreen; after 3 s idle the cursor hides (`BlankCursor`); mouse move restores arrow and restarts the timer; every exit path (F-off, Esc, `closeEvent`) cancels the timer and restores a visible cursor; fullscreen state never persisted.

- [x] RED: with `showFullScreen`/`showNormal` monkeypatched to recording stubs and the `_fullscreen_active` mirror: `Key_F` → `_fullscreen_active` True + `showFullScreen` called; `Key_F` again → False + `showNormal`; `Key_Escape` while fullscreen exits; `Key_Escape` while windowed is a no-op; invoking `_on_cursor_timeout()` directly sets `BlankCursor`; a synthesized `QEvent.Type.MouseMove` restores arrow and restarts the (spied) timer; exiting fullscreen stops the timer and leaves no blank cursor; `closeEvent` while fullscreen restores windowed state; run and confirm FAIL. <!-- sdd-owner: implementation -->
- [x] GREEN: implement D5 — `F` toggle, `Esc` → `_exit_fullscreen()` (single exit path: stop timer, `unsetCursor()`, remove event filter, `showNormal()`), 3000 ms single-shot `QTimer`, event filter on self/central/splitter/table/video reacting to `MouseMove`, `_fullscreen_active` mirror, `closeEvent` routing through `_exit_fullscreen()`; confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: confirm `_exit_fullscreen()` is the only place cursor/timer state is torn down; full suite green. <!-- sdd-owner: implementation -->

**Verify:** fullscreen tests green. **Rollback:** revert fullscreen code + tests.

### WU 3.7 — Splitter save/restore + pre-hide snapshot (REQ-8)

**Files:**
- Modify: `src/infrastructure/ui/main_window.py`
- Modify: `tests/test_main_window.py`

**AC:** AC-8 — splitter sizes persist across sessions via `saveState`/`restoreState`; the collapsed VIDEO state never clobbers the saved state (synchronous pre-hide snapshot); restarting in VIDEO and returning to NORMAL restores the persisted sizes.

- [x] RED: with the splitter handle moved to known sizes: debounce timer flush writes `config['splitter_state']` as base64 of `bytes(splitter.saveState())`; entering VIDEO writes the pre-hide snapshot synchronously and the debounce handler is skipped while the table is hidden; building a window from a saved `splitter_state` and switching to NORMAL restores equal sizes; run and confirm FAIL. <!-- sdd-owner: implementation -->
- [x] GREEN: implement D4 — debounced single-shot `QTimer` (300 ms) armed on `splitterMoved` (skipped while table hidden), synchronous `splitter.saveState()` snapshot on entering VIDEO before hiding the table, restore via `_splitter_snapshot` then `decode_splitter_state(config['splitter_state'])` fallback, one restore at startup; confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: verify save/restore round-trips sizes (not just handle positions) and the full suite is green. <!-- sdd-owner: implementation -->

**Verify:** splitter tests green. **Rollback:** revert splitter persistence + tests.

### WU 3.8 — Menu shortcuts stay active in COMPACT/VIDEO (REQ-9)

**Files:**
- Modify: `src/infrastructure/ui/main_window.py` (only if needed — should be a no-op for production code)
- Modify: `tests/test_main_window.py`

**AC:** AC-14 — in COMPACT/VIDEO every menu QAction reports `isEnabled() == True` and `Ctrl+G` opens the EPG grid; after returning to NORMAL the menu bar is visible again and `Ctrl+G` still works.

- [x] RED: in COMPACT and VIDEO: assert every `menuBar().actions()`-derived QAction `isEnabled() == True`; patch `EPGGridDialog` with a recorder stub and fake `EPGManager` data, then `qtbot.keyClick(window, Qt.Key.Key_G, Qt.KeyboardModifier.ControlModifier)` → dialog recorded; in VIDEO → NORMAL via `Alt+1` → menu bar visible, `Ctrl+G` still recorded; run and confirm the COMPACT/VIDEO cases FAIL (menu bar hidden but actions may be disabled / EPG not reachable). <!-- sdd-owner: implementation -->
- [x] GREEN: this must pass with **no** `setEnabled(False)` anywhere — if the existing EPG action or any QAction was disabled by earlier code, remove that disabling; confirm the shortcut path (`view_epg_action.trigger()`) fires while the menu bar is hidden; tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: grep the window for `setEnabled(False)` to prove none exists; full suite green. <!-- sdd-owner: implementation -->

**Verify:** menu-liveness tests green. **Rollback:** revert only the disabling-code removal (should be nothing) + tests.

**PR 3 boundary:** push as its own PR. If the PR 3 diff approaches 400 lines at apply time, split it (e.g. layout+shortcuts+zap vs. fullscreen+splitter+menu) — this is the `ask-on-risk` decision point flagged in the forecast.

---

## PR 4 — PIP window (pytest-qt)

### WU 4.1 — `PIPWindow` + `ResizeGrip` component (REQ-6)

**Files:**
- Create: `src/infrastructure/ui/components/pip_window.py`
- Modify: `tests/test_main_window.py`

**AC:** REQ-6 (partial) — frameless `Tool | FramelessWindowHint | WindowStaysOnTopHint` flags; draggable by body press/move; bottom-right `ResizeGrip` resize with a minimum size; `keyPressEvent` forwards every key to the target widget.

- [x] RED: component-level pytest-qt tests: `PIPWindow(key_forward_target)` has the three window flags; `set_video_widget(widget)` re-parents the widget; body drag (synthesized `MouseButtonPress`/`MouseMove` with `LeftButton`) moves the window; grip drag resizes with `geometry().width()/height()` >= minimum; `qtbot.keyClick(pip_window, Key_Down)` → the target's `keyPressEvent` receives a key event with `Key_Down`; run and confirm FAIL (module missing). <!-- sdd-owner: implementation -->
- [x] GREEN: implement `ResizeGrip(QWidget)` (records drag start, resizes parent from global delta, min 160×90) and `PIPWindow(QWidget)` per D7 (flags `Tool | FramelessWindowHint | WindowStaysOnTopHint`; body press/move drag; `keyPressEvent` → `QApplication.sendEvent(self._key_forward_target, event)`); confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: verify the grip and body drag paths are mutually exclusive (grip is a child widget) and no stale geometry is emitted; full suite green. <!-- sdd-owner: implementation -->

**Verify:** component tests green. **Rollback:** delete `pip_window.py` + tests; window does not import it yet.

### WU 4.2 — PIP toggle, reparent, and never auto-opens (REQ-6)

**Files:**
- Modify: `src/infrastructure/ui/main_window.py`
- Modify: `tests/test_main_window.py`

**AC:** AC-11, AC-12 — `P` or `Alt+4` toggles `pip_open`; opening re-parents the existing `video_widget` into the lazy `PIPWindow` and hides the main placeholder; closing returns the widget to the splitter (index 1) with per-mode visibility restored; PIP never auto-opens at launch even with persisted geometry.

- [x] RED: widget tests: `Key_P` → `pip_window` visible, video widget parented to it, main splitter no longer contains the video widget; `Key_P` again → widget back at `splitter.widget(1)`, placeholder visibility per current mode; `Alt+4` opens and closes the same PIP instance (no second window); a window built from `config['pip_geometry'] = "1280,40,480,270"` shows no PIP window at launch; run and confirm FAIL (toggle missing). <!-- sdd-owner: implementation -->
- [x] GREEN: implement `_toggle_pip()` per D7 (lazy-create/reuse `PIPWindow`; open: `setParent`, apply geometry, show, `pip_open = True`; close: hide, `setParent(splitter)` + `splitter.insertWidget(1, video_widget)`, `pip_open = False`, `_apply_layout(current mode)`); wire `P` and complete the `Alt+4` shortcut from WU 3.3; confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: confirm no startup path instantiates or shows `PIPWindow`; full suite green. <!-- sdd-owner: implementation -->

**Verify:** PIP toggle tests green. **Rollback:** revert PIP integration in `main_window.py` + tests; keep `pip_window.py`.

### WU 4.3 — PIP geometry persistence and restore (REQ-8, REQ-6)

**Files:**
- Modify: `src/infrastructure/ui/main_window.py`
- Modify: `tests/test_main_window.py`

**AC:** AC-13 — drag/resize records `pip_geometry` (debounced) into `config` and persists via `save_callback`; reopening with a valid persisted geometry restores it; invalid or missing geometry → default placement; off-screen geometry clamps to the primary screen.

- [x] RED: drag the PIP body and flush the debounce timer → `config['pip_geometry'] == geometry_to_str(*pip.geometry().getRect()[:4])` and `save_callback` received the dict; resize via grip → geometry updated and persisted; build a window with `pip_geometry = "100,100,480,270"`, open PIP → `pip_window.geometry()` matches; `pip_geometry = "garbage"` → default geometry, no crash; run and confirm FAIL. <!-- sdd-owner: implementation -->
- [x] GREEN: implement D7 geometry handling — apply `str_to_geometry(config['pip_geometry'])` on open else default (e.g. 480×270, 20 px margin top-right of the primary screen), debounced (300 ms) save timer on move/resize writing `config['pip_geometry']`, and the off-screen clamp heuristic; confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: confirm geometry writes never fire when the PIP is closed (debounce canceled on close); full suite green. <!-- sdd-owner: implementation -->

**Verify:** PIP geometry tests green. **Rollback:** revert geometry persistence + tests.

### WU 4.4 — Re-target on PIP open/close (REQ-7)

**Files:**
- Modify: `src/infrastructure/ui/main_window.py`
- Modify: `tests/test_main_window.py`

**AC:** AC-16 (second half) — exactly two `initialize_display` calls for open+close, each with the `winId()` valid at that moment.

- [x] RED: with the recording `FakePlaybackManager`: open PIP then close → exactly two `initialize_display` calls, each id equal to `int(video_widget.winId())` at that instant (ids may differ across reparent); run and confirm FAIL (no calls yet). <!-- sdd-owner: implementation -->
- [x] GREEN: call the WU 3.4 `_retarget_video()` helper after PIP open and after PIP close (re-read `winId()` each time, never cache); confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: assert the total call count across a mode switch + PIP cycle matches expectations; full suite green. <!-- sdd-owner: implementation -->

**Verify:** re-target tests green. **Rollback:** revert the two re-target calls + tests.

### WU 4.5 — PIP key forwarding (REQ-6)

**Files:**
- Modify: `src/infrastructure/ui/main_window.py`
- Modify: `tests/test_main_window.py`

**AC:** REQ-6 (last scenario), REQ-9 under PIP focus — with the PIP focused, `↑`/`↓` zap, `P` toggles, `Alt+1..3` switch modes, `F`/`Esc` work, `Ctrl+G` opens the EPG grid.

- [x] RED: open the PIP, then `qtbot.keyClick(pip_window, Qt.Key.Key_Down)` → `play_channel(next)` recorded; `qtbot.keyClick(pip_window, Key_P)` → PIP closes; `qtbot.keyClick(pip_window, Key_Alt+2)` → mode COMPACT; `qtbot.keyClick(pip_window, Key_Ctrl+G)` → EPG dialog stub recorded; run and confirm FAIL (dispatch path missing). <!-- sdd-owner: implementation -->
- [x] GREEN: implement D8 — main window `keyPressEvent` → `_dispatch_key_event(event)` (skip if `event.isAccepted()`), handling the full key table (`Alt+1..4`, `P`, `F`, `Esc`, `Up`/`Down`, `Ctrl+G` → `view_epg_action.trigger()`); `PIPWindow` forwarding (WU 4.1) delivers keys to the main window; confirm tests PASS. <!-- sdd-owner: implementation -->
- [x] REFACTOR: prove no double-dispatch (a key consumed by a `QShortcut` never re-enters `_dispatch_key_event`); full suite green. <!-- sdd-owner: implementation -->

**Verify:** forwarding tests green. **Rollback:** revert `keyPressEvent`/`_dispatch_key_event` + tests.

**PR 4 boundary:** push as its own PR — PIP is fully self-contained behind the window integration from PR 3.

---

## Final verification

### WU 5.1 — Real-engine manual smoke test (REQ-11)

**Files:** none (evidence recorded in `openspec/changes/view-modes/verify-report.md` / archive report)

**AC:** REQ-11 — with real VLC and real mpv engines: mode switches keep the video attached and correctly sized; PIP open/drag/resize/close keeps the stream following the widget; fullscreen hides the cursor after 3 s and restores it on mouse move; `Alt+1..4` pass through the Windows native menu bar.

- [ ] Run the app with a real channel playing on VLC, then on mpv; switch NORMAL→COMPACT→VIDEO→NORMAL, open/drag/resize/close PIP, toggle fullscreen and wait 3 s for the cursor to hide, move the mouse to restore it; record results as manual evidence (with the exact steps and pass/fail notes) in the verify/archive report. <!-- sdd-owner: implementation -->
- [ ] Run the complete automated suite once more (`pytest tests/ -q`) and record the final green result alongside the smoke evidence. <!-- sdd-owner: implementation -->

**Rollback:** this WU changes nothing; a failure here blocks archiving, not delivery.

---

## Parent-owned gates (after implementation, grouped)

- [ ] Review the full change against this task list and the spec AC table (AC-1..AC-16); verify every scenario is covered by a test or the manual smoke evidence, and confirm the chained-PR slicing decision (PR 3 may need a further split at the ~400-line boundary). <!-- sdd-owner: parent -->
- [ ] After the last PR merges, run `sdd-verify` and, on PASS, `sdd-archive` recording the REQ-11 smoke evidence; if verification fails, route remediation back to the failing work unit. <!-- sdd-owner: parent -->
