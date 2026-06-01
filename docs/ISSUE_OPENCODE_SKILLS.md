# feat: OpenCode skills — browser automation, skill-authoring & learning-by-doing (incl. macOS screen-record + vision)

> Full design & complete code blocks: **`docs/PLAN_OPENCODE_SKILL_AND_LEARNING.md`**

## Goal
Give OpenCode CLI agents everything they need to build, run, and **continuously
improve** browser automations with SIN-Browser-Tools — including a macOS
screen-recording + vision-analysis loop so an agent always knows *what happened*
and *what went wrong* when it fails.

## Deliverables — three integrated OpenCode skills (`.opencode/skills/`)
1. **`sin-browser-automation`** — which `browser_*` tool to use, when, and in
   which order. Enforces the LOOK → DECIDE → ACT → VERIFY loop, with
   `reference/sequencing.md`, `reference/error-recovery.md`, auto-generated
   `reference/tool-decision-tree.md`.
2. **`sin-browser-skill-authoring`** — turn a proven run into a reusable skill;
   templates + `python -m sin_browser_tools.skills.generator` scaffold/validate.
3. **`sin-browser-learning`** — record runs as playbooks, retrieve the best known
   trajectory before improvising, rank by success/efficiency, and on failure
   **auto-capture a macOS screen recording and vision-analyze it**.

## New code
- `sin_browser_tools/playbook.py` — file-based playbook store + ranking.
- `sin_browser_tools/tools/learning.py` — `browser_playbook_suggest/record/list/compare`.
- `sin_browser_tools/core/screen_record.py` — ffmpeg/screencapture backends,
  window-region capture, keyframe extraction.
- `sin_browser_tools/tools/screen_record.py` — `browser_screen_record_start/stop/analyze`.
- `sin_browser_tools/skills/generator.py` — skill scaffold + validation.
- `scripts/gen_skill_references.py` — auto-generate decision tree from catalog.
- Manager hook `note_tool_failure(...)` → auto-record on first failure
  (`SIN_AUTO_RECORD_ON_FAILURE`, default on, macOS only).

## Acceptance Criteria
- [ ] Three `SKILL.md` files present and `generator.py --validate` passes for each.
- [ ] New tools discoverable via `catalog.discover()` (`browser_playbook_*`,
      `browser_screen_record_*`); tool-count assertion updated.
- [ ] Playbooks persist to `.sin_playbooks/<task>/<url_hash>/variants.json`,
      ranked by success_rate then avg_steps; metrics merge across runs.
- [ ] `screen_record_start/stop` produce a video on macOS; non-macOS returns a
      structured `unsupported`. `analyze` extracts frames and returns a
      structured failure report (summary, failure frame, recommended `browser_*` fix).
- [ ] Auto-record triggers on the first `ok:false` mid-run when enabled.
- [ ] Tests: `test_playbook.py`, `test_learning_tools.py`, `test_skill_generator.py`,
      `test_screen_record.py` (platform-guarded).
- [ ] Docs: `PERMISSIONS_MACOS.md` (Screen Recording permission + ffmpeg install),
      `AGENTS.md`/`COOKBOOK.md` updated with the learning loop & "record on failure" rule.
- [ ] `.gitignore` excludes `.sin_recordings/` and `.sin_playbooks/`.

## Implementation order
1. Core: `playbook.py`, `tools/learning.py`.
2. Recording: `core/screen_record.py`, `tools/screen_record.py`, manager hook.
3. Skills: three `SKILL.md` + reference/ + templates/.
4. Generator + auto-gen scripts.
5. Catalog/`__init__` wiring, `.gitignore`, docs.
6. Tests green (`python -m pytest`) → commit → push `main`.

## Risks / decisions
- macOS screen recording needs the **Screen Recording permission**; window-region
  capture reuses the WindowController from the window/spaces plan.
- ffmpeg is a system tool (not pip) — documented, with `screencapture` fallback.
- Vision analysis reuses `tools/vision.py`; add a multi-image `analyze_images`
  (fallback to single-frame analysis).
- Default `SIN_AUTO_RECORD_ON_FAILURE=true` (macOS only) — flip to opt-in if noisy.

Related: window/spaces plan (`docs/PLAN_WINDOW_SPACES_AND_FIXES.md`).
