# View Modes — Proposal

**Change:** `view-modes`
**Status:** Proposed
**Author:** SDD proposal phase
**Affected files (predicted):**

- `src/infrastructure/ui/main_window.py` — mode switching, fullscreen, keyboard handling, PIP integration
- `src/infrastructure/ui/components/pip_window.py` — NEW: floating always-on-top video window
- `src/application/services/view_mode_controller.py` — NEW: pure, Qt-free mode state machine + persistence serialization
- `main.py` — extend `load_config()` / `save_config()` to persist new keys
- `tests/test_view_mode_controller.py` — NEW: pure state-machine tests
- `tests/test_main_window.py` — NEW: Qt widget tests (pytest-qt)

---

## 1. Problem statement and user value

Today `IPTVMainWindow` offers exactly one layout: a horizontal `QSplitter` with a
3-column `QTableWidget` (Canal / Logo / Programación) on the left and an embedded
black `video_widget` on the right, plus a permanent menu bar. The user gets no way
to adapt the UI to the moment:

- Watching a channel with the table taking half the screen wastes space and
  distracts from the video.
- A "video only" experience (ideal for movie-style viewing) is impossible without
  hacking the window.
- Fullscreen leaves a visible cursor after a few seconds, which is annoying on TV-like
  use.
- Zapping channels requires clicking rows in a table, so it is impossible while the
  table is hidden or when focus is on the video.
- There is no detached picture-in-picture window, so a small overlay view of the
  stream (while doing something else on the desktop) does not exist.

**Value:** three explicit layout modes (Normal / Compact / Video), fullscreen as an
orthogonal axis, keyboard zapping (`↑`/`↓`) that works everywhere, and a draggable,
resizable, always-on-top PIP window — each remembered across sessions. This turns
the viewer from a table-with-video window into a lean-back TV experience.

---

## 2. Scope

### In scope

1. Three layout modes with shortcuts:
   - **Normal** (`ALT+1`): current layout — 3-column table + video + menu bar.
   - **Compact** (`ALT+2`): channel column only (Logo and Programación columns
     hidden) + video, **no menu bar**, **no context menu**.
   - **Video** (`ALT+3`): video only, table hidden, **no menu bar**, **no context
     menu**.
2. Fullscreen axis: `F` toggles fullscreen from any mode; `Esc` exits fullscreen.
   Cursor auto-hides after 3 s of inactivity while fullscreen and reappears on mouse
   move.
3. Persistence across sessions (in `config.ini` / config dict): last selected mode,
   splitter geometry (table↔video sizes), PIP geometry.
4. Channel zapping: `↑` / `↓` switches to previous / next channel and starts
   playback in **all** modes, including Video mode with the table hidden.
5. **PIP (in scope)**: a floating, frameless, always-on-top window showing the
   current video stream. Opened/closed with `P` or `ALT+4`. Draggable and
   resizable; position and size remembered across sessions.
6. Feature gating: in Compact/Video there is no menu and no context menu, and menu
   action shortcuts (e.g. `Ctrl+G` for EPG) are deactivated — the user must return
   to Normal (`ALT+1`) to reach Config / EPG / lists.

### Non-goals (out of scope)

- Persisting main-window position/size across sessions (existing behavior, unchanged).
- A second, independent player instance for PIP. PIP re-targets the **same** player
  output by reparenting the existing `video_widget` (see risks).
- Channel search / filter / favorite navigation UI.
- OSD overlays, channel-name popups, or EPG overlay on the video.
- Mouse-based channel switching (click-to-play in Normal mode is preserved as-is).
- Configurable/custom shortcuts (hardcoded v1).
- Per-mode layouts beyond the table/video split; no toolbar or status bar additions.
- Persisting fullscreen state or PIP *visibility* at startup (PIP opens closed;
  fullscreen starts off; both are session-only).

---

## 3. View-mode state machine

### 3.1 Modes (exclusive)

`ViewMode` ∈ { `NORMAL`, `COMPACT`, `VIDEO` }. Exactly one mode is active at a time.

The pure state lives in a new Qt-free application service
`ViewModeController` (no `PyQt6` imports) so the transitions and the persistence
serialization are unit-testable with plain pytest. The Qt adapter
(`IPTVMainWindow`) observes the controller and applies the widget-visibility
mapping:

| Mode | Table | Columns shown | Video | Menu bar | Menu shortcuts | Context menu |
|---|---|---|---|---|---|---|
| NORMAL | visible | 0, 1, 2 | visible | visible | enabled | default |
| COMPACT | visible | 0 only (1, 2 hidden) | visible | hidden | **disabled** | `NoContextMenu` |
| VIDEO | hidden | — | visible (fills area) | hidden | **disabled** | `NoContextMenu` |

Mode transitions:

- `ALT+1` → `NORMAL` from any mode.
- `ALT+2` → `COMPACT` from any mode.
- `ALT+3` → `VIDEO` from any mode.
- Re-selecting the active mode is a no-op (idempotent).

### 3.2 Fullscreen — orthogonal axis

`fullscreen: bool`, independent of the mode and of PIP:

- `F` toggles `fullscreen` (show/hide fullscreen) in any mode; `Esc` sets it to
  `False` (only meaningful while fullscreen; otherwise no-op).
- While `fullscreen == True`: a 3 s inactivity `QTimer` hides the cursor
  (`Qt.CursorShape.BlankCursor`); any mouse move restores the arrow cursor and
  restarts the timer.
- Exiting fullscreen restores the pre-fullscreen window state (`showNormal()`).
- Fullscreen state is **not** persisted.

### 3.3 PIP — auxiliary floating window

`pip_open: bool`, orthogonal to mode and fullscreen.

- `P` or `ALT+4` toggles `pip_open` from anywhere.
- v1 semantics (recommended): opening PIP **reparents the existing `video_widget`**
  into a new frameless, always-on-top `PIPWindow`
  (`Qt.WindowType.Tool | FramelessWindowHint | WindowStaysOnTopHint`). While PIP is
  open, the main window's video placeholder is hidden (the splitter then shows the
  table only). Closing PIP moves the widget back into the splitter.
- Single player output is preserved: after any reparent, the player output is
  re-targeted via `playback_manager.initialize_display(int(video_widget.winId()))`.
- PIP is draggable (mouse press/move on the window body) and resizable (a
  bottom-right resize grip), since frameless windows have no native frame.
- PIP geometry (`x, y, w, h`) is persisted on move/resize (debounced) and restored
  when PIP is next opened. PIP *visibility* is not persisted: PIP opens closed at
  startup.
- PIP is always-on-top of the main window, including when the main window is
  fullscreen (flagged in risks).

### 3.4 Persistence contract

New keys in the config dict, written by `save_callback` and read back by
`load_config()`:

| Key | Type (in dict) | Serialized in `[SETTINGS]` | Default |
|---|---|---|---|
| `view_mode` | `str` | `normal` \| `compact` \| `video` | `normal` |
| `splitter_state` | `bytes` (from `QSplitter.saveState()`) | base64 ASCII string | (empty) |
| `pip_geometry` | `str` | `x,y,w,h` | (empty) |

**Mandatory companion change:** `load_config()` / `save_config()` in `main.py`
currently enumerate exactly the known keys and **drop everything else** on save.
Without extending them, none of the three keys above would survive a restart — the
persistence requirement would silently fail. The controller exposes pure
serialization helpers (e.g. `geometry_to_str(QRect)`-equivalent pure functions) so
`main.py` only does mechanical read/write.

`main.py`'s `load_config`/`save_config` also need an optional config-path parameter
(or the tests monkeypatch `CONFIG_FILE`) so the round-trip is testable without
touching the real `config.ini`.

### 3.5 Key handling

- Mode / fullscreen / PIP shortcuts are registered as `QAction` shortcuts on the
  window (WindowShortcut context).
- `↑`/`↓` are handled in `keyPressEvent` (or a `QShortcut`) of the main window and
  work in every mode. The current channel index is derived by matching
  `PlaybackManager.current_channel` against `self._last_playlist.channels`
  (identity/URL); if there is no current channel, `↓` starts at index 0 (or the
  first selected row). Behavior at the ends is no-wrap by default (open question,
  §6).
- While a mode ≠ NORMAL, menu-bar actions are explicitly disabled
  (`setEnabled(False)`) — **hiding the menu bar alone does not deactivate QAction
  shortcuts** (`Ctrl+G` would still fire, violating requirement 6).
- PIP key focus: see open question §6 (recommendation: PIP forwards key events to
  the main window so `↑`/`↓`/`P` keep working while PIP has focus).

---

## 4. User stories / acceptance criteria

Strict TDD applies: each AC is written as a failing test first, verified RED, then
made GREEN. Widget tests use pytest-qt (`qtbot`) with fakes for
`PlaylistLoader`, `PlaybackManager`, `EPGManager`, `QtLogoLoaderAdapter` (recording
`play_channel` calls). Pure logic tests target `ViewModeController` directly.

| # | Acceptance criterion (Given / When / Then) |
|---|---|
| AC-1 | **Startup default** — Given a config without `view_mode`, When the window opens, Then it is in NORMAL: table visible with 3 columns, video visible, menu bar visible. |
| AC-2 | **Compact** — Given the window is open, When `ALT+2` is pressed, Then the mode is COMPACT, columns 1–2 are hidden (column 0 visible), the table and video are visible, the menu bar is hidden. |
| AC-3 | **Video** — When `ALT+3` is pressed, Then the mode is VIDEO, the table is hidden, the video is visible, the menu bar is hidden. |
| AC-4 | **Return to Normal** — From any mode, when `ALT+1` is pressed, Then NORMAL is restored: 3 columns, video, menu bar visible. Re-pressing the active mode's shortcut leaves the state unchanged. |
| AC-5 | **Fullscreen + cursor** — When `F` is pressed in any mode, Then the window is fullscreen; after 3 s without mouse input the cursor is blank; on mouse move the arrow cursor returns. |
| AC-6 | **Esc exits fullscreen** — When fullscreen and `Esc` is pressed, Then fullscreen is exited; pressing `Esc` while not fullscreen has no effect. |
| AC-7 | **Mode persistence** — Given mode COMPACT selected and `save_callback` invoked, Then the config dict contains `view_mode == 'compact'`; loading that config and building the window starts in COMPACT. Round-trip through `load_config`/`save_config` (temp file) is asserted. |
| AC-8 | **Splitter persistence** — When the splitter handle is moved and the config is saved, Then `splitter_state` round-trips through `save_state`/`restore_state` with equal sizes. |
| AC-9 | **Zap down/up, all modes** — In each of NORMAL, COMPACT, VIDEO: when `↓` is pressed, Then the next channel (per playlist order) is played via `playback_manager.play_channel`; `↑` plays the previous one. In VIDEO the table is hidden yet zapping still works. |
| AC-10 | **Zap edges** — Given the playlist has N channels, When `↑` on the first channel or `↓` on the last, Then nothing happens (no crash, no wrap; default, see §6). Given an empty playlist, `↑`/`↓` are no-ops. |
| AC-11 | **PIP open** — When `P` (or `ALT+4`) is pressed, Then a frameless, always-on-top PIP window appears containing the video widget; the main window's video placeholder is hidden. |
| AC-12 | **PIP toggle** — When `P` is pressed again, Then the PIP closes and the video widget returns to the main window's splitter. |
| AC-13 | **PIP geometry persistence** — Given the PIP is moved/resized and the config is saved, Then `pip_geometry` round-trips and the next PIP open restores that position/size. |
| AC-14 | **Menu gating** — In COMPACT and VIDEO, `Ctrl+G` (EPG) does **not** trigger the EPG grid and the menu actions report `isEnabled() == False`; after `ALT+1` they are enabled again. |
| AC-15 | **No context menu** — In COMPACT and VIDEO, the table and video have `Qt.ContextMenuPolicy.NoContextMenu`; right-click produces no menu. |
| AC-16 | **Video re-target** — After every mode switch and PIP open/close, `PlaybackManager.initialize_display` is invoked with the current `video_widget.winId()` (recorded by the fake), so the player output stays attached. |

---

## 5. Interaction map

| Key(s) | Mode(s) | Action |
|---|---|---|
| `ALT+1` | any | Switch to **Normal** mode (table 3 cols + video + menu) |
| `ALT+2` | any | Switch to **Compact** mode (channel column + video, no menu) |
| `ALT+3` | any | Switch to **Video** mode (video only, no menu) |
| `ALT+4` | any | Toggle **PIP** window |
| `P` | any | Toggle **PIP** window |
| `F` | any | Toggle **fullscreen** |
| `Esc` | fullscreen only | Exit fullscreen (no-op otherwise) |
| `↑` | any (main window / PIP focus) | Play **previous** channel |
| `↓` | any (main window / PIP focus) | Play **next** channel |
| `Ctrl+G` | Normal only | EPG grid (existing; disabled outside Normal) |
| mouse click on row | Normal | Play channel (existing, unchanged) |
| mouse move | fullscreen | Restore cursor + restart 3 s hide timer |
| drag PIP body / grip | PIP | Move / resize PIP (geometry persisted) |

No conflicts with existing shortcuts (`Ctrl+G` EPG; no other `ALT+*`, `F`, `P`, or
arrow shortcuts exist today).

---

## 6. Open questions / risks

### Open questions (RESOLVED by user)

1. **PIP semantics** — The proposed v1 detaches the *same* video widget into the PIP
   (single player output, re-targeted). The alternative — a true second video stream
   in PIP — requires a second player instance and is explicitly out of scope. Confirm
   the detach model is acceptable (i.e., while PIP is open the main window shows no
   video placeholder).
2. **Zap wrap-around** — `↑` on the first / `↓` on the last channel: stop (default in
   AC-10) or wrap around?
3. **Menu shortcut gating** — Confirm that in Compact/Video even the *shortcuts*
   (`Ctrl+G`) must be dead until returning to Normal (AC-14), not just the visible
   menus.
4. **PIP startup visibility** — Confirm PIP always opens closed at startup (geometry
   only is remembered).
5. **PIP focus** — Confirm that while the PIP window has focus, keys (`↑`/`↓`/`P`)
   should be forwarded to the main window so zapping keeps working.

### Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **Video output on mode switch / reparent** — VLC/mpv embedded via `winId()` may not resize or may blank when widgets are hidden/shown or the widget is reparented into PIP; `winId()` can change across `setParent`. | High | Re-call `playback_manager.initialize_display(int(video_widget.winId()))` after every visibility/layout change (AC-16). Automated tests use a fake player recording calls; final validation requires a **manual smoke test with both real engines (VLC and mpv)** — this is the one acceptance criterion that cannot be fully proven by pytest alone. |
| **Persistence silently lost** — `save_config()` in `main.py` only writes known keys; `view_mode`, `splitter_state`, `pip_geometry` would be dropped on save unless `main.py` is extended. | High | Include `main.py` changes in scope; controller-level pure serialization + temp-file round-trip tests (AC-7/8/13). |
| **Hidden menu bar keeps shortcuts alive** — hiding the menubar does not disable its `QAction` shortcuts. | Medium | Explicitly `setEnabled(False)` on menu actions in non-NORMAL modes (AC-14). |
| **Fullscreen × PIP** — PIP stays always-on-top above a fullscreen main window (may cover content). | Medium | Documented behavior in v1; flagged for user confirmation. |
| **Fullscreen × cursor timer** — Timer armed while leaving fullscreen could leave a blank cursor. | Medium | Cancel/restore cursor on every fullscreen exit path (AC-5/6). |
| **Splitter restore after hiding table** — Hiding the table in VIDEO collapses splitter state; restoring sizes when returning to NORMAL must be explicit. | Medium | Save splitter state before hiding; restore after showing (AC-8). |
| **Headless test limitations** — `offscreen` platform may not fully exercise fullscreen/cursor behavior. | Low | Test cursor logic by invoking the timeout handler and `mouseMoveEvent` directly; keep window-level asserts minimal. |
| **ALT shortcuts vs menu mnemonics** — `ALT+1..4` must not be swallowed by the native menu handling when the menu bar is visible. | Low | Verify with `qtbot.keyClick` on the real widget; fall back to `QShortcut` if needed. |
| **Frameless PIP resizing** — Frameless windows have no native resize frame; need a custom grip. | Low | Implement a bottom-right resize grip with mouse tracking (small, testable surface). |

---

## 7. Rollback

- Purely additive UI change. Reverting = restore `main_window.py`/`main.py` from
  before this change and delete the new controller/PIP/test files.
- Config compatibility: `load_config()` reads new keys with fallbacks, so an old
  `config.ini` opens fine; an old binary ignores unknown keys on read. No migration
  step required. Rolling back the feature leaves harmless keys in `config.ini`
  (ignored on read, overwritten on next save).
- No data model, playlist, or playback-path changes — playback code is untouched
  except for re-target calls.

---

## 8. Success criteria

1. All acceptance criteria AC-1…AC-16 pass under strict TDD (test-first,
   verified RED).
2. Existing test suite remains green (`pytest`).
3. Manual smoke test with **both** real engines: switching modes while playing
   keeps the video attached and correctly sized; PIP opens/drags/resizes/closes
   with the stream following the widget; fullscreen hides the cursor after 3 s and
   restores it on mouse move.
4. Mode, splitter layout, and PIP geometry survive an application restart
   (`config.ini` round-trip verified).
5. In Compact/Video: no menu, no context menu, no EPG shortcut — and `ALT+1`
   restores everything.

---

## Proposal question round — RESOLVED

User decisions (2026-08-24):

1. **PIP model** → DETACH. The current video widget is re-parented into the PIP; the
   main window shows no video while the PIP is open. True dual-stream PIP stays out of scope.
2. **Zap wrap-around** → WRAP-AROUND. `↑` on the first channel wraps to the last; `↓` on
   the last wraps to the first. (Revises AC-10.)
3. **Shortcut gating** → KEEP ACTIVE. `Ctrl+G` (EPG) and any menu shortcuts remain
   functional in Compact/Video; do NOT disable menu QActions. (Revises AC-14.)
4. **PIP startup** → PIP NEVER auto-opens at launch, even if the app exited with the PIP
   open. Only its geometry is persisted.
5. **PIP focus** → Forward keys from the PIP to the main window so `↑`/`↓`/`P` keep
   working while the PIP has focus. Additionally: the PIP is ALWAYS-ON-TOP and no other
   window may cover it.
