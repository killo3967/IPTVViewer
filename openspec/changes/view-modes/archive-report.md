# Archive Report — view-modes

**Change:** `view-modes`
**Backend:** OpenSpec (file-backed)
**Archive date:** 2026-08-24
**Final status:** **COMPLETE** (one manual follow-up item remains — REQ-11)

---

## Executive summary

The `view-modes` change is **complete**. It delivers three exclusive layout modes
(NORMAL / COMPACT / VIDEO), an orthogonal fullscreen axis with cursor auto-hide,
keyboard channel zapping with wrap-around, and a detached always-on-top PIP window,
with mode / splitter / PIP-geometry persistence across sessions.

Implementation shipped across 5 commits and was verified by a fully green automated
suite. The three CRITICAL blockers found by `sdd-verify` were all resolved by the
remediation commit `dd22668`. The only open item is the **manual** real-engine smoke
test (REQ-11, VLC + mpv), which is recorded as a follow-up — it is **not** a delivery
failure.

## Final-state facts

| Fact | Value |
|---|---|
| Commits | `134f8f1` (PR1 controller) → `61aaeef` (PR2 persistence) → `3543ee8` (PR3 main-window core) → `135766e` (PR4 PIP) → `dd22668` (remediation) |
| Final test result | `QT_QPA_PLATFORM=offscreen pytest tests/ -q` → **140 passed** (was 130; +10 remediation tests) |
| Targeted new-test run | `tests/test_view_mode_controller.py` + `test_config_roundtrip.py` + `test_main_window.py` → **84 passed** (was 74) |
| REQ-9 constraint | `grep "setEnabled(False)" main_window.py` → no match (menu shortcuts never disabled) |
| CRITICAL blockers | All 3 resolved by `dd22668` (see below) |
| Open item | REQ-11 manual smoke test (VLC + mpv) — **PENDING, manual follow-up** |

### Environment note (pre-existing, not introduced by this change)

On this machine the full suite exits with Windows code 139 (access violation during Qt
teardown at process exit) after Qt window tests run. Proven on a pristine HEAD
worktree (`135766e`): `tests/test_main_window.py` prints `41 passed` and exits 139
identically. Root cause: PyQt6 6.11 + pytest-qt 4.5 + offscreen teardown accumulation,
independent of this change. **The pytest summary (140 passed, 0 failed) is the gate
signal**, consistent with how the prior verify phase reported `130 passed`.

## Resolution of the 3 CRITICAL verify blockers

| # | Verify blocker | Resolution (commit `dd22668`) |
|---|---|---|
| 1 | AC-13 / REQ-8 / REQ-6 — `pip_geometry` never persisted on move/resize | `PIPWindow.geometry_changed` signal emitted from `moveEvent` + `resizeEvent`; main window connects it once at lazy PIP creation to `_arm_pip_geometry_save` (300 ms debounce) → `_flush_pip_geometry` writes `config['pip_geometry']` + `save_callback`; `_close_pip()` cancels the timer and `_flush_pip_geometry` guards on `_pip_open`. Restore-on-open + garbage→default already existed. |
| 2 | `tasks.md` unchecked implementation markers (WU 4.1–4.5) | 15 implementation checkboxes (RED/GREEN/REFACTOR for WU 4.1–4.5) marked `- [x]`. WU 5.1 (manual smoke) and the two parent-owned gates intentionally left unchecked (recorded as follow-ups). |
| 3 | No OpenSpec `apply-progress.md` and no `TDD Cycle Evidence` table | `openspec/changes/view-modes/apply-progress.md` created with the full TDD Cycle Evidence table (WU 1.1 → WU 5.1), merging the prior Engram observation (id 2565) without overwrite. |

## Acceptance criteria — final results

| AC | Behavior | Result |
|---|---|---|
| AC-1 | Startup default NORMAL | PASS |
| AC-2 | Compact layout (cols 1–2 hidden, menu hidden) | PASS |
| AC-3 | Video layout (table hidden, menu hidden) | PASS |
| AC-4 | Return to Normal; re-select active mode is no-op | PASS |
| AC-5 | Fullscreen + cursor auto-hide after 3 s | PASS |
| AC-6 | Esc exits fullscreen only when fullscreen | PASS |
| AC-7 | Mode persistence round-trip | PASS |
| AC-8 | Splitter persistence round-trip | PASS |
| AC-9 | Zap down/up in all modes | PASS |
| AC-10 | Zap edges wrap-around; empty playlist no-op | PASS |
| AC-11 | PIP open: frameless always-on-top, placeholder hidden | PASS |
| AC-12 | PIP toggle: widget returns to splitter | PASS |
| AC-13 | **PIP geometry persistence and restore** | **PASS (remediated by `dd22668`)** |
| AC-14 | Menu shortcuts stay ACTIVE in Compact/Video | PASS |
| AC-15 | No context menu in Compact/Video | PASS |
| AC-16 | Video re-target after mode switch and PIP open/close | PASS (both halves now tested) |

## Requirements — final results

| REQ | Result |
|---|---|
| REQ-1 Qt-free view-mode state machine | PASS — no `PyQt6` import in `view_mode_controller.py` |
| REQ-2 Per-mode layout mapping | PASS |
| REQ-3 Mode shortcut registration | PASS |
| REQ-4 Fullscreen axis | PASS |
| REQ-5 Channel zapping with wrap-around | PASS |
| REQ-6 PIP detach window | PASS (geometry persistence remediated) |
| REQ-7 Video re-target after visibility change | PASS — `winId()` re-read at call time; both mode-switch and PIP open/close tested |
| REQ-8 Persistence of mode/splitter/PIP geometry | PASS |
| REQ-9 Menu shortcuts remain active | PASS |
| REQ-10 No context menu in Compact/Video | PASS |
| REQ-11 Real-engine smoke (VLC + mpv) | **PENDING — manual follow-up** |

## Follow-up manual task (the only open item)

**REQ-11 — real-engine smoke test with VLC and mpv.** Run the app with a real channel
playing on VLC, then on mpv; switch NORMAL→COMPACT→VIDEO→NORMAL; open/drag/resize/close
PIP; toggle fullscreen and wait 3 s for the cursor to hide, move the mouse to restore it;
verify `Alt+1..4` pass through the native Windows menu bar. Record pass/fail notes and
append them to this archive report when done.

This is the one acceptance surface pytest cannot prove (embedded `winId()` resizing/
reparenting against real engines). It was scoped from the start as a **manual** item
(proposal risk table, design §6, spec REQ-11, WU 5.1). Its absence does **not** fail the
automated archive.

## Remaining unchecked `tasks.md` lines (intentional)

- WU 5.1 manual smoke (VLC + mpv) → covered by the follow-up above.
- WU 5.1 "run the complete automated suite once more" → satisfied: `pytest tests/ -q` = 140 passed.
- Parent gate "Review the full change against the spec AC table" → satisfied by this archive (all AC-1..AC-16 PASS; REQ-11 recorded as manual follow-up).
- Parent gate "run `sdd-verify` then `sdd-archive`" → satisfied by this archive phase.

## Deviations from design (carried from apply-progress)

1. WU 4.3 tests drive `pip.move()`/`pip.resize()` instead of `QTest.mouseDrag`/`mouseMove` (synthesized drags crash natively offscreen once prior Qt windows accumulate); the move/resize event wiring is the same path a real drag/grip uses, and the mouse mechanics are already covered by `test_pip_body_drag_moves_window` / `test_pip_grip_drag_resizes_with_minimum`.
2. Off-screen clamp heuristic (design §8) not implemented — a v1 heuristic with no AC coverage; out of the delegated remediation scope.
3. Design D8's main-window `keyPressEvent` → `_dispatch_key_event` was **not** added: the PIP is QWidget-parented to the main window, so the main window's `WindowShortcut` shortcuts already fire under PIP focus (proven by the 4 new WU 4.5 tests passing against existing code). A second dispatch path would be speculative code with no failing test and a double-dispatch risk. `PIPWindow.keyPressEvent` forwarding (WU 4.1) remains for non-shortcut keys.
4. Debounce flush in tests uses `_pump_events()` (processEvents + sleep) instead of `qtbot.wait(350)` (nested QEventLoop crashes natively here); identical observable behavior.

## Risks carried forward (post-archive, non-blocking)

- **Real-engine re-target** (REQ-11) still unverified manually — the one residual risk, mitigated by the follow-up task.
- **Windows native menu swallowing of `Alt+1..4`** — expected to pass (no mnemonic is `1..4`); contingency (`ApplicationShortcut` context) documented in design D8, only if the real-Windows smoke test shows swallowing.
- **PIP `Tool` window may hide when the app loses focus** on some platforms — documented v1 limitation.
- **Fullscreen × PIP overlap** — PIP stays on top and may cover fullscreen content (accepted v1 behavior).
- Pre-existing unrelated working-tree changes (docs/, `mpv_player_adapter.py`, `player_factory.py`, proxy files) — outside this change's scope; do not gate archive.

## Rollback

Purely additive UI change. Rollback = restore `main_window.py`/`main.py` from before this
change and delete `view_mode_controller.py`, `pip_window.py`, and the three new test files.
Legacy `config.ini` compatibility: new keys are read with fallbacks; an old binary ignores
them. No data-model, playlist, or playback-path changes (playback code untouched except
re-target calls).

## Success criteria — final

1. AC-1…AC-16 pass under strict TDD — **YES** (140 automated tests green).
2. Existing suite green — **YES**.
3. Manual smoke with both engines — **PENDING** (follow-up; the only open criterion).
4. Mode/splitter/PIP geometry survive restart — **YES** (round-trip tested).
5. Compact/Video: no menu, no context menu, EPG shortcut active, `ALT+1` restores — **YES**.
