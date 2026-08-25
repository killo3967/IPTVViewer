# View Modes — Design

**Change:** `view-modes`
**Status:** Designed
**Companions:** `openspec/changes/view-modes/proposal.md`, `openspec/changes/view-modes/spec.md`
**Backend:** OpenSpec (file-backed)

## 1. Overview

This design implements three exclusive layout modes (NORMAL / COMPACT / VIDEO), an
orthogonal fullscreen axis with cursor auto-hide, keyboard channel zapping with
wrap-around, and a detached always-on-top PIP window. Layout mode, splitter geometry,
and PIP geometry persist across sessions; fullscreen state and PIP visibility do not.

Architectural spine: a **Qt-free application service** (`ViewModeController`) owns all
pure state and math (mode state machine, serialization, zap index resolution, geometry
parsing). The Qt adapter (`IPTVMainWindow`) observes the controller and applies the
widget-visibility mapping. A new `PIPWindow` component hosts the detached video widget.

Key resolved decisions carried forward from the spec:

- PIP uses the **DETACH** model — the single `video_widget` is re-parented; no second
  player instance.
- Zap edges **wrap around**; empty playlist is a no-op; no current channel → index 0.
- Menu QActions are **never disabled**; hidden menu bar keeps `Ctrl+G` alive.
- PIP **never auto-opens** at launch; only geometry persists.

## 2. Context and current state

Current relevant code (verified):

- `main.py`: `load_config()` reads `config.ini` into a flat dict (`sources`, `active`,
  `hw_acceleration`, `player_engine`, `vlc_config`, `mpv_config`, `proxy_config`);
  `save_config(config_data)` **enumerates known keys only** and rebuilds `[SETTINGS]`
  from scratch — any new key is silently dropped on save. `CONFIG_FILE` is a module
  global with no injection seam.
- `src/infrastructure/ui/main_window.py` (`IPTVMainWindow`): single horizontal
  `QSplitter` with a 3-column `QTableWidget` (Canal / Logo / Programación) + a black
  `video_widget`; `initialize_display(int(video_widget.winId()))` is called once in
  `_setup_ui`; no `keyPressEvent` override; menu bar always visible; `Ctrl+G` is a
  QAction shortcut (`view_epg_action`) on the "Ver Parrilla EPG" action.
- `PlaybackManager` exposes `play_channel(channel)`, `initialize_display(window_id)`
  (→ `player.set_output_window`), `stop_playback()`, and the `current_channel`
  property. `Channel` is a frozen dataclass (`name`, `url`, `group`, `logo_url`,
  `tvg_id`); `Playlist` exposes `.channels` and is iterable/len-able.
- `tests/` use plain-pytest style fakes (e.g. `FakePlayer` implementing `IPlayer`);
  there is no `test_main_window.py` yet (new) and no pytest-qt usage yet (new).

## 3. Design decisions

### D1 — `ViewModeController`: Qt-free pure controller (REQ-1, REQ-8)

New file `src/application/services/view_mode_controller.py` with **zero `PyQt6`
imports**. Contents:

```python
from enum import Enum
from typing import Callable, Optional, Sequence

class ViewMode(Enum):
    NORMAL = "normal"
    COMPACT = "compact"
    VIDEO = "video"

    @classmethod
    def parse(cls, raw: object) -> "ViewMode":
        # Unknown/None -> NORMAL; never raises.
        ...

class ViewModeController:
    def __init__(self, initial: ViewMode = ViewMode.NORMAL): ...
    @property
    def mode(self) -> ViewMode: ...

    def activate(self, mode: ViewMode) -> bool:
        # True iff state changed. On change, notify listeners with (old, new).
        # Re-activating the active mode returns False and emits nothing (REQ-1).

    def register_listener(self, listener: Callable[[ViewMode, ViewMode], None]) -> None: ...
```

- The controller owns **only** the mode state machine. Fullscreen and PIP are window
  session state owned by `IPTVMainWindow` (they are not persisted and never affect the
  mode), so they do not live in the controller. This keeps the controller's contract
  minimal and its tests plain-pytest.
- Listener notification is the Qt-free observer mechanism (a list of callables). The
  main window registers a bound method that applies the layout mapping (D3). Because
  `activate()` returns `False` without notifying on no-op, "layout is not re-applied"
  (REQ-3) falls out of the controller contract and is asserted with a spy listener.
- `parse()` is the single entry for persisted strings: unknown values (e.g. `"cinema"`)
  fall back to `NORMAL` without raising (REQ-1 scenario).

Pure helpers in the same module (no Qt types — tuples/str/bytes only):

```python
def resolve_zap_index(channels: Sequence, current_channel, direction: int) -> Optional[int]
    # direction: -1 (up) or +1 (down). Returns None if empty. No current channel
    # (or current not found in the playlist) -> 0. Edges wrap (modulo). (REQ-5)

def geometry_to_str(x: int, y: int, w: int, h: int) -> str            # "x,y,w,h"
def str_to_geometry(raw: str) -> Optional[tuple[int, int, int, int]]   # None on invalid
def encode_splitter_state(state: bytes) -> str                         # base64 ASCII
def decode_splitter_state(encoded: str) -> Optional[bytes]             # None on invalid
```

**Decision rationale:** placing the state machine and all math in a Qt-free service
makes every transition, serialization edge, and wrap case testable with plain pytest
(no display, no event loop), per REQ-1/REQ-5/REQ-8. The tuple-based geometry helpers
avoid leaking `QRect` into the service layer; `main.py` and the window convert at the
boundary.

**Zap index resolution details (REQ-5):**

- Empty playlist → `None` (caller no-ops).
- `current_channel is None` → `0`.
- Current channel not found in the playlist (e.g. stale `current_channel` after
  playlist switch) → treat as no current → `0`.
- Found at index `i`: up → `(i - 1) % n`; down → `(i + 1) % n` (wrap-around).
- Matching is by URL first (`c.url == current_channel.url`), falling back to full
  dataclass equality — URL identity is the stable key for a stream; full equality
  covers channels duplicated across sources with identical payloads. (Assumption from
  spec §"Zap index"; documented so the fake-based tests match real behavior.)

**Geometry parsing details (REQ-8):**

- `str_to_geometry`: must be exactly 4 comma-separated integers; `w > 0` and `h > 0`
  required; `x`/`y` may be negative (multi-monitor). Any other input (wrong count,
  non-int, empty) → `None` → caller uses default geometry. Never raises.
- `decode_splitter_state`: `base64.b64decode` wrapped in try/except → `None` on any
  error (so a corrupted `config.ini` never crashes startup).

### D2 — Persistence: mandatory `main.py` extension (REQ-8)

`main.py` `load_config()` / `save_config()` gain an optional `config_path` parameter
(defaulting to the module-level `CONFIG_FILE`) so round-trip tests are hermetic — no
monkeypatching of `CONFIG_FILE` needed.

Three new flat keys in the config dict, serialized in `[SETTINGS]`:

| Key | Dict value type | Serialized form | Default |
|---|---|---|---|
| `view_mode` | `str` | `normal` \| `compact` \| `video` | `"normal"` |
| `splitter_state` | `str` (base64) | base64 ASCII string | `""` |
| `pip_geometry` | `str` | `x,y,w,h` | `""` |

- `load_config()` reads all three with `parser.get('SETTINGS', key, fallback='')` and
  normalizes `view_mode` through `ViewMode.parse(...).value` so an invalid persisted
  value is normalized to `'normal'` at load time. `splitter_state` and `pip_geometry`
  are stored verbatim (empty string when missing); parsing/validation happens at the
  consumer (window) via the controller helpers.
- `save_config()` adds the three keys to the `parser['SETTINGS']` dict:
  `config_data.get('view_mode', 'normal')`, `config_data.get('splitter_state', '')`,
  `config_data.get('pip_geometry', '')`. All values are `str`, so `configparser` never
  receives `None`.
- **Round-trip safety:** base64 alphabet (`A–Z a–z 0–9 + / =`) and digits/commas contain
  no `%`, so `ConfigParser` interpolation never corrupts them; the values are
  newline-free. Legacy `config.ini` files without the keys load with defaults and are
  untouched until the next save (which then adds the keys — harmless, per proposal
  rollback note).

Callers of `load_config()`/`save_config()` inside `main.py` (including the
`save_callback` wired into `IPTVMainWindow`) are updated to pass the new parameter
through where needed; default behavior outside tests is unchanged.

### D3 — Layout mapping in `IPTVMainWindow` (REQ-2, REQ-10)

The window owns the widgets and applies the mapping; it never decides state itself.

| Mode | Table | Columns | Video | Menu bar | Context menu |
|---|---|---|---|---|---|
| NORMAL | visible | 0, 1, 2 visible | visible | `show()` | `DefaultContextMenu` on table and video |
| COMPACT | visible | 1, 2 hidden via `setColumnHidden` | visible | `hide()` | `NoContextMenu` on table and video |
| VIDEO | `hide()` | — | visible (fills) | `hide()` | `NoContextMenu` on table and video |

Single method `_apply_layout(mode: ViewMode)`:

1. `NORMAL`: `table.show()`; unhide columns 0–2; `menuBar().show()`; set
   `DefaultContextMenu` on table and video; restore saved splitter state if a
   pre-hide snapshot exists (D4).
2. `COMPACT`: `table.show()`; `table.setColumnHidden(1, True)` /
   `setColumnHidden(2, True)`; `menuBar().hide()`; `NoContextMenu` on table and video.
3. `VIDEO`: save splitter snapshot first (D4); `table.hide()`; `menuBar().hide()`;
   `NoContextMenu` on table and video. The splitter then stretches the single visible
   video widget automatically.

**Context-menu note (REQ-10):** the current code never sets a policy (Qt default
`DefaultContextMenu`). NORMAL explicitly resets `DefaultContextMenu` so switching
COMPACT→NORMAL restores the original behavior exactly.

**Menu bar and shortcuts (REQ-9):** `_apply_layout` only ever calls
`menuBar().show()` / `menuBar().hide()`. **No QAction is ever `setEnabled(False)`.**
Hiding the menu bar does not unregister QAction shortcuts, so `Ctrl+G` keeps firing in
COMPACT/VIDEO when the main window (or any of its children) has focus — this is
exactly the behavior REQ-9 demands.

**Mode-change sequence (called from the controller listener):**

1. If new mode is VIDEO and old mode was NORMAL/COMPACT: capture
   `splitter.saveState()` → keep in-memory snapshot `self._splitter_snapshot` and write
   it into `config['splitter_state']` + save **before** hiding the table (prevents the
   collapsed state from being persisted).
2. `_apply_layout(new_mode)`.
3. Re-target the player output (D6).
4. If mode actually changed: `config['view_mode'] = new_mode.value`; save via
   `save_callback`.

`_apply_layout` runs on startup too (after `_setup_ui` / `_create_menus`), so a
persisted `view_mode` starts the window in that mode (AC-1/AC-7).

### D4 — Splitter state save/restore (REQ-8)

- **Live persistence:** a debounced `QTimer` (single-shot, 300 ms) is armed on
  `splitter.splitterMoved`. On timeout, `config['splitter_state'] =
  encode_splitter_state(bytes(self.splitter.saveState()))` and `save_callback`.
  The debounce handler is skipped while the table is hidden (VIDEO), so the collapsed
  state can never clobber the persisted good state.
- **Pre-hide snapshot:** entering VIDEO captures the pre-hide state **synchronously**
  (step 1 of the mode-change sequence) and persists it immediately — this is the
  authoritative "saved before the table is hidden" state (REQ-8 scenario).
- **Restore:** returning to NORMAL restores `self._splitter_snapshot` first (live
  session), falling back to `decode_splitter_state(config['splitter_state'])` when the
  snapshot is absent (e.g. startup in VIDEO → later NORMAL). At startup, after UI
  setup, a valid persisted `splitter_state` is restored once (AC-8).
- `QSplitter.saveState()` returns `QByteArray`; convert with `bytes(...)` on save.
  `restoreState(...)` accepts Python `bytes` in PyQt6. Sizes (not just handle
  positions) round-trip because `saveState` encodes the full size list.

### D5 — Fullscreen axis with cursor auto-hide (REQ-4)

Window state (session-only, never persisted):

- `F` toggles: if `self.isFullScreen()` → `_exit_fullscreen()`; else `showFullScreen()`,
  arm the hide timer, enable mouse tracking on self + central widget tree.
- `Esc` → `_exit_fullscreen()` (no-op when not fullscreen).
- `_enter_fullscreen()`: `showFullScreen()`; `self._cursor_timer = QTimer(self)`
  (single-shot, 3000 ms) with timeout → `self.setCursor(Qt.CursorShape.BlankCursor)`;
  install the window as an event filter on itself and the central widget, splitter,
  table, and video widget.
- `_exit_fullscreen()`: **single exit path used by F-off, Esc, and `closeEvent`** —
  `self._cursor_timer.stop()`, `self.unsetCursor()` (arrow restored — no blank-cursor
  leak), remove the event filter, `showNormal()`. Every exit path routes here.
- `eventFilter(self, obj, event)`: on `QEvent.Type.MouseMove` → `unsetCursor()` and
  restart the timer (arrow reappears, 3 s countdown restarts). The filter approach
  catches mouse moves over child widgets (table/video), not just the window frame.
- The window keeps a `_fullscreen_active: bool` mirror (updated in enter/exit) so
  headless tests can assert axis state even when the `offscreen` platform makes
  `isFullScreen()` unreliable; production behavior is driven by Qt's real state.

**Test surface:** tests invoke `_on_cursor_timeout()` directly (headless-safe),
synthesize a mouse-move event, and assert timer state (`isActive()`) + cursor shape.
They monkeypatch `showFullScreen`/`showNormal` with recording stubs where window-level
asserts are needed.

### D6 — Video re-targeting after every visibility change (REQ-7)

`PlaybackManager.initialize_display(int(video_widget.winId()))` is re-invoked:

- at the end of every mode switch (`_apply_layout` step 3) — exactly once per switch;
- after PIP open (re-parent into PIP) and after PIP close (re-parent back) — one call
  per reparent;
- at startup (existing `_setup_ui` call, unchanged).

The `winId()` is **re-read at call time, never cached**: it can change across
`setParent` and hide/show, so any cached id would re-target a stale native handle.
The re-target is a no-op-safe call (the player just re-binds its output window) even
when playback is idle. Tests use a recording fake and assert the call count and that
the id equals the widget's `winId()` at that moment (REQ-7 scenarios).

### D7 — PIP: detached always-on-top window (REQ-6)

New file `src/infrastructure/ui/components/pip_window.py`:

```python
class ResizeGrip(QWidget):
    # Bottom-right grip. mousePressEvent records the drag start; mouseMoveEvent
    # with LeftButton resizes the parent window from the global-position delta,
    # enforcing a minimum size (e.g. 160x90). Emits/notifies on geometry change.
    ...

class PIPWindow(QWidget):
    def __init__(self, key_forward_target: QWidget): ...
    # Flags: Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
    #        | Qt.WindowType.WindowStaysOnTopHint
    # Layout: video container (the reparented video_widget) + ResizeGrip aligned
    # bottom-right.
    def set_video_widget(self, widget: QWidget) -> None: ...   # reparent helper
    def keyPressEvent(self, event) -> None:                    # forward to target
```

Window behavior:

- **Open (`P` or `ALT+4`)**: if `pip_open` → close path; else create (lazy singleton
  on first use) or reuse the `PIPWindow`; `video_widget.setParent(pip_window)`; apply
  persisted geometry if valid (`str_to_geometry(config['pip_geometry'])` → `setGeometry`)
  else default (e.g. 480×270 at top-right of the primary screen, 20 px margin); set
  `pip_open = True`; `pip_window.show()`; re-target (D6). The main window's splitter no
  longer contains the video widget — the placeholder is gone by construction (DETACH).
- **Close**: `pip_window.hide()`; `video_widget.setParent(splitter)`;
  `splitter.insertWidget(1, video_widget)` (restores table-left / video-right order);
  `pip_open = False`; `_apply_layout(current mode)` (re-applies per-mode visibility);
  re-target (D6).
- **Drag**: `PIPWindow.mousePressEvent` records the offset; `mouseMoveEvent` with
  `LeftButton` moves the window via `move(global_pos - offset)`. Grip and body events
  are naturally separated because the grip is a child widget.
- **Resize**: `ResizeGrip` adjusts the window size with a minimum bound.
- **Geometry persistence**: after every move/resize, arm the debounced save timer
  (300 ms) → `config['pip_geometry'] = geometry_to_str(*pip_window.geometry().getRect()[:4])`
  → save. (Debounce optional per spec; used to avoid write storms.)
- **Never auto-opens at launch**: no startup path instantiates or shows `PIPWindow`.
  Only the geometry string is loaded into the config dict (REQ-6 scenario).
- **Always on top**: `WindowStaysOnTopHint` (plus `Tool` so it stays above the main
  window and dialogs and has no taskbar entry). Documented limitation: `Tool` windows
  may hide when the app loses focus on some platforms (Windows shows them above the
  owner); accepted for v1 and covered by the manual smoke test.
- **Key forwarding**: `PIPWindow.keyPressEvent` forwards **every** key event to the
  main window (spec assumption 3) via `QApplication.sendEvent(self._key_forward_target, event)`.
  The main window's `keyPressEvent` (D8) then dispatches it, so `↑/↓/P/ALT+1..4/F/Esc`
  and `Ctrl+G` keep working while the PIP has focus (REQ-6 scenario).

`PIPWindow` is created **lazily on first open** and kept alive (hidden) afterwards, so
closing and reopening does not rebuild native handles repeatedly.

### D8 — Key dispatch: shortcuts + `keyPressEvent` fallback (REQ-3, REQ-5, REQ-6)

Two complementary paths, both funnelling into one handler table:

| Key(s) | Effect |
|---|---|
| `Alt+1` | `view_controller.activate(ViewMode.NORMAL)` |
| `Alt+2` | `view_controller.activate(ViewMode.COMPACT)` |
| `Alt+3` | `view_controller.activate(ViewMode.VIDEO)` |
| `Alt+4` / `P` | toggle PIP (D7) |
| `F` | toggle fullscreen (D5) |
| `Esc` | `_exit_fullscreen()` (no-op when not fullscreen) |
| `Up` / `Down` | zap previous/next (D9) |
| `Ctrl+G` | `view_epg_action.trigger()` |

- **Focused-in-main-window path:** `QShortcut(self, QKeySequence(...))` with default
  `Qt.WindowShortcut` context for `Alt+1..4`, `P`, `F`, `Esc`, `Up`, `Down`. This is
  the spec-mandated registration (REQ-3) and it works even when a **child** (the table)
  has focus — `WindowShortcut` fires for any focus inside the window. When a shortcut
  fires, Qt accepts the event, so the table never sees the arrow keys (arrow-key row
  navigation in the table is deliberately replaced by zapping, matching REQ-5's "in
  every mode"; click-to-play in NORMAL is unchanged).
- **PIP-focus path:** forwarded key events (D7) arrive at the main window's
  `keyPressEvent`, which calls `_dispatch_key_event(event)`. `_dispatch_key_event`
  first checks `event.isAccepted()` and skips if already accepted — this guards against
  any double-dispatch drift between the shortcut map and the forwarded path.
- `Ctrl+G` under PIP focus goes through `keyPressEvent` → `view_epg_action.trigger()`
  (the existing QAction shortcut continues to serve the main-window path; hiding the
  menu bar never disabled it — REQ-9).
- **Known risk (from proposal):** Windows native menu handling can swallow bare
  `Alt+<key>` presses when a matching mnemonic exists. No menu mnemonic is `1..4`, so
  `Alt+1..4` are expected to pass through; REQ-3's `qtbot.keyClick` scenario asserts
  this with the menu bar visible. Contingency if the real-Windows smoke test shows
  swallowing: switch the mode keys to `QShortcut` with `ApplicationShortcut` context
  (only for the view-mode keys; verified behavior change).

**Dispatch exclusivity:** zapping, mode switching, fullscreen, and PIP toggling are the
only consumers of these keys; no existing shortcut collides (verified: `Ctrl+G` only).

### D9 — Zapping (REQ-5)

`_zap(direction: int)`:

```python
channels = self._last_playlist.channels
idx = resolve_zap_index(channels, self._playback_manager.current_channel, direction)
if idx is not None:
    self._playback_manager.play_channel(channels[idx])
```

- Works in every mode (shortcut path fires regardless of layout; PIP path forwards).
- Wrap-around and empty-playlist no-op come from the pure function (D1).
- Playback goes through `play_channel`, which stops the previous stream and restarts —
  the player re-attaches to the same output window, so no extra re-target is needed
  for zapping itself.

## 4. Data flow / interaction sequences

**Mode switch (`Alt+2` in NORMAL):**

```
QShortcut(Alt+2) fires (or PIP-forwarded keyPressEvent)
  -> ViewModeController.activate(COMPACT)            # pure: state change
  -> listener: _on_view_mode_changed(NORMAL, COMPACT)
       -> _apply_layout(COMPACT)                     # hide cols 1-2, hide menubar, NoContextMenu
       -> initialize_display(int(video_widget.winId()))   # re-target, re-read id
       -> config['view_mode'] = 'compact'; save_callback(config)
```

**PIP open/close (DETACH):**

```
P (main window) -> toggle_pip()
  open:  video_widget.setParent(pip_window) -> pip_window.show() -> pip_open=True
         -> initialize_display(int(video_widget.winId()))          # winId may differ
  close: pip_window.hide() -> video_widget.setParent(splitter)
         -> splitter.insertWidget(1, video_widget) -> pip_open=False
         -> _apply_layout(current_mode) -> initialize_display(int(video_widget.winId()))
```

**Config round-trip (REQ-8):**

```
save:  config['splitter_state'] = encode_splitter_state(bytes(splitter.saveState()))
       save_config(config, path=...) -> [SETTINGS] view_mode/splitter_state/pip_geometry
load:  load_config(path=...) -> dict[str, ...] (normalized view_mode, raw strings)
start: window init -> controller(ViewMode.parse(config['view_mode']))
       -> _apply_layout(mode) -> restore splitter_state if valid -> (PIP never opens)
```

## 5. Persistence format summary

`config.ini` `[SETTINGS]` additions:

```ini
[SETTINGS]
view_mode = compact
splitter_state = <base64 of QSplitter.saveState() bytes>
pip_geometry = 1280,40,480,270
```

- Missing keys → defaults (`normal`, `""`, `""`) — legacy files open unchanged.
- All values ASCII, `%`-free → `ConfigParser` interpolation-safe.
- Controller pure helpers are the only producers/parsers of these strings; `main.py`
  does mechanical read/write only.

## 6. Testing strategy (strict TDD)

Every requirement scenario is written as a failing test first (RED), then GREEN.
Existing suite must stay green.

**Plain pytest (no Qt) — `tests/test_view_mode_controller.py`:**

| Unit | Cases |
|---|---|
| `ViewModeController` | default NORMAL; each transition; idempotent re-activation returns `False` + no listener notification; listener receives `(old, new)` only on change |
| `ViewMode.parse` | `normal/compact/video` round-trip; `"cinema"`/`None`/`""` → NORMAL without raising |
| `resolve_zap_index` | next/prev; wrap down at last → first; wrap up at first → last; empty → `None`; no current → 0; current not in playlist → 0; matching by URL and by full equality |
| `geometry_to_str` / `str_to_geometry` | round-trip; negative x/y allowed; `w<=0`/`h<=0` → `None`; wrong count / non-int / empty → `None`; never raises |
| `encode/decode_splitter_state` | base64 round-trip; garbage → `None`; never raises |

**Plain pytest — `tests/test_config_roundtrip.py`:**

| Unit | Cases |
|---|---|
| `load_config(path)` / `save_config(data, path)` | new keys survive a temp-file round-trip; legacy file without keys → defaults, no error; invalid persisted `view_mode` normalized to `'normal'` in the returned dict; `splitter_state`/`pip_geometry` empty defaults; ASCII/`%`-safety (values with `+`, `/`, `=`) |

**pytest-qt — `tests/test_main_window.py`:**

| Area | Cases |
|---|---|
| Layout mapping | per-mode visibility of table/columns/menubar; context policies (NoContextMenu in COMPACT/VIDEO, DefaultContextMenu restored in NORMAL); startup in persisted mode; startup default NORMAL |
| Shortcuts | `qtbot.keyClick` `Alt+1..4` with menu bar visible (mnemonic-swallow regression); re-pressing active mode is a no-op (layout spy records no re-apply); `Up`/`Down` fire while the table has focus |
| Fullscreen | F toggles (spied `showFullScreen`/`showNormal` + `_fullscreen_active`); Esc exits only when fullscreen; timeout handler → `BlankCursor`; synthetic mouse move → arrow + timer restarted; every exit path (F-off, Esc, closeEvent) cancels the timer and restores the cursor |
| Zapping | zap down/up in NORMAL/COMPACT/VIDEO with recording fake; wrap at both edges; empty playlist no-op; no-current → first channel; `play_channel(target)` recorded |
| Re-target | exactly one `initialize_display` after a mode switch; exactly two after PIP open+close; ids equal the widget's `winId()` at call time |
| PIP | open → frameless/Tool/`WindowStaysOnTopHint` flags, video reparented, main splitter has no video; close → widget back at splitter index 1; `P` and `Alt+4` toggle the same instance; never auto-opens at launch (config with `pip_geometry` → no PIP window); drag and grip resize change geometry and (after debounce flush) persist `pip_geometry`; restore of persisted geometry on open; key forwarding: `qtbot.keyClick(pip, Key_Down)` → `play_channel` recorded |
| Menu liveness | in COMPACT/VIDEO all menu actions `isEnabled() == True`; `Ctrl+G` opens the EPG grid (patch `EPGGridDialog` with a recorder stub; fake `EPGManager` with data); `Ctrl+G` still works under PIP focus via forwarding |

**Fakes** (module-level in test files, mirroring the existing `FakePlayer` style):
`FakePlaylistLoader` (returns a fixed `Playlist`), `FakePlaybackManager` (records
`play_channel`/`initialize_display`; settable `current_channel`), `FakeEPGManager`
(`has_data`), `FakeLogoLoader` (`QtLogoLoaderAdapter` subclass or `QObject` with the
`logo_loaded` signal).

**Manual smoke test (REQ-11, evidence recorded in the archive report):** with real VLC
and mpv engines — mode switches keep the video attached and correctly sized; PIP
open/drag/resize/close keeps the stream following the widget; fullscreen hides the
cursor after 3 s and restores it on mouse move; `Alt+1..4` pass through the Windows
native menu bar.

## 7. File changes

| File | Change |
|---|---|
| `src/application/services/view_mode_controller.py` | **NEW** — `ViewMode`, `ViewModeController`, `resolve_zap_index`, geometry + splitter-state helpers (Qt-free) |
| `src/infrastructure/ui/components/pip_window.py` | **NEW** — `PIPWindow` (Tool/frameless/always-on-top, drag, key forwarding) + `ResizeGrip` |
| `src/infrastructure/ui/main_window.py` | Mode QShortcuts + `keyPressEvent`/`_dispatch_key_event`; `_apply_layout`; fullscreen axis; PIP integration (toggle, reparent, geometry persistence); splitter save/restore; re-target calls; `closeEvent` cleanup |
| `main.py` | `load_config`/`save_config` gain `config_path` param; read/write `view_mode`, `splitter_state`, `pip_geometry` |
| `tests/test_view_mode_controller.py` | **NEW** — pure controller/math tests |
| `tests/test_config_roundtrip.py` | **NEW** — `load_config`/`save_config` round-trip on temp files |
| `tests/test_main_window.py` | **NEW** — pytest-qt widget tests (layout, shortcuts, fullscreen, zap, PIP, re-target, menu liveness) |

Playback path (`PlaybackManager`, players, playlist/EPG services) is untouched except
for the existing `initialize_display` calls being re-invoked.

## 8. Edge cases

- **Zap on empty/stale playlist** → `resolve_zap_index` returns `None` → no-op.
- **Zap while no channel current** → index 0 (assumption: symmetric for `↑`/`↓`).
- **Startup in persisted VIDEO** → table hidden from the start; no pre-hide snapshot
  exists; returning to NORMAL restores the persisted `splitter_state` (fallback path).
- **PIP close in VIDEO** → main area stays empty (table hidden), video back in splitter.
- **PIP geometry off-screen after monitor change** → on open, if the restored geometry
  does not intersect any available screen, clamp to the primary screen's default
  placement (v1 heuristic; documented, not covered by an AC).
- **Fullscreen + PIP open** → PIP remains on top (flag), may cover fullscreen content —
  accepted v1 behavior flagged in the proposal.
- **Fullscreen + close** → `closeEvent` routes through `_exit_fullscreen()`: timer
  canceled, cursor restored.
- **Config file with corrupted base64 / malformed geometry** → helpers return `None`,
  defaults apply, no crash.
- **Double-dispatch drift** between QShortcut and the forwarded key path → guarded by
  the `event.isAccepted()` check in `_dispatch_key_event`.

## 9. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| `winId()` changes across `setParent`/hide-show | High | Re-read at every re-target call site (D6); fake-asserted counts in tests; real-engine smoke test mandatory |
| Splitter state clobbered by collapsed VIDEO layout | High | Pre-hide synchronous snapshot + skip debounce while table hidden (D4) |
| Hidden menu bar keeping shortcuts alive is now the **required** behavior | Medium | REQ-9: never `setEnabled(False)`; tests assert `isEnabled() == True` in COMPACT/VIDEO |
| `Alt+1..4` swallowed by native menu handling (Windows) | Low | REQ-3 test with menu bar visible; contingency `ApplicationShortcut` context (D8) |
| Blank-cursor leak on fullscreen exit | Medium | Single `_exit_fullscreen()` path used by F-off/Esc/close; timer canceled + cursor restored (D5) |
| Offscreen platform can't fully exercise fullscreen/window flags | Low | State mirror + handler-level invocation + `showFullScreen`/`showNormal` spies (D5) |
| EPG dialog is modal (`exec()`) | Low | Tests patch `EPGGridDialog` with a recorder stub |
| PIP `Tool` window may hide when the app loses focus (platform quirk) | Low | Documented; verified in the manual smoke test |
| Arrow-key table navigation replaced by zapping | Low | Intentional per REQ-5; click-to-play preserved |

## 10. Rollout and rollback

- Purely additive UI change; no data-model or playback-path changes.
- Rollback = restore `main_window.py` / `main.py` and delete the new controller, PIP,
  and test files. Legacy `config.ini` compatibility means no migration step; leftover
  `[SETTINGS]` keys are ignored on read and overwritten on next save.
- Verification order: pure pytest suite → pytest-qt suite → existing suite → manual
  smoke test with both engines (REQ-11) before archiving.
