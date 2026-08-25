# Verify Report — view-modes

**Change:** `view-modes` · **Backend:** OpenSpec (file-backed; apply-progress found in Engram only)
**Verification date:** 2026-08-24 · **Verifier:** sdd-verify (sonnet)
**Strict TDD:** enabled (pytest 9.0.2 + pytest-qt 4.5.0)

## Verdict

**FAIL** — implementation is largely complete and the automated suite is green (130 passed), but one acceptance criterion (AC-13, PIP geometry persistence) is NOT implemented, unchecked implementation task markers remain in `tasks.md`, and the apply-progress artifact carries no `TDD Cycle Evidence` table. Archive is BLOCKED.

## Commands run

| Command | Result |
|---|---|
| `QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q` | **130 passed in 1.42s** (0 failures) |
| `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_view_mode_controller.py tests/test_config_roundtrip.py tests/test_main_window.py -q` | **74 passed** (29 + 4 + 41) |
| `grep -rn "setEnabled(False)" src/infrastructure/ui/main_window.py` | no match (exit 1) — REQ-9 constraint respected |

## Artifacts inspected

- `openspec/changes/view-modes/spec.md` (authoritative), `tasks.md`
- Commits: `134f8f1` (PR1), `61aaeef` (PR2), `3543ee8` (PR3), `135766e` (PR4)
- `src/application/services/view_mode_controller.py`, `main.py` (`load_config`/`save_config`), `src/infrastructure/ui/main_window.py`, `src/infrastructure/ui/components/pip_window.py`
- Tests: `tests/test_view_mode_controller.py`, `tests/test_config_roundtrip.py`, `tests/test_main_window.py`
- Engram observation `sdd/view-modes/apply-progress` (id 2565) — no `apply-progress.md` exists under `openspec/changes/view-modes/`

## Acceptance criteria results

| AC | Behavior | Result | Evidence |
|---|---|---|---|
| AC-1 | Startup default NORMAL (3 columns, video, menu bar) | **PASS** | `_apply_layout(NORMAL)`; `test_startup_default_is_normal_layout` |
| AC-2 | Compact: columns 1–2 hidden, table+video visible, menu hidden | **PASS** | `_apply_layout(COMPACT)`; `test_compact_layout_hides_columns_and_menubar` |
| AC-3 | Video: table hidden, video visible, menu hidden | **PASS** | `_apply_layout(VIDEO)`; `test_video_layout_hides_table_and_menubar` |
| AC-4 | Return to Normal; re-selecting active mode is no-op | **PASS** | controller `activate()` returns False on no-op, no listener/persist; `test_alt1_returns_to_normal`, `test_repressing_active_mode_shortcut_is_noop` |
| AC-5 | Fullscreen + cursor auto-hide after 3 s, restore on move | **PASS** | `_enter_fullscreen`/`_on_cursor_timeout`/`eventFilter`; `test_f_toggles_fullscreen_on/off`, `test_cursor_timeout_hides_cursor`, `test_mouse_move_restores_cursor_and_restarts_timer` |
| AC-6 | Esc exits fullscreen only when fullscreen | **PASS** | `_exit_fullscreen()` early-return; `test_escape_exits_fullscreen_only_when_fullscreen` |
| AC-7 | Mode persistence round-trip | **PASS** | `main.py` keys + `ViewMode.parse`; `test_new_keys_survive_round_trip`, `test_startup_applies_persisted_compact_mode` |
| AC-8 | Splitter persistence round-trip | **PASS** | debounced save + pre-hide snapshot + restore; `test_splitter_move_flush_persists_state`, `test_entering_video_writes_prehide_snapshot_synchronously`, `test_restart_in_video_returns_to_normal_restores_splitter` |
| AC-9 | Zap down/up in all modes, incl. Video | **PASS** | window-level Up/Down shortcuts + `resolve_zap_index`; `test_zap_down_plays_next_channel`, `test_zap_up_in_video_mode` |
| AC-10 | **REVISED** wrap-around edges; empty playlist no-op | **PASS** | `(index ± 1) % len`; `test_zap_down_at_last_wraps_to_first`, `test_zap_up_at_first_wraps_to_last`, `test_zap_empty_playlist_is_noop`, `test_zap_with_no_current_channel_plays_first` |
| AC-11 | PIP open: frameless always-on-top, main placeholder hidden | **PASS** | `PIPWindow` flags `Tool|FramelessWindowHint|WindowStaysOnTopHint`; `test_pip_window_has_detached_flags`, `test_p_opens_pip_and_hides_main_placeholder` |
| AC-12 | PIP toggle: widget returns to splitter | **PASS** | `_close_pip()` re-parent + `insertWidget(1)`; `test_p_closes_pip_and_widget_returns_to_splitter`, `test_alt4_toggles_the_same_pip_instance` |
| AC-13 | PIP geometry persistence AND restore | **FAIL** | restore-on-open implemented (`_apply_pip_geometry`), but NO code path writes `config['pip_geometry']` on move/resize (no `moveEvent`/`resizeEvent` handler, no debounce, no `save_callback`); no test exists for either half |
| AC-14 | **REVISED** menu shortcuts stay ACTIVE; `Ctrl+G` works; `isEnabled() == True` | **PASS** | window-level `Ctrl+G` QShortcut; grep proves no `setEnabled(False)`; `test_all_menu_actions_enabled_in_compact_and_video`, `test_ctrl_g_opens_epg_grid_in_compact_and_video`, `test_ctrl_g_works_after_returning_to_normal` |
| AC-15 | No context menu in Compact/Video | **PASS** | `NoContextMenu` in COMPACT/VIDEO, `DefaultContextMenu` in NORMAL; `_apply_layout` |
| AC-16 | Video re-target after every mode switch and PIP open/close | **PASS** (code) / WARNING (coverage) | `_retarget_video()` called on mode change (tested exactly-once: `test_mode_switch_retargets_video_exactly_once`) and in `_open_pip`/`_close_pip` (untested — no dedicated test) |

## Requirements results

| REQ | Result |
|---|---|
| REQ-1 Qt-free view-mode state machine | **PASS** — no `PyQt6` import in `view_mode_controller.py` (only `enum`/`typing`); 29 plain-pytest tests |
| REQ-2 Per-mode layout mapping | **PASS** |
| REQ-3 Mode shortcut registration | **PASS** |
| REQ-4 Fullscreen axis | **PASS** |
| REQ-5 Channel zapping with wrap-around | **PASS** — pure `resolve_zap_index` + window shortcuts |
| REQ-6 PIP detach window | **FAIL (partial)** — all behavior except geometry persistence (see AC-13) |
| REQ-7 Video re-target after visibility change | **PASS** (code) — `winId()` re-read at call time; mode-switch test only |
| REQ-8 Persistence of mode/splitter/PIP geometry | **FAIL (partial)** — `view_mode` + `splitter_state` round-trip; `pip_geometry` restore-only, never persisted |
| REQ-9 Menu shortcuts remain active | **PASS** |
| REQ-10 No context menu in Compact/Video | **PASS** |
| REQ-11 Real-engine smoke (VLC + mpv) | **MANUAL** — cannot be proven by pytest; not scored FAIL; WU 5.1 evidence pending (see below) |

## Findings

### CRITICAL

1. **AC-13 / REQ-8 / REQ-6 — PIP geometry is never persisted.** `main_window.py` reads `pip_geometry` in `_apply_pip_geometry` (open) but nothing writes it: no `moveEvent`/`resizeEvent` handler on `PIPWindow`, no debounce timer, no `save_callback` on move/resize. `pip_window.py` has only a `resizeEvent` that repositions the grip. The spec ("PIP geometry (`x, y, w, h`) MUST be persisted on move/resize … and restored when PIP is next opened") is only half implemented. No test covers this (WU 4.3 RED/GREEN never written).

2. **Unchecked implementation task markers remain in `tasks.md`.** WU 4.1–4.5 (all three steps each) and WU 5.1 are still `- [ ]`. WU 4.1/4.2 are stale (code + tests exist and pass), but WU 4.3 is genuinely incomplete and WU 5.1 awaits manual evidence. Exact unchecked implementation lines:
   - `- [ ] RED: component-level pytest-qt tests: ...` / `- [ ] GREEN: implement \`ResizeGrip(QWidget)\` ...` / `- [ ] REFACTOR: verify the grip and body drag paths ...` (WU 4.1)
   - `- [ ] RED: widget tests: \`Key_P\` ...` / `- [ ] GREEN: implement \`_toggle_pip()\` ...` / `- [ ] REFACTOR: confirm no startup path instantiates or shows \`PIPWindow\` ...` (WU 4.2)
   - `- [ ] RED: drag the PIP body and flush the debounce timer ...` / `- [ ] GREEN: implement D7 geometry handling ...` / `- [ ] REFACTOR: confirm geometry writes never fire when the PIP is closed ...` (WU 4.3 — NOT implemented)
   - `- [ ] RED: with the recording \`FakePlaybackManager\`: open PIP then close ...` / `- [ ] GREEN: call the WU 3.4 \`_retarget_video()\` helper ...` / `- [ ] REFACTOR: assert the total call count ...` (WU 4.4 — code exists, tests missing)
   - `- [ ] RED: open the PIP, then \`qtbot.keyClick(pip_window, Qt.Key.Key_Down)\` ...` / `- [ ] GREEN: implement D8 ...` / `- [ ] REFACTOR: prove no double-dispatch ...` (WU 4.5 — code exists, integration tests missing)
   - `- [ ] Run the app with a real channel playing on VLC, then on mpv ...` / `- [ ] Run the complete automated suite once more (\`pytest tests/ -q\`) ...` (WU 5.1 — manual evidence pending)
   - Parent-owned gates (`- [ ] Review the full change ...` / `- [ ] After the last PR merges, run \`sdd-verify\` ...`) also unchecked.
   
   Archive is not ready while these remain. The Engram apply-progress note ("130 tests green") is not sufficient to reconcile them: it contains no per-WU checklist and no TDD evidence table.

3. **Strict TDD evidence missing.** `apply-progress.md` does not exist under `openspec/changes/view-modes/` (the only apply-progress is an Engram observation, id 2565), and that observation contains **no `TDD Cycle Evidence` table**. Strict TDD verification rules require the table plus red-green evidence for each work unit; none is present. Per the strict-TDD contract this is CRITICAL.

### WARNING

4. **Dedicated tests missing for PIP re-target and PIP-focus key dispatch (WU 4.4, WU 4.5).** Code paths exist (`_retarget_video()` in `_open_pip`/`_close_pip`; `PIPWindow.keyPressEvent` → `QApplication.sendEvent(main_window, event)`), and a component-level forward test exists (`test_pip_forwards_key_events_to_target`), but there is no integration test asserting exactly two `initialize_display` calls across a PIP open+close cycle, nor end-to-end `keyClick(pip_window, Key_Down)` → `play_channel(...)`, `Alt+2`, `Ctrl+G` under PIP focus. Coverage gap for AC-16 (second half) and REQ-6 last scenario.

5. **Review-workload deviation not recorded.** The forecast flagged PR 3 as likely to approach the ~400-line budget ("Decision needed before apply: Yes"; PR 3 diff is 245 src + 635 test lines ≈ 880) and left `Chain strategy: pending`. The apply proceeded with a single undivided PR 3 commit and no recorded decision; the Engram note reports the strategy as `stacked-to-main` but there is no artifact proving the parent gate decision. Work boundary matches the 4-PR forecast; the missing record is the issue.

6. **Scope bleed in PR 2 and PR 3 commits.** Both commit messages note unrelated pre-existing working-tree changes (`player_factory build_player_adapter` refactor) were bundled into the view-modes commits. The working tree also carries unrelated uncommitted changes (`mpv_player_adapter.py`, `player_factory.py`, proxy files, docs). These do not break the build/tests but violate clean PR boundaries.

### SUGGESTION

7. **`apply-progress` backend inconsistency.** The change is OpenSpec-backed, but the apply phase wrote progress to Engram only and never created `openspec/changes/view-modes/apply-progress.md`. Either the store selection was hybrid, or the apply phase deviated; reconcile so archive has a single authoritative progress artifact.

8. **Assertion quality** (audited, no findings): the 74 new tests are behavior-focused with recording fakes (`FakePlaybackManager` records `play_channel`/`initialize_display`; recorder stubs for `EPGGridDialog`), exact call counts, no tautologies, no ghost loops, no type-only assertions, no implementation-detail CSS/geometry asserts beyond behavior. `setEnabled(False)` provably absent. Controller module is Qt-free (verified by reading imports). No CRITICAL/WARNING assertion-quality issues.

## Strict TDD compliance

- Strict TDD active (parent prompt + `tasks.md`). 
- Result: **NOT COMPLIANT as evidenced.** No `TDD Cycle Evidence` table exists (see CRITICAL 3). Test files do exist for WU 1.1–1.4, 2.1, 3.1–3.8 and most of 4.1/4.2, and the suite is green, but the RED→GREEN cycle per work unit is not recorded anywhere retrievable. The apply note's "130 tests green" claim was independently confirmed by this verification run.

## Review workload / PR boundary

- Forecast: 4 chained PRs (`ask-on-risk`). Delivered: 4 sequential commits (`stacked-to-main` per Engram note) — boundary matches.
- PR 3 slice not split despite the forecast's ~400-line flag and `Decision needed before apply: Yes` (WARNING 5).
- `size:exception` not recorded (not applicable — no exception was requested).
- Scope creep beyond assigned tasks: unrelated `player_factory` refactor bundled into PR 2/3 commits (WARNING 6).

## Manual verification items

- **REQ-11 (AC manual smoke):** run the app with a real channel on VLC and on mpv; switch NORMAL→COMPACT→VIDEO→NORMAL; open/drag/resize/close PIP; toggle fullscreen and wait 3 s for cursor hide, move mouse to restore; verify `Alt+1..4` pass through the native Windows menu bar. Record pass/fail notes in the archive report. WU 5.1 remains open until this evidence exists; it is a delivery/archive gate, not an automated FAIL.

## Blockers (exact)

1. AC-13: `pip_geometry` persistence on move/resize not implemented (code + tests) — CRITICAL.
2. `tasks.md` unchecked implementation markers WU 4.1–4.5 (4.3 genuinely incomplete; 4.4/4.5 missing dedicated tests) and WU 5.1 (manual smoke pending) — CRITICAL, archive blocked.
3. No `TDD Cycle Evidence` table and no OpenSpec `apply-progress.md` — CRITICAL strict-TDD evidence gap.

## Remediation (for parent/apply, not performed by verify)

1. Implement PIP geometry persistence (debounced write of `config['pip_geometry']` + `save_callback` on body move and grip resize; cancel on close), per WU 4.3.
2. Add WU 4.3 tests (persist on drag/resize, restore on reopen, garbage → default) and WU 4.4/4.5 integration tests (exactly two `initialize_display` on open+close; `keyClick(pip_window, …)` for `↓`, `P`, `Alt+2`, `Ctrl+G`).
3. Reconcile `tasks.md` checkboxes with apply evidence and create `openspec/changes/view-modes/apply-progress.md` with a `TDD Cycle Evidence` table.
4. Run REQ-11 manual smoke on both engines and record evidence.
5. Re-run `pytest tests/ -q` and re-verify before archive.
