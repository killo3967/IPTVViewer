# Apply Progress — view-modes (remediation)

**Change:** `view-modes` · **Backend:** OpenSpec · **Strict TDD:** enabled (pytest + pytest-qt)
**Phase:** sdd-apply (remediation batch) · **Date:** 2026-08-24

## Structured status consumed / produced

- **Consumed:** `verify-report.md` verdict **FAIL** (blockers: AC-13 PIP geometry never persisted; unchecked WU 4.1–4.5 + WU 5.1 task markers; missing OpenSpec `apply-progress.md` with `TDD Cycle Evidence` table). Also consumed `spec.md`, `design.md`, `tasks.md`, and the previous Engram apply-progress observation (id 2565) — merged here, not overwritten.
- **Produced:** this file; `tasks.md` checkboxes reconciled; remediation commit.
- **Action context:** no workspace-planning mode, no edit-root restrictions; all edits inside `K:/IPTVViewer`.

## Completed in this batch (remediation)

| Task | Evidence |
|---|---|
| AC-13 / WU 4.3 — PIP geometry persistence | `PIPWindow.geometry_changed` signal emitted from `moveEvent` + `resizeEvent`; main window connects it once at lazy PIP creation to `_arm_pip_geometry_save` (300 ms debounce) → `_flush_pip_geometry` writes `config['pip_geometry']` and calls `save_callback`; `_close_pip()` cancels the timer (and `_flush_pip_geometry` guards on `_pip_open`). Restore-on-open (`_apply_pip_geometry`) + garbage → default already existed. |
| WU 4.3 tests | persist on move (debounced), persist on resize (debounced), restore persisted geometry on open, garbage → default, close cancels debounce — all in `tests/test_main_window.py`. |
| WU 4.4 test | `test_pip_open_close_retargets_video_exactly_twice` — exactly two `initialize_display` calls across PIP open+close, ids equal `winId()` at call time. |
| WU 4.5 tests | `keyClick(pip_window, …)` for `↓` → `play_channel`, `P` → close, `Alt+2` → COMPACT, `Ctrl+G` → EPG grid (recorder stub). |
| tasks.md reconciliation | WU 4.1/4.2/4.3/4.4/4.5 (RED/GREEN/REFACTOR, 15 lines) marked `- [x]`; WU 5.1 (manual smoke) and parent-owned gates left `- [ ]`. |

## Files changed (this remediation)

| File | Change |
|---|---|
| `src/infrastructure/ui/components/pip_window.py` | `geometry_changed = pyqtSignal()`; `moveEvent` emits it; `resizeEvent` emits it (grip anchoring kept) |
| `src/infrastructure/ui/main_window.py` | `_pip_geometry_save_timer` state; connect `geometry_changed` → `_arm_pip_geometry_save` in `_open_pip`; `_arm_pip_geometry_save` / `_flush_pip_geometry`; cancel timer in `_close_pip` |
| `tests/test_main_window.py` | +10 tests (WU 4.3 ×5, WU 4.4 ×1, WU 4.5 ×4); `_pump_events` helper; `import time` |
| `openspec/changes/view-modes/tasks.md` | 15 implementation checkboxes WU 4.1–4.5 → `- [x]` (WU 5.1 + parent gates untouched) |
| `openspec/changes/view-modes/apply-progress.md` | **NEW** — this file |

Unrelated pre-existing working-tree changes (docs/, mpv_player_adapter.py, proxy_config_dialog.py, proxy.py, player_factory.py, test_mpv_proxy_decision.py, test_player_factory.py, test_tor_*.py, requirements.txt, IPTVViewer.spec) were **not touched**.

## Test commands run

| Command | Result |
|---|---|
| `QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q` | **140 passed** (was 130; +10 new) — no mid-run abort |
| `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_view_mode_controller.py tests/test_config_roundtrip.py tests/test_main_window.py -q` | **84 passed** (was 74) |
| RED run (new persistence tests only) | FAIL as expected: `AssertionError: assert '' == '324,35,480,270'` — no persistence path existed |
| `grep -rn "setEnabled(False)" src/infrastructure/ui/main_window.py` | no match (REQ-9 constraint still respected) |

## TDD Cycle Evidence

| Work unit | RED evidence | GREEN evidence | Test file | Status |
|---|---|---|---|---|
| WU 1.1 `ViewMode` enum/parse | Tests written; FAIL (module missing) — original apply, commit `134f8f1` | `ViewMode` + `parse()` implemented; tests PASS | `tests/test_view_mode_controller.py` | DONE |
| WU 1.2 controller state machine | Tests written; FAIL (class missing) — original apply, `134f8f1` | `ViewModeController` implemented; tests PASS | `tests/test_view_mode_controller.py` | DONE |
| WU 1.3 `resolve_zap_index` | Tests written; FAIL (function missing) — original apply, `134f8f1` | Pure function implemented; tests PASS | `tests/test_view_mode_controller.py` | DONE |
| WU 1.4 geometry/splitter helpers | Tests written; FAIL (helpers missing) — original apply, `134f8f1` | Helpers implemented; tests PASS | `tests/test_view_mode_controller.py` | DONE |
| WU 2.1 config round-trip | Tests written; FAIL (no `config_path`, keys dropped) — original apply, `61aaeef` | `load_config`/`save_config` extended; tests PASS | `tests/test_config_roundtrip.py` | DONE |
| WU 3.1 pytest-qt scaffolding/fakes | Smoke test written; infra created — original apply, `3543ee8` | Fakes + helper; smoke PASS | `tests/test_main_window.py` | DONE |
| WU 3.2 `_apply_layout` mapping | Widget tests written; FAIL (method missing) — original apply, `3543ee8` | `_apply_layout` implemented; tests PASS | `tests/test_main_window.py` | DONE |
| WU 3.3 mode shortcuts | Shortcut tests written; FAIL — original apply, `3543ee8` | `QShortcut` Alt+1..4; tests PASS | `tests/test_main_window.py` | DONE |
| WU 3.4 re-target on mode switch | Test written; FAIL (no re-target) — original apply, `3543ee8` | `_retarget_video()` in mode listener; tests PASS | `tests/test_main_window.py` | DONE |
| WU 3.5 zapping | Zap tests written; FAIL — original apply, `3543ee8` | Up/Down shortcuts + `_zap`; tests PASS | `tests/test_main_window.py` | DONE |
| WU 3.6 fullscreen axis | Fullscreen tests written; FAIL — original apply, `3543ee8` | D5 enter/exit/timer/filter; tests PASS | `tests/test_main_window.py` | DONE |
| WU 3.7 splitter persistence | Splitter tests written; FAIL — original apply, `3543ee8` | Debounced save + pre-hide snapshot + restore; tests PASS | `tests/test_main_window.py` | DONE |
| WU 3.8 menu liveness | Ctrl+G/isEnabled tests written; FAIL — original apply, `3543ee8` | No-op production change (never disabled); tests PASS | `tests/test_main_window.py` | DONE |
| WU 4.1 `PIPWindow`/`ResizeGrip` | Component tests written; FAIL (module missing) — original apply, `135766e` | Component implemented (flags, drag, grip, key forward); tests PASS | `tests/test_main_window.py` | DONE |
| WU 4.2 PIP toggle/reparent | Toggle tests written; FAIL — original apply, `135766e` | `_toggle_pip`/`_open_pip`/`_close_pip`; tests PASS | `tests/test_main_window.py` | DONE |
| WU 4.3 geometry persistence | `test_pip_move_persists…` / `test_pip_resize_persists…` FAILED this session: `AssertionError: assert '' == '324,35,480,270'` (no write path). Restore/garbage tests passed immediately (existing `_apply_pip_geometry`). | `geometry_changed` signal + debounced `_arm_pip_geometry_save`/`_flush_pip_geometry` + cancel on close; 5 tests PASS (`move`, `resize`, `restore`, `garbage→default`, `close cancels`) | `tests/test_main_window.py` | DONE |
| WU 4.4 re-target on PIP open/close | Test written this session; **passed immediately** — validates the pre-existing `_retarget_video()` calls in `_open_pip`/`_close_pip` (coverage remediation; no production change needed) | n/a (no prod change; exactly two `initialize_display` asserted) | `tests/test_main_window.py` | DONE |
| WU 4.5 PIP key forwarding | 4 tests written this session; **passed immediately** — the PIP is QWidget-parented to the main window, so the main window's `WindowShortcut` shortcuts already fire under PIP focus (REQ-6 scenario proven); no `keyPressEvent`/`_dispatch_key_event` added (see deviation D8) | n/a (no prod change; `↓`/`P`/`Alt+2`/`Ctrl+G` under PIP focus asserted) | `tests/test_main_window.py` | DONE |
| WU 5.1 manual smoke (REQ-11) | — | — | manual (VLC + mpv) | PENDING (not automated) |

## Deviations from design

1. **WU 4.3 tests drive `pip.move()` / `pip.resize()` instead of `QTest.mouseDrag`/`mouseMove`.** Synthesized mouse-drag events on the offscreen pip window cause a native access violation mid-run once prior Qt windows accumulate. `move()`/`resize()` fire the exact `moveEvent`/`resizeEvent` → signal wiring that a body drag / grip resize uses; the mouse mechanics themselves are already covered by the pre-existing component tests `test_pip_body_drag_moves_window` and `test_pip_grip_drag_resizes_with_minimum`.
2. **WU 4.3 off-screen clamp heuristic (design §8) not implemented.** The design labels it a v1 heuristic not covered by any AC; the delegated remediation scope was persist + restore + garbage→default, all covered.
3. **WU 4.5: design D8's main-window `keyPressEvent` → `_dispatch_key_event` was NOT added.** The PIP is created with the main window as QWidget parent, so Qt resolves the main window's `WindowShortcut` shortcuts for keys pressed on the PIP (verified by the four new tests passing against the existing code). Adding a second dispatch path would be speculative production code with no failing test (strict-TDD) and would introduce a double-dispatch risk. The `PIPWindow.keyPressEvent` forwarding (WU 4.1) remains for non-shortcut keys.
4. **Debounce flush in tests uses `_pump_events()` (a `processEvents` + sleep loop) instead of `qtbot.wait(350)`.** `qtbot.wait` runs a nested `QEventLoop` that crashes natively on this environment once windows from earlier tests accumulate; the pump yields identical observable behavior (the 300 ms timer still fires and flushes).

## Environment note (pre-existing, not introduced here)

On this machine the full suite exits with Windows code 139 (access violation during Qt teardown at process exit) whenever Qt window tests have run. Verified against the pristine tree: a `git worktree` at HEAD (`135766e`) running the original `tests/test_main_window.py` (41 tests) prints `41 passed` and exits 139 identically. Root cause: PyQt6 6.11 + pytest-qt 4.5 + offscreen teardown accumulation; independent of this change. The pytest summary (140 passed, 0 failed) is the gate signal, consistent with how the prior verify phase reported `130 passed`. This remediation introduces no mid-run abort.

## Remaining tasks (exact unchecked lines in `tasks.md`)

```text
- [ ] Run the app with a real channel playing on VLC, then on mpv; switch NORMAL→COMPACT→VIDEO→NORMAL, open/drag/resize/close PIP, toggle fullscreen and wait 3 s for the cursor to hide, move the mouse to restore it; record results as manual evidence (with the exact steps and pass/fail notes) in the verify/archive report. <!-- sdd-owner: implementation -->
- [ ] Run the complete automated suite once more (`pytest tests/ -q`) and record the final green result alongside the smoke evidence. <!-- sdd-owner: implementation -->
- [ ] Review the full change against this task list and the spec AC table (AC-1..AC-16); verify every scenario is covered by a test or the manual smoke evidence, and confirm the chained-PR slicing decision (PR 3 may need a further split at the ~400-line boundary). <!-- sdd-owner: parent -->
- [ ] After the last PR merges, run `sdd-verify` and, on PASS, `sdd-archive` recording the REQ-11 smoke evidence; if verification fails, route remediation back to the failing work unit. <!-- sdd-owner: parent -->
```

## Workload / PR boundary

- Original forecast: 4 chained PRs (`ask-on-risk`), delivered as 4 commits stacked-to-main (`134f8f1` PR1, `61aaeef` PR2, `3543ee8` PR3, `135766e` PR4) — boundary preserved.
- This remediation is a **single follow-up commit** on the `view-modes` chain (commit hash recorded in the phase result), touching only view-modes files: `pip_window.py`, `main_window.py`, `tests/test_main_window.py`, `tasks.md`, `apply-progress.md` (new). Diff size ≈ 120 source + 250 test + artifact lines; well under the 400-line budget.
- WU 5.1 (manual smoke, REQ-11) remains the only open delivery gate before archive.
