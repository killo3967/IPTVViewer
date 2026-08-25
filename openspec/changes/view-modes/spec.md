# View Modes Specification

**Change:** `view-modes`
**Status:** Specified
**Companion:** `openspec/changes/view-modes/proposal.md`
**Backend:** OpenSpec (file-backed)

## Purpose

Give the IPTV viewer three exclusive layout modes — **Normal** (`ALT+1`), **Compact** (`ALT+2`), **Video** (`ALT+3`) — plus an orthogonal fullscreen axis, keyboard channel zapping with wrap-around, and a detached, always-on-top picture-in-picture (PIP) window. Layout mode, splitter geometry, and PIP geometry persist across sessions; fullscreen state and PIP visibility do not. Menu shortcuts (e.g. `Ctrl+G` EPG) remain functional in every mode.

## Revisions from the proposal (resolved question round, 2026-08-24)

| # | Proposal original | Resolved decision | Effect |
|---|---|---|---|
| 1 | PIP v1 detach (Q1) | DETACH confirmed — single player output, re-parented widget | REQ-6 |
| 2 | AC-10: zap at edges = stop | WRAP-AROUND (`↑` on first → last; `↓` on last → first) | REQ-5, revises AC-10 |
| 3 | AC-14 / §2 item 6 / §3.5: menu shortcuts disabled in Compact/Video | KEEP ACTIVE — do NOT disable menu QActions | REQ-9, revises AC-14 |
| 4 | PIP visibility persisted (Q4) | PIP NEVER auto-opens at launch; only geometry is persisted | REQ-6, REQ-8 |
| 5 | PIP focus forwarding (Q5) | Forward keys to main window; PIP always-on-top, no window may cover it | REQ-6 |

## Requirements

### Requirement: Qt-free view-mode state machine

The system MUST provide a pure view-mode controller with **no `PyQt6` imports** (unit-testable with plain pytest) that holds the view-mode state. The state MUST be exactly one of `NORMAL`, `COMPACT`, `VIDEO` at any time. A newly created controller with no persisted mode MUST start in `NORMAL`. The controller MUST expose idempotent activation commands: activating the already-active mode MUST leave the state unchanged and MUST NOT emit a layout-change signal. The controller MUST expose a pure mapping from mode to its serialized string (`normal`, `compact`, `video`) and MUST parse unknown persisted strings by falling back to `NORMAL` without raising.

#### Scenario: Default mode is NORMAL

- GIVEN a new controller with no persisted mode
- WHEN the controller is created
- THEN the active mode is `NORMAL`

#### Scenario: Switching modes

- GIVEN the controller is in `NORMAL`
- WHEN `activate(COMPACT)` is invoked
- THEN the active mode is `COMPACT`

#### Scenario: Re-activating the active mode is a no-op

- GIVEN the controller is in `COMPACT`
- WHEN `activate(COMPACT)` is invoked again
- THEN the state is unchanged and no layout-change notification is produced

#### Scenario: Mode serialization round-trip

- GIVEN the controller is in `VIDEO`
- WHEN the serialized form is requested and then parsed back
- THEN the serialized string is `"video"` and parsing it yields `VIDEO`

#### Scenario: Unknown persisted mode falls back to NORMAL

- GIVEN a persisted value `"cinema"` (not one of the three known strings)
- WHEN the controller parses it
- THEN the mode becomes `NORMAL` without raising

### Requirement: Per-mode layout mapping

The main window MUST apply the following mapping when the mode changes, and MUST apply the `NORMAL` mapping when the window is built with no persisted mode:

| Mode | Table | Columns shown | Video | Menu bar | Context menu |
|---|---|---|---|---|---|
| NORMAL | visible | 0, 1, 2 | visible | visible | default |
| COMPACT | visible | 0 only (1 and 2 hidden) | visible | hidden | `NoContextMenu` |
| VIDEO | hidden | — | visible, fills the area | hidden | `NoContextMenu` |

Hiding the menu bar MUST NOT deactivate its `QAction` shortcuts (see REQ-9).

#### Scenario: Startup default is NORMAL

- GIVEN a config without a `view_mode` value
- WHEN the window opens
- THEN the mode is `NORMAL`: table visible with 3 columns, video visible, menu bar visible

#### Scenario: Compact layout

- GIVEN the window is open
- WHEN `ALT+2` is pressed
- THEN the mode is `COMPACT`, columns 1 and 2 of the table are hidden, column 0 remains visible, the table and video are visible, and the menu bar is hidden

#### Scenario: Video layout

- GIVEN the window is open
- WHEN `ALT+3` is pressed
- THEN the mode is `VIDEO`, the table is hidden, the video is visible and fills the window area, and the menu bar is hidden

#### Scenario: Return to Normal

- GIVEN the window is in `VIDEO` (table hidden, menu bar hidden)
- WHEN `ALT+1` is pressed
- THEN the `NORMAL` layout is restored: 3 table columns, video, and menu bar visible

### Requirement: Mode shortcut registration

The system MUST register `ALT+1`, `ALT+2`, `ALT+3` as window-level shortcuts (WindowShortcut context) that switch to `NORMAL`, `COMPACT`, `VIDEO` respectively from any mode, fullscreen state, or PIP focus (via REQ-6 key forwarding). Re-pressing the active mode's shortcut MUST be a no-op. When the menu bar is visible, the `ALT+1..4` shortcuts MUST still fire (they MUST NOT be swallowed by native menu mnemonics).

#### Scenario: Mode switch via shortcut

- GIVEN the window is in `NORMAL` with the menu bar visible
- WHEN `ALT+2` is pressed via `qtbot.keyClick`
- THEN the mode becomes `COMPACT`

#### Scenario: Idempotent re-selection

- GIVEN the window is in `VIDEO`
- WHEN `ALT+3` is pressed
- THEN the mode stays `VIDEO` and the layout is not re-applied (no mode-change notification)

### Requirement: Fullscreen axis

`F` MUST toggle fullscreen from any mode; `Esc` MUST exit fullscreen and MUST be a no-op when not fullscreen. While fullscreen, after 3 seconds without mouse movement the cursor MUST be hidden (`BlankCursor`); any mouse movement MUST restore the arrow cursor and restart the 3-second timer. Exiting fullscreen MUST restore the pre-fullscreen windowed state and MUST cancel the hide timer and restore a visible cursor (no blank-cursor leak after exit). Fullscreen state MUST NOT be persisted.

#### Scenario: Toggle fullscreen on and off

- GIVEN the window is windowed in `COMPACT`
- WHEN `F` is pressed
- THEN the window is fullscreen
- WHEN `F` is pressed again
- THEN the window returns to its pre-fullscreen windowed state

#### Scenario: Esc exits fullscreen only when fullscreen

- GIVEN the window is fullscreen
- WHEN `Esc` is pressed
- THEN fullscreen is exited
- GIVEN the window is not fullscreen
- WHEN `Esc` is pressed
- THEN nothing changes

#### Scenario: Cursor hides after inactivity and returns on move

- GIVEN the window is fullscreen
- WHEN the timeout handler is invoked (simulating 3 s without mouse input; tests invoke the handler directly, headless-safe)
- THEN the cursor is hidden
- WHEN a mouse-move event is delivered
- THEN the arrow cursor is restored and the 3-second timer restarts

#### Scenario: No blank cursor after exiting fullscreen

- GIVEN the window is fullscreen and the hide timer is armed
- WHEN the window exits fullscreen (via `F` or `Esc`)
- THEN the timer is canceled and the cursor is visible

### Requirement: Channel zapping with wrap-around

`↑` and `↓` MUST switch to the previous/next channel and start playback in **every** mode, including `VIDEO` with the table hidden and when the PIP window has focus (via REQ-6 key forwarding). The current channel index MUST be derived by matching `PlaybackManager.current_channel` against the playlist order (by channel identity/URL). The index-resolution logic (given playlist, current channel, direction → target index) MUST be a pure, Qt-free function so edge and wrap cases are unit-testable with plain pytest. When the playlist is empty, `↑`/`↓` MUST be no-ops. When there is no current channel and the playlist is non-empty, both `↑` and `↓` MUST select the first channel (index 0 or the first selected row). At the edges the selection MUST wrap around: `↑` on the first channel selects the last; `↓` on the last selects the first. After resolving the target, the system MUST call `playback_manager.play_channel(target)`.

#### Scenario: Zap down plays the next channel

- GIVEN the playlist is `[c1, c2, c3]` and the current channel is `c1`
- WHEN `↓` is pressed
- THEN `play_channel(c2)` is recorded by the fake `PlaybackManager`

#### Scenario: Zap up works in Video mode with the table hidden

- GIVEN the mode is `VIDEO` (table hidden) and the current channel is `c2`
- WHEN `↑` is pressed
- THEN `play_channel(c1)` is recorded

#### Scenario: Wrap-around at the last channel

- GIVEN the playlist is `[c1, c2, c3]` and the current channel is `c3`
- WHEN `↓` is pressed
- THEN `play_channel(c1)` is recorded (wraps to first)

#### Scenario: Wrap-around at the first channel

- GIVEN the playlist is `[c1, c2, c3]` and the current channel is `c1`
- WHEN `↑` is pressed
- THEN `play_channel(c3)` is recorded (wraps to last)

#### Scenario: Empty playlist is a no-op

- GIVEN the playlist is empty
- WHEN `↑` or `↓` is pressed
- THEN no `play_channel` call is recorded and no crash occurs

#### Scenario: No current channel starts at the first channel

- GIVEN a non-empty playlist and no current channel
- WHEN `↓` is pressed
- THEN `play_channel(first_channel)` is recorded

### Requirement: PIP detach window

`P` or `ALT+4` MUST toggle `pip_open` from anywhere (any mode, any fullscreen state). Opening PIP MUST reparent the **existing** video widget into a new frameless, always-on-top PIP window flagged with `Qt.WindowType.Tool | FramelessWindowHint | WindowStaysOnTopHint` (DETACH model — a single player output; a second player instance is out of scope). While PIP is open, the main window's video placeholder MUST be hidden (in `NORMAL`/`COMPACT` the splitter then shows the table only; in `VIDEO` the main area is empty). Closing PIP MUST move the widget back into the main window's splitter and restore placeholder visibility per the current mode. After every reparent the player output MUST be re-targeted via `playback_manager.initialize_display(int(video_widget.winId()))` (see REQ-7). The PIP MUST be draggable by mouse press/move on the window body and resizable via a bottom-right resize grip. PIP geometry (`x, y, w, h`) MUST be persisted on move/resize (debounce MAY be used) and restored when PIP is next opened; when no geometry was persisted, the PIP MUST open with an implementation-chosen default geometry. The PIP MUST NEVER auto-open at launch, even if the application was closed with the PIP open. While the PIP is open, it MUST remain on top of all application windows — including a fullscreen main window and any dialogs — and no window MUST be placed above it. While the PIP window has focus, it MUST forward key events to the main window so window-level shortcuts (`↑`, `↓`, `P`/`ALT+4`, `ALT+1..3`, `F`, `Esc`, `Ctrl+G`) continue to work.

#### Scenario: PIP opens detached and hides the main placeholder

- GIVEN the window is in `NORMAL` with playback active
- WHEN `P` is pressed
- THEN a frameless window with `WindowStaysOnTopHint` appears containing the video widget, and the main window's video placeholder is hidden

#### Scenario: PIP toggles closed and the widget returns

- GIVEN the PIP is open
- WHEN `P` is pressed again
- THEN the PIP closes and the video widget returns to the main window's splitter with placeholder visibility restored per the current mode

#### Scenario: ALT+4 toggles the same PIP

- GIVEN the PIP is closed
- WHEN `ALT+4` is pressed
- THEN the PIP opens (same behavior as `P`)
- WHEN `ALT+4` is pressed again
- THEN the PIP closes

#### Scenario: PIP never auto-opens at launch

- GIVEN the persisted config contains a `pip_geometry` and the previous session ended with the PIP open
- WHEN the application launches
- THEN no PIP window exists and the video widget is in the main window

#### Scenario: Player output re-targeted after reparent

- GIVEN a fake `PlaybackManager` recording calls
- WHEN the PIP is opened and then closed
- THEN `initialize_display` is recorded with the video widget's current `winId()` after each reparent

#### Scenario: PIP drag and resize persist geometry

- GIVEN the PIP is open
- WHEN the user drags the PIP body to a new position
- THEN the PIP moves and the new geometry is recorded for persistence
- WHEN the user drags the bottom-right resize grip
- THEN the PIP resizes and the new geometry is recorded for persistence

#### Scenario: PIP stays on top of other windows

- GIVEN the PIP is open
- WHEN the main window is raised to fullscreen or an application dialog (e.g. EPG grid) is opened
- THEN the PIP remains visible and is not covered (its window flags include `WindowStaysOnTopHint`; no window is raised above it)

#### Scenario: PIP forwards keys to the main window

- GIVEN the PIP window has focus
- WHEN `↓` is pressed on the PIP window
- THEN the main window's zap logic runs and `play_channel(next_channel)` is recorded

### Requirement: Video re-target after every visibility change

After every mode switch and every PIP open/close, the system MUST invoke `playback_manager.initialize_display(int(video_widget.winId()))` with the **current** window id (a `winId()` can change across `setParent`/hide-show, so the id MUST be re-read at call time, not cached).

#### Scenario: Re-target after mode switch

- GIVEN playback is active in `NORMAL` and the fake records calls
- WHEN `ALT+2` is pressed
- THEN `initialize_display` is recorded once with the current `winId()`

#### Scenario: Re-target on PIP open and close

- GIVEN the fake records calls
- WHEN the PIP is opened and then closed
- THEN exactly two `initialize_display` calls are recorded, each with the `winId()` valid at that moment

### Requirement: Persistence of mode, splitter, and PIP geometry

The config dict MUST carry three new keys, serialized in `[SETTINGS]`:

| Key | Type in dict | Serialized in `[SETTINGS]` | Default |
|---|---|---|---|
| `view_mode` | `str` | `normal` \| `compact` \| `video` | `normal` |
| `splitter_state` | `bytes` (from `QSplitter.saveState()`) | base64 ASCII string | (empty) |
| `pip_geometry` | `str` | `x,y,w,h` | (empty) |

`main.py`'s `load_config()` / `save_config()` MUST be extended to read and write these keys — the current implementation enumerates known keys and drops everything else on save, which would silently break persistence; this companion change is mandatory. The controller MUST expose pure serialization helpers (mode ↔ string; geometry string ↔ `(x, y, w, h)` tuple with validation) so `main.py` only performs mechanical read/write. `load_config`/`save_config` MUST accept a config-path parameter (or be monkeypatchable via `CONFIG_FILE`) so round-trip tests never touch the real `config.ini`. A window built from a saved `view_mode` MUST start in that mode. Splitter sizes MUST be saved before the table is hidden (`VIDEO`) and restored when returning to `NORMAL`. Missing keys MUST fall back to their defaults and an old `config.ini` MUST open unchanged.

#### Scenario: Mode round-trip

- GIVEN the mode is `COMPACT` and `save_callback` is invoked
- THEN the config dict contains `view_mode == 'compact'`
- WHEN the config is saved to a temp file and loaded back
- THEN a window built from it starts in `COMPACT`

#### Scenario: Splitter round-trip

- GIVEN the splitter handle is moved to known sizes and the config is saved
- THEN `splitter_state` round-trips through `saveState`/`restoreState` with equal sizes when reloaded

#### Scenario: PIP geometry round-trip

- GIVEN the PIP was dragged to `(x, y, w, h)` and the config was saved
- THEN the config contains `pip_geometry == "x,y,w,h"`
- WHEN the app restarts and the PIP is opened
- THEN the PIP opens at that position and size

#### Scenario: Defaults and legacy config compatibility

- GIVEN a config file with none of the three new keys
- WHEN the app loads it and builds the window
- THEN the mode is `NORMAL`, no splitter restore occurs, no PIP opens, and no error is raised

### Requirement: Menu shortcuts remain active in Compact and Video

In `COMPACT` and `VIDEO` the menu bar is hidden but ALL menu `QAction` shortcuts MUST remain functional: pressing `Ctrl+G` MUST open the EPG grid, and every menu action MUST report `isEnabled() == True`. The application MUST NOT disable menu actions when entering `COMPACT` or `VIDEO`, and MUST NOT re-enable anything special on return to `NORMAL` (they are never disabled). This REVISES proposal §2 scope item 6, §3.5, and AC-14 (the original "deactivated" behavior is removed).

#### Scenario: Ctrl+G works in Compact

- GIVEN the mode is `COMPACT` (menu bar hidden)
- WHEN `Ctrl+G` is pressed
- THEN the EPG grid dialog opens and the menu actions report `isEnabled() == True`

#### Scenario: Ctrl+G works in Video

- GIVEN the mode is `VIDEO` (menu bar hidden, table hidden)
- WHEN `Ctrl+G` is pressed
- THEN the EPG grid dialog opens

#### Scenario: Shortcuts stay enabled across mode round-trip

- GIVEN the window is in `VIDEO`
- WHEN the mode returns to `NORMAL` via `ALT+1`
- THEN the menu bar is visible again and `Ctrl+G` continues to open the EPG grid

### Requirement: No context menu in Compact and Video

In `COMPACT` and `VIDEO`, the table and video MUST use `Qt.ContextMenuPolicy.NoContextMenu`; right-click MUST produce no menu. In `NORMAL` the existing default context-menu behavior MUST be preserved unchanged.

#### Scenario: Right-click produces no menu in Compact

- GIVEN the mode is `COMPACT`
- WHEN the table (or video) is right-clicked
- THEN no context menu appears

#### Scenario: Normal mode keeps existing context behavior

- GIVEN the mode is `NORMAL`
- WHEN the table is right-clicked
- THEN the existing default context behavior is preserved

### Requirement: Real-engine smoke verification

The one acceptance surface that automated tests cannot fully prove MUST be covered by a manual smoke test on BOTH real engines (VLC and mpv): switching modes while playing keeps the video attached and correctly sized; PIP open/drag/resize/close keeps the stream following the widget; fullscreen hides the cursor after 3 s and restores it on mouse move.

#### Scenario: Manual smoke test with both engines

- GIVEN a real VLC engine and a real mpv engine
- WHEN a channel is playing and modes are switched, PIP is opened/dragged/resized/closed, and fullscreen is toggled with cursor inactivity
- THEN the video stays attached and correctly sized at every step and the cursor behaves per REQ-4 (recorded as manual evidence in the archive report)

## Acceptance criteria (revised)

| AC | Behavior | Requirement | Status |
|---|---|---|---|
| AC-1 | Startup default NORMAL (3 columns, video, menu bar) | REQ-2 | Confirmed |
| AC-2 | Compact: columns 1–2 hidden, table+video visible, menu hidden | REQ-2 | Confirmed |
| AC-3 | Video: table hidden, video visible, menu hidden | REQ-2 | Confirmed |
| AC-4 | Return to Normal; re-selecting active mode is no-op | REQ-2, REQ-3 | Confirmed |
| AC-5 | Fullscreen + cursor auto-hide after 3 s, restore on move | REQ-4 | Confirmed |
| AC-6 | Esc exits fullscreen only when fullscreen | REQ-4 | Confirmed |
| AC-7 | Mode persistence round-trip | REQ-8 | Confirmed |
| AC-8 | Splitter persistence round-trip | REQ-8 | Confirmed |
| AC-9 | Zap down/up in all modes, incl. Video | REQ-5 | Confirmed |
| AC-10 | **REVISED: zap edges WRAP-AROUND** (`↑` first → last, `↓` last → first); empty playlist no-op | REQ-5 | **Revised** |
| AC-11 | PIP open: frameless always-on-top, main placeholder hidden | REQ-6 | Confirmed |
| AC-12 | PIP toggle: widget returns to splitter | REQ-6 | Confirmed |
| AC-13 | PIP geometry persistence and restore | REQ-8 | Confirmed |
| AC-14 | **REVISED: menu shortcuts stay ACTIVE** in Compact/Video (`Ctrl+G` works, `isEnabled() == True`, QActions NOT disabled) | REQ-9 | **Revised** |
| AC-15 | No context menu in Compact/Video | REQ-10 | Confirmed |
| AC-16 | Video re-target after every mode switch and PIP open/close | REQ-7 | Confirmed |

## Testing strategy (strict TDD)

- **Plain pytest (no Qt):** `ViewModeController` state machine and serialization (REQ-1); zap index resolution incl. wrap-around, empty playlist, no-current-channel (REQ-5 pure function); geometry string helpers (REQ-8); `load_config`/`save_config` round-trips on a temp file (REQ-8).
- **pytest-qt (`qtbot`):** layout mapping per mode (REQ-2), mode shortcuts incl. `ALT+1..4` not swallowed by mnemonics (REQ-3), fullscreen toggle/Esc and cursor handler invocation (REQ-4), key-driven zapping with fakes for `PlaylistLoader`/`PlaybackManager`/`EPGManager`/`QtLogoLoaderAdapter` recording `play_channel`/`initialize_display` (REQ-5/REQ-7), PIP open/close/reparent/drag/resize/flags/key forwarding (REQ-6), `Ctrl+G` in Compact/Video and `isEnabled()` assertions (REQ-9), context-menu policy (REQ-10).
- Every requirement scenario above is written as a failing test first (RED), then made GREEN; existing suite must remain green.

## Non-goals (explicitly out of scope)

- A second, independent player instance for PIP (true dual-stream) — out of scope; PIP re-parents the same `video_widget`.
- Persisting main-window position/size (existing behavior unchanged).
- Persisting fullscreen state or PIP visibility (both session-only).
- Channel search/filter/favorite UI, OSD overlays, channel-name popups, EPG overlay on video.
- Mouse-based channel switching in Normal (existing click-to-play preserved).
- Configurable/custom shortcuts (hardcoded v1).
- Per-mode layouts beyond the table/video split; no toolbar/status-bar additions.

## Assumptions (spec-level decisions beyond the proposal text)

1. **`↑` with no current channel:** both `↑` and `↓` select the first channel (index 0 / first selected row) when no channel is current and the playlist is non-empty (proposal only specified `↓`; `↑` is symmetric to avoid a surprising wrap-to-last on first zap).
2. **PIP default geometry:** when no `pip_geometry` is persisted, the implementation chooses a sane default position/size; the exact value is not specified.
3. **Key forwarding scope:** the PIP forwards all key events to the main window (not only `↑`/`↓`/`P`), so every window-level shortcut keeps working under PIP focus.
