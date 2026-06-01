# Plan: OpenCode-CLI-Skill für SIN-Browser-Tools + Learning-by-Doing

> **Status:** **IMPLEMENTIERT** (Commit `192a607`, 2026-06-01)
> - [x] Core: playbook.py, learning.py, screen_record.py
> - [x] Skills: sin-browser-automation, sin-browser-skill-authoring, sin-browser-learning
> - [x] Generator: skills/generator.py
> - [x] Tests: test_playbook.py, test_screen_record.py, test_skill_generator.py
> - [x] Verkabelung: catalog.py, tools/__init__.py, .gitignore
>
> **Verwandt:** baut auf `AGENTS.md` (Loop), `COOKBOOK.md` (Rezepte),
> `sin_browser_tools/opensin_skill.py` (Tool-Registry aus Catalog) auf.
> **Prinzip dieser Plan-Datei:** Jede neue Datei steht hier **vollständig mit
> Code in Blöcken**, damit bei der Umsetzung nichts fehlen oder vergessen werden
> kann.

---

## 0. Ziel in einem Satz

Ein Agent in der **OpenCode CLI** soll mit einem einzigen Skill (a) wissen,
**welche SIN-Browser-Tools in welcher Reihenfolge** eine Automation lösen, (b)
**eigene Browser-Automation-Skills** erzeugen können und (c) Automationen über
ein **Learning-by-Doing-System** (selbst-erzeugte, bewertete Trajektorien —
ähnlich Behavior-Cloning / Offline-RL) **messbar verbessern**.

---

## 1. Was es heute gibt vs. was fehlt

| Vorhanden | Lücke |
|-----------|-------|
| `AGENTS.md` — Loop & Error→Fix-Tabelle | Kein **OpenCode-Skill** (`SKILL.md`), der das automatisch lädt |
| `COOKBOOK.md` — 10 Rezepte | Kein **Skill-Generator** für neue, wiederverwendbare Automationen |
| `opensin_skill.py` — Tool-Registry aus Catalog | Kein **Gedächtnis**: jede Session startet bei null, lernt nichts |
| `MCP`-Server (52+ Tools) | Keine **Bewertung/Optimierung** erfolgreicher Abläufe über Zeit |

**Kernidee:** Wir fügen drei Schichten hinzu:
1. **Skill-Schicht** (`.opencode/skills/...`) — deklaratives Wissen für OpenCode.
2. **Skill-Generator** (`sin_browser_tools/skills/generator.py`) — erzeugt aus
   einer erfolgreichen Session einen neuen, parametrisierten Skill.
3. **Learning-Schicht** (`sin_browser_tools/learning/`) — speichert Episoden,
   bewertet Trajektorien, liefert beim nächsten Lauf den besten bekannten Weg.

---

## 2. OpenCode-Skill-Format (recherchiert)

OpenCode entdeckt Skills unter:
- Projekt: `.opencode/skills/<name>/SKILL.md`
- Global: `~/.config/opencode/skills/<name>/SKILL.md`

`SKILL.md` beginnt mit YAML-Frontmatter (`name`, `description` Pflicht); der
`name` **muss** dem Ordnernamen entsprechen. Die `description` ist der primäre
Trigger, mit dem der Agent entscheidet, ob er den Skill lädt — also dicht &
spezifisch halten. Der Markdown-Body enthält die eigentliche Anleitung und darf
auf weitere Dateien im Skill-Ordner verweisen (progressive disclosure).

---

## 3. Verzeichnis-Layout (neu)

```text
.opencode/
  skills/
    sin-browser-automation/        # Haupt-Skill: Tools + Loop + Tool-Auswahl
      SKILL.md
      reference/
        tool-decision-tree.md      # "Was will ich -> welches Tool" (erweitert)
        sequencing.md              # Reihenfolge-Muster (Login, Webmail, Forms, ...)
        error-recovery.md          # Error -> Fix (aus AGENTS.md, kondensiert)
    sin-browser-skill-authoring/   # Meta-Skill: wie man EIGENE Skills baut
      SKILL.md
      templates/
        SKILL.template.md
        automation.template.py
    sin-browser-learning/          # Meta-Skill: Learning-by-Doing
      SKILL.md
      reference/
        learning-loop.md

sin_browser_tools/
  skills/
    __init__.py
    generator.py                   # erzeugt Skill-Dateien aus einer Session
    generator.md
  learning/
    __init__.py
    playbook.py                    # Episoden-Speicher + beste Trajektorie
    playbook.md
    journal.py                     # rohes Episoden-Log (append-only)
    scorer.py                      # bewertet/aggregiert Trajektorien
    learning.md

docs/
  SKILLS_AND_LEARNING.md           # Gesamtüberblick (Mensch + Agent)
examples/
  07_learning_loop.py              # lauffähiges Beispiel
tests/
  test_playbook.py
  test_skill_generator.py
```

---

## 4. Skill 1 — `sin-browser-automation` (Tools + Reihenfolge)

**Datei `.opencode/skills/sin-browser-automation/SKILL.md`:**

````markdown
---
name: sin-browser-automation
description: |-
  Drive a real Chromium browser with SIN-Browser-Tools (52+ browser_* MCP tools)
  to automate web tasks: login, webmail (GMX/web.de OOPIF), forms, search,
  scraping, file upload, multi-tab, shadow DOM. Use whenever the task is
  "go to a website and do X", "log into ...", "read the email / OTP", "fill out
  the form", "scrape ...", or any browser interaction. Teaches the mandatory
  LOOK -> DECIDE -> ACT -> VERIFY loop, which tool to use when, correct ordering,
  and how to recover from failed clicks (OOPIF, stale refs, shadow DOM, dialogs).
---

# SIN Browser Automation

You drive a **real** browser. You are blind without a snapshot. Follow the loop.

## The only loop you ever run
```
1. LOOK    browser_snapshot            -> page as @e1, @e2 ... refs
2. DECIDE  pick ONE @eN
3. ACT     browser_click / browser_type / ... with that @eN
4. VERIFY  browser_snapshot again, confirm the change
```
Never chain two ACT steps without a LOOK. Refs reset on every snapshot; a ref
from a previous snapshot is **stale**.

## First calls of any session
```text
browser_list_tools()                 # discover what exists (and search by keyword)
browser_navigate("https://...")
browser_wait_for_load("networkidle")
browser_snapshot()                   # now you have refs
```

## Pick the right tool (fast)
| I want to... | Tool |
|---|---|
| See page / get refs | `browser_snapshot` |
| See cross-origin iframes (webmail!) | `browser_snapshot_full_oopif` |
| Click button/link | `browser_click("@e7")` |
| Click didn't work | `browser_click_cdp("@e7")` |
| Click by visible label | `browser_click_by_text("Accept all")` |
| Type | `browser_type("@e3","text")` |
| Dropdown | `browser_select_option("@e4", label="…")` |
| Go to URL | `browser_navigate(url)` |
| Wait for content | `browser_wait_for_text("Inbox")` |
| Read text | `browser_get_text` |
| Find text/ref in any frame | `browser_find_by_text`, `browser_scan_frames` |
| New tab opened | `browser_list_tabs` + `browser_switch_tab` |
| Popup/alert | `browser_dialog("accept")` |

When unsure: `browser_list_tools("keyword")`.

## Ordering patterns (load on demand)
- Login, webmail/OOPIF, multi-field forms, search, scraping, OTP-from-iframe:
  see `reference/sequencing.md`.
- Full decision tree: `reference/tool-decision-tree.md`.
- Stuck / a click vanished / stale ref / shadow DOM: `reference/error-recovery.md`.

## Golden rules
1. Snapshot before every act. 2. Only refs from the latest snapshot.
3. Target by ref, not guessed CSS. 4. One action at a time.
5. A failed click is NOT repeated 5x — switch to `browser_click_cdp` or consult
   error-recovery. 6. Wait for load/text before snapshotting. 7. Read each tool
   result's `ok`/`error`; on `ok:false`, STOP and act on `error`.

## Learn from every run
If the `sin-browser-learning` skill is available, **before** improvising call
`playbook_suggest(task, url)` to get the best known trajectory, and **after**
finishing call `playbook_record(...)`. See that skill for details.
````

**Datei `.opencode/skills/sin-browser-automation/reference/sequencing.md`** —
kondensierte, geordnete Sequenzen (aus `COOKBOOK.md` übernommen: Login,
Webmail-OOPIF, Forms, Search, New-Tab, OTP-aus-iframe, Shadow-DOM). Wird per
progressive disclosure nur bei Bedarf geladen.

**Datei `.opencode/skills/sin-browser-automation/reference/error-recovery.md`** —
die Error→Fix-Tabelle + OOPIF/Shadow-DOM-Absatz aus `AGENTS.md`.

**Datei `.opencode/skills/sin-browser-automation/reference/tool-decision-tree.md`**
— wird beim Build **auto-generiert** aus dem Catalog (siehe §8 Generator), damit
sie nie driftet.

---

## 5. Skill 2 — `sin-browser-skill-authoring` (eigene Skills bauen)

**Datei `.opencode/skills/sin-browser-skill-authoring/SKILL.md`:**

````markdown
---
name: sin-browser-skill-authoring
description: |-
  Create a NEW reusable browser-automation skill from a task you just solved (or
  want to solve) with SIN-Browser-Tools. Use when the user says "make a skill
  for this", "save this automation", "turn this flow into a reusable skill", or
  when you finished a multi-step browser task worth reusing. Produces a valid
  OpenCode SKILL.md plus an optional parametrized Python automation, following
  the repo conventions.
---

# Authoring a SIN browser-automation skill

## When to create a skill
Create one when a browser flow is (a) multi-step, (b) likely to repeat, and
(c) parametrizable (URL, credentials-ref, search term, ...). One flow = one skill.

## Steps
1. **Name it** lowercase-hyphenated, e.g. `gmx-read-latest-otp`. The folder name
   MUST equal the frontmatter `name`.
2. **Write the trajectory** as the proven ordered tool sequence (the one that
   actually worked — copy it from your run or from `playbook_suggest`).
3. **Generalize**: replace concrete values with `{{params}}` (url, query, ...).
   Replace concrete `@eN` refs with *intent* ("the Sign-in button") because refs
   are session-specific — the runner re-snapshots and re-resolves by text/role.
4. **Emit files** with the helper:
   ```bash
   python -m sin_browser_tools.skills.generator \
     --name gmx-read-latest-otp \
     --description "Log into GMX and return the latest 6-digit OTP from the newest email." \
     --from-playbook gmx.net::read-otp        # or --from-journal <run_id>
   ```
   This writes `.opencode/skills/<name>/SKILL.md` and (optional)
   `automation.py` from the templates in `templates/`.
5. **Validate**: `python -m sin_browser_tools.skills.generator --validate <name>`
   checks frontmatter, name==folder, and that every referenced tool exists in
   the catalog.

## SKILL.md template
See `templates/SKILL.template.md`. The body MUST: state the loop reminder, the
ordered steps with the correct tool per step, parameters, success check
(a `browser_wait_for_text` proof), and an error-recovery pointer.

## Rules
- Never bake real credentials into a skill. Reference the session vault
  (`browser_*` cookie/storage tools) or a `{{secret_ref}}`.
- Every step names the exact `browser_*` tool. No vague "click around".
- End with a VERIFY step that proves success.
````

**Datei `.opencode/skills/sin-browser-skill-authoring/templates/SKILL.template.md`:**
```markdown
---
name: {{name}}
description: |-
  {{description}}
---

# {{title}}

Loop reminder: LOOK -> DECIDE -> ACT -> VERIFY. Refs reset on every snapshot.

## Parameters
{{params_block}}   # e.g. - url (string, required): start page

## Steps
{{steps_block}}    # ordered "N. <intent> -> browser_<tool>(...)" lines

## Success check
{{success_block}}  # e.g. browser_wait_for_text("...") proving the goal

## If stuck
Consult the `sin-browser-automation` skill's reference/error-recovery.md.
```

**Datei `.opencode/skills/sin-browser-skill-authoring/templates/automation.template.py`:**
```python
"""Auto-generated automation: {{name}}.

Parametrized, re-snapshotting runner. Refs are resolved by INTENT (text/role)
at runtime via browser_find_by_text, NOT by hard-coded @eN.
"""
import asyncio
from sin_browser_tools.core import manager
from sin_browser_tools.tools import navigation, interaction, extraction


async def run({{signature}}):
    await manager.start_local(headless={{headless}})
    try:
        # {{steps_as_code}}  -- generator fills proven steps here
        ...
        return {"status": "ok"}
    finally:
        await manager.cleanup()


if __name__ == "__main__":
    asyncio.run(run())
```

---

## 6. Skill 3 — `sin-browser-learning` (Learn-by-Doing, Playbook + Screen-Record)

**Idee:** Jeder Run wird als **Playbook** (Trajectory + Metriken) gespeichert.
Vor einem neuen ähnlichen Task ruft der Agent `playbook_suggest` → nutzt bewährte
Sequenz statt zu improvisieren. Nach dem Run `playbook_record`. **Bei Fehlern**
wird automatisch eine **Screen-Recording + Vision-Analyse** angehängt (siehe §7),
damit der Agent „sieht", was schiefging.

**Datei `.opencode/skills/sin-browser-learning/SKILL.md`:**

````markdown
---
name: sin-browser-learning
description: |-
  Learn from previous browser-automation runs and self-improve. Record successful
  trajectories as reusable playbooks, retrieve the best known sequence before
  trying, and rank by success/efficiency. CRUCIAL: when an automation FAILS, this
  skill auto-captures a macOS screen recording of the run and analyzes the video
  with vision to explain what happened and what went wrong. Use when starting a
  task similar to past runs, finishing a run worth memorizing, or recovering from
  a failure you need to diagnose visually.
---

# SIN Browser Learning

Record runs. Retrieve patterns before improvising. On failure, WATCH THE REPLAY.

## Tools
- **playbook_suggest(task, url)** — best known trajectory (ranked).
- **playbook_record(task, url, trajectory, metrics)** — save/update + auto-rank.
- **playbook_list(filter)** / **playbook_compare(task, url)** — inspect library.
- **screen_record_start(label)** — begin a macOS screen recording of THIS run.
- **screen_record_stop()** — stop and return the saved video path.
- **screen_record_analyze(path, question)** — vision-analyze the video: what
  happened, where it broke, what the UI showed at the failure moment.

## The self-improving loop
```
1. Task arrives -> playbook_suggest(task, url)
2. screen_record_start("task-name")        # always record; cheap insurance
3. Execute (use suggested trajectory or sin-browser-automation skill)
4a. SUCCESS -> screen_record_stop(); playbook_record(... success metrics ...)
4b. FAILURE -> screen_record_stop()
              -> screen_record_analyze(video, "what went wrong at the failing step?")
              -> use the vision findings to fix the trajectory, retry once
              -> playbook_record(... with failure note + corrected steps ...)
```

## When to ALWAYS screen-record (mandatory)
- Any task you have failed at before (playbook shows success_rate < 1.0).
- Any task with >8 steps, login/OTP, OOPIF webmail, file upload, payment.
- The moment a tool returns `ok:false` mid-run -> if not already recording,
  start one and reproduce, so the failure is captured on video.

## Why video (not just snapshots)
Snapshots are point-in-time. A recording shows *timing* problems: a button that
appeared then vanished, a redirect that flashed an error, an overlay that
intercepted the click, a CAPTCHA, a slow spinner. Vision analysis of the clip
pinpoints the exact frame where reality diverged from the plan.

See `reference/screen-record.md` for the full failure-diagnosis recipe and
`integration.md` for storage/ranking details.
````

**Datei `.opencode/skills/sin-browser-learning/reference/screen-record.md`:**
````markdown
# Failure diagnosis via screen recording + vision

## Recipe: an automation just failed
```python
# 1. Stop the recording you started at run begin
video = await screen_record_stop()              # -> {"path": ".sin_recordings/...mp4"}

# 2. Ask vision exactly what went wrong
report = await screen_record_analyze(
    video["path"],
    question="The click on the 'Send' button failed. Watch the video and tell me: "
             "did the button move, was there an overlay/cookie banner, did the page "
             "redirect, or did a dialog appear? Report the timestamp of the problem."
)
# report -> {"summary": "...", "failure_frame_s": 4.2, "observations": [...],
#            "recommended_fix": "dismiss cookie banner with browser_click_by_text('Accept all') first"}

# 3. Apply the recommended fix, retry once, then record the corrected playbook
```

## What the analyzer extracts
- The frame/timestamp where the UI diverged from the expected state.
- Visual blockers: cookie banners, modals, CAPTCHAs, spinners, error toasts.
- Whether a navigation/redirect happened unexpectedly.
- A concrete `recommended_fix` mapped to a `browser_*` tool when possible.

## Privacy / scope
Recording captures the screen (or, preferred, only the browser window region).
Use `screen_record_start(region="window")` to limit capture to the browser
window bounds (resolved via the WindowController from the window/spaces plan).
Recordings live in `.sin_recordings/` and are gitignored.
````

---

## 7. Feature — macOS Screen Recording + Vision (`core/screen_record.py`)

**Mechanik:** macOS bringt `screencapture -v` (Video) mit; alternativ `ffmpeg`
mit `avfoundation`. Wir kapseln beide als Backends mit Auto-Erkennung. Für die
**fenster-genaue** Aufnahme nutzen wir die Fenster-Bounds aus dem Window-Plan
(`WindowController.get_bounds()`), sonst Vollbild. Vision-Analyse läuft über die
bereits vorhandene Vision-Infrastruktur (`tools/vision.py` / VLM), der wir
keyframes (extrahiert via ffmpeg) übergeben.

**Komplette neue Datei:**

```python
# sin_browser_tools/core/screen_record.py
"""macOS-Screen-Recording + Frame-Extraktion für die Vision-Analyse.

Backends (Auto-Erkennung): ffmpeg(avfoundation) > screencapture.
Nicht-macOS -> strukturierte "unsupported"-Antwort statt Exception.
"""

import asyncio
import platform
import shutil
import time
from pathlib import Path
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)
IS_MACOS = platform.system() == "Darwin"


async def _run(cmd: list[str], timeout: float = 30.0) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "", "timeout"
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")


class ScreenRecorder:
    """Eine Aufnahme-Session. start() -> ... -> stop() liefert den Videopfad."""

    def __init__(self, out_dir: str = ".sin_recordings"):
        self.out_dir = Path(out_dir)
        self.out_dir.mkdir(exist_ok=True)
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._path: Optional[Path] = None
        self._backend = self._detect_backend()

    def _detect_backend(self) -> Optional[str]:
        if not IS_MACOS:
            return None
        if shutil.which("ffmpeg"):
            return "ffmpeg"
        if shutil.which("screencapture"):
            return "screencapture"
        return None

    def _unsupported(self) -> dict:
        if not IS_MACOS:
            return {"status": "unsupported", "error": "Screen recording is macOS-only here.",
                    "platform": platform.system()}
        return {"status": "error",
                "error": "No recorder backend. Install ffmpeg (brew install ffmpeg).",
                "see": "docs/PERMISSIONS_MACOS.md"}

    async def start(self, label: str = "run",
                    region: Optional[tuple[int, int, int, int]] = None) -> dict:
        """Aufnahme starten. region = (x, y, w, h) für fenster-genaue Aufnahme.

        Braucht die Screen-Recording-Permission (System Settings > Privacy).
        """
        if not self._backend:
            return self._unsupported()
        ts = time.strftime("%Y%m%d-%H%M%S")
        self._path = self.out_dir / "{}-{}.mp4".format(label.replace("/", "_"), ts)

        if self._backend == "ffmpeg":
            # avfoundation: "1" = Bildschirm-Index (Capture). -r 5 = 5 fps reicht.
            cmd = ["ffmpeg", "-y", "-f", "avfoundation", "-r", "5", "-i", "1:none"]
            if region:
                x, y, w, h = region
                cmd += ["-vf", "crop={}:{}:{}:{}".format(w, h, x, y)]
            cmd += ["-pix_fmt", "yuv420p", str(self._path)]
        else:  # screencapture -v (Video), -V <sec> ohne -> bis SIGINT
            cmd = ["screencapture", "-v", str(self._path)]

        self._proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        return {"status": "ok", "backend": self._backend, "path": str(self._path),
                "recording": True, "label": label}

    async def stop(self) -> dict:
        """Aufnahme sauber beenden (q an ffmpeg / SIGINT an screencapture)."""
        if not self._proc:
            return {"status": "error", "error": "no active recording"}
        try:
            if self._backend == "ffmpeg":
                try:
                    self._proc.stdin.write(b"q")
                    await self._proc.stdin.drain()
                except Exception:
                    self._proc.terminate()
            else:
                self._proc.send_signal(__import__("signal").SIGINT)
            await asyncio.wait_for(self._proc.wait(), timeout=15.0)
        except asyncio.TimeoutError:
            self._proc.kill()
        finally:
            self._proc = None
        exists = self._path and self._path.exists()
        return {"status": "ok" if exists else "error",
                "path": str(self._path) if self._path else None,
                "exists": bool(exists)}

    async def extract_frames(self, video_path: str, every_s: float = 1.0,
                             max_frames: int = 12) -> list[str]:
        """Keyframes via ffmpeg extrahieren -> Liste PNG-Pfade (für Vision)."""
        if not shutil.which("ffmpeg"):
            return []
        frames_dir = Path(video_path).with_suffix("")
        frames_dir.mkdir(exist_ok=True)
        pattern = str(frames_dir / "frame-%03d.png")
        rc, _, _ = await _run(
            ["ffmpeg", "-y", "-i", video_path,
             "-vf", "fps=1/{}".format(every_s), "-frames:v", str(max_frames), pattern],
            timeout=60.0,
        )
        if rc != 0:
            return []
        return sorted(str(p) for p in frames_dir.glob("frame-*.png"))
```

### 7.1 `sin_browser_tools/tools/screen_record.py` (Tools für Skills)

```python
"""Screen-Recording- + Vision-Analyse-Tools.

    browser_screen_record_start(label, region="window"|"full")
    browser_screen_record_stop()
    browser_screen_record_analyze(path, question)
"""

from typing import Optional

from sin_browser_tools.core import manager
from sin_browser_tools.core.screen_record import ScreenRecorder

_recorder: Optional[ScreenRecorder] = None


async def browser_screen_record_start(label: str = "run", region: str = "window") -> dict:
    """Start a macOS screen recording of the current run.

    region="window" records only the browser window bounds (via WindowController);
    region="full" records the whole screen. macOS-only; needs Screen Recording
    permission. Call this at run start, especially for risky/failed-before tasks.
    """
    global _recorder
    _recorder = ScreenRecorder()
    crop = None
    if region == "window":
        inst = getattr(manager, "_instance", None)
        win = getattr(inst, "window", None)
        if win is not None:
            try:
                b = await win.get_bounds()
                if all(b.get(k) is not None for k in ("left", "top", "width", "height")):
                    crop = (int(b["left"]), int(b["top"]), int(b["width"]), int(b["height"]))
            except Exception:
                crop = None
    return await _recorder.start(label, region=crop)


async def browser_screen_record_stop() -> dict:
    """Stop the active recording and return the saved video path."""
    if _recorder is None:
        return {"status": "error", "error": "no recorder started"}
    return await _recorder.stop()


async def browser_screen_record_analyze(path: str, question: str) -> dict:
    """Vision-analyze a recorded run: what happened, where it broke, why.

    Extracts keyframes from the video and feeds them (in order, with timestamps)
    to the existing vision model. Returns a structured failure report with the
    likely failure timestamp and a recommended browser_* fix.
    """
    rec = _recorder or ScreenRecorder()
    frames = await rec.extract_frames(path)
    if not frames:
        return {"status": "error", "error": "no frames extracted (need ffmpeg)",
                "path": path}

    # Reuse the project's vision pipeline. analyze_images is expected to accept an
    # ordered list of image paths + a prompt and return text/structured findings.
    from sin_browser_tools.tools import vision
    prompt = (
        "These are sequential keyframes (≈1s apart) of a browser automation run.\n"
        "Question: {q}\n"
        "Identify the frame index where the UI diverged from the expected action, "
        "describe visual blockers (cookie banner, modal, CAPTCHA, spinner, error "
        "toast), note any unexpected redirect, and give ONE concrete recommended "
        "fix mapped to a browser_* tool if possible. Answer as JSON with keys "
        "summary, failure_frame_index, observations, recommended_fix."
    ).format(q=question)

    try:
        result = await vision.analyze_images(frames, prompt)  # type: ignore[attr-defined]
    except AttributeError:
        # Fallback: analyze the single most relevant frame via existing tool.
        result = await vision.browser_analyze_screenshot(frames[-1], prompt)  # type: ignore

    return {"status": "ok", "path": path, "frames_analyzed": len(frames),
            "analysis": result}
```

> **Verkabelung:** beide neuen Module in `tools/catalog.py` `TOOL_MODULES`
> ergänzen (`learning`, `screen_record`), in `tools/__init__.py` re-exportieren,
> in `.gitignore` `.sin_recordings/` + `.sin_playbooks/` aufnehmen, in
> `docs/PERMISSIONS_MACOS.md` die **Screen-Recording-Permission** + `ffmpeg`-
> Installation dokumentieren.

### 7.2 Auto-Trigger bei Fehlern (Manager-Hook)

Damit Agenten **automatisch** aufzeichnen, wenn sie scheitern, ergänzen wir im
`BrowserManager` einen optionalen Failure-Hook. Konzept (Diff in `core/manager.py`):

```python
# in __init__:
self.auto_record_on_failure = _as_bool(os.getenv("SIN_AUTO_RECORD_ON_FAILURE"), True)
self._consecutive_failures = 0

async def note_tool_failure(self, tool_name: str, error: str) -> None:
    """Vom Tool-Layer bei ok:false aufgerufen. Startet nach 1. Fehler eine
    Aufnahme, damit der nächste Reproduktionsversuch auf Video ist."""
    self._consecutive_failures += 1
    if self.auto_record_on_failure and self._consecutive_failures == 1 and IS_MACOS:
        try:
            from sin_browser_tools.tools import screen_record
            await screen_record.browser_screen_record_start(
                label="autofail-{}".format(tool_name), region="window")
            logger.warning("auto screen-record started after failure",
                           tool=tool_name, error=error)
        except Exception as e:
            logger.debug("auto-record failed to start", error=str(e))
```

Der zentrale Tool-Dispatcher (Catalog/MCP-Layer) ruft bei `result.get("ok") is
False` `manager.note_tool_failure(name, result["error"])` auf; bei Erfolg
`self._consecutive_failures = 0`.

---

## 8. Python Core Modules (Playbook + Generator + Learning-Tools)

### 8.1 `sin_browser_tools/playbook.py` (Storage + Ranking)

```python
"""Playbook system: record, retrieve, rank browser-automation trajectories."""

import json, time, hashlib
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict

import structlog
logger = structlog.get_logger(__name__)


@dataclass
class Metrics:
    success_rate: float = 1.0      # 0..1
    avg_steps: float = 0.0
    avg_latency: float = 0.0       # seconds
    avg_user_rating: float = 5.0   # 1..5
    total_runs: int = 1
    last_used: float = 0.0


@dataclass
class PlaybookVariant:
    variant_id: str
    trajectory: list[dict[str, Any]]
    created_at: float
    last_updated: float
    metrics: Metrics
    feedback: Optional[str] = None
    failure_video: Optional[str] = None   # link to a recorded failure clip


class PlaybookStore:
    """File-based storage in `.sin_playbooks/<task>/<url_hash>/variants.json`."""

    def __init__(self, base_dir: str = ".sin_playbooks"):
        self.base_dir = Path(base_dir); self.base_dir.mkdir(exist_ok=True)

    def _task_dir(self, task: str) -> Path:
        return self.base_dir / task.replace("/", "_").replace(":", "_").lower()

    def _url_hash(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:8]

    def _variant_file(self, task: str, url: str) -> Path:
        d = self._task_dir(task) / self._url_hash(url)
        d.mkdir(parents=True, exist_ok=True)
        return d / "variants.json"

    def load_variants(self, task: str, url: str) -> list[PlaybookVariant]:
        path = self._variant_file(task, url)
        if not path.exists():
            return []
        try:
            data = json.load(open(path))
            variants = [
                PlaybookVariant(
                    variant_id=v["variant_id"], trajectory=v["trajectory"],
                    created_at=v["created_at"], last_updated=v["last_updated"],
                    metrics=Metrics(**v["metrics"]), feedback=v.get("feedback"),
                    failure_video=v.get("failure_video"),
                ) for v in data.get("variants", [])
            ]
            variants.sort(key=lambda v: (-v.metrics.success_rate, v.metrics.avg_steps))
            return variants
        except Exception as e:
            logger.warning("load variants failed", path=str(path), error=str(e))
            return []

    def save_variant(self, task: str, url: str, trajectory: list[dict],
                     success: bool, steps: int, latency: float,
                     user_rating: float = 5.0, failure_video: Optional[str] = None,
                     keep_top: int = 5) -> str:
        path = self._variant_file(task, url)
        variants = self.load_variants(task, url)
        vid = hashlib.sha256(json.dumps(trajectory, sort_keys=True).encode()).hexdigest()[:16]
        existing = next((v for v in variants if v.variant_id == vid), None)
        now = time.time()

        if existing:
            m, n = existing.metrics, existing.metrics.total_runs
            m.success_rate = (m.success_rate * n + (1.0 if success else 0.0)) / (n + 1)
            m.avg_steps = (m.avg_steps * n + steps) / (n + 1)
            m.avg_latency = (m.avg_latency * n + latency) / (n + 1)
            m.avg_user_rating = (m.avg_user_rating * n + user_rating) / (n + 1)
            m.total_runs = n + 1; m.last_used = now
            existing.last_updated = now
            if failure_video: existing.failure_video = failure_video
        else:
            variants.append(PlaybookVariant(
                variant_id=vid, trajectory=trajectory, created_at=now,
                last_updated=now, failure_video=failure_video,
                metrics=Metrics(success_rate=1.0 if success else 0.0,
                                avg_steps=float(steps), avg_latency=latency,
                                avg_user_rating=user_rating, total_runs=1, last_used=now),
            ))

        variants.sort(key=lambda v: (-v.metrics.success_rate, v.metrics.avg_steps))
        variants = variants[:keep_top]
        json.dump({"task": task, "url": url, "updated": now,
                   "variants": [{**asdict(v), "metrics": asdict(v.metrics)} for v in variants]},
                  open(path, "w"), indent=2)
        return vid
```

### 8.2 `sin_browser_tools/tools/learning.py` (Tool-API)

```python
"""Tools for sin-browser-learning: suggest/record/list/compare playbooks."""

from typing import Optional
from sin_browser_tools.playbook import PlaybookStore

_store = PlaybookStore()


async def browser_playbook_suggest(task: str, url: str, limit: int = 3) -> dict:
    variants = _store.load_variants(task, url)
    if not variants:
        return {"status": "not_found", "task": task, "url": url,
                "hint": "No prior playbook. Use the sin-browser-automation skill and record after."}
    return {"status": "ok", "task": task, "url": url,
            "variants": [{"id": v.variant_id, "steps": len(v.trajectory),
                          "success_rate": round(v.metrics.success_rate, 2),
                          "avg_latency": round(v.metrics.avg_latency, 1),
                          "failure_video": v.failure_video,
                          "trajectory": v.trajectory} for v in variants[:limit]]}


async def browser_playbook_record(task: str, url: str, trajectory: list[dict],
                                  success: bool = True, steps: int = 0,
                                  latency: float = 0.0, user_rating: float = 5.0,
                                  failure_video: Optional[str] = None) -> dict:
    vid = _store.save_variant(task, url, trajectory, success, steps, latency,
                              user_rating, failure_video=failure_video)
    return {"status": "ok", "task": task, "url": url, "variant_id": vid,
            "message": "Playbook recorded and ranked"}


async def browser_playbook_list(task_filter: str = "") -> dict:
    import json
    from pathlib import Path
    pb = Path(".sin_playbooks")
    if not pb.exists():
        return {"status": "ok", "playbooks": []}
    out = []
    for task_dir in pb.iterdir():
        if not task_dir.is_dir():
            continue
        name = task_dir.name.replace("_", ":")
        if task_filter and task_filter.lower() not in name.lower():
            continue
        for url_dir in task_dir.iterdir():
            vf = url_dir / "variants.json"
            if vf.exists():
                try:
                    d = json.load(open(vf))
                    out.append({"task": name, "url": d.get("url", "?"),
                                "variant_count": len(d.get("variants", []))})
                except Exception:
                    pass
    return {"status": "ok", "playbooks": out}


async def browser_playbook_compare(task: str, url: str) -> dict:
    variants = _store.load_variants(task, url)
    if not variants:
        return {"status": "not_found"}
    return {"status": "ok", "task": task, "url": url,
            "comparison": [{"variant_id": v.variant_id,
                            "success_rate_pct": round(v.metrics.success_rate * 100, 1),
                            "avg_steps": round(v.metrics.avg_steps, 1),
                            "avg_latency_s": round(v.metrics.avg_latency, 1),
                            "total_runs": v.metrics.total_runs} for v in variants[:3]]}
```

### 8.3 `sin_browser_tools/skills/generator.py` (scaffold + validate)

```python
"""Generate/validate OpenCode skills from proven runs."""

import argparse, sys
from pathlib import Path
from typing import Optional


def generate_skill(name: str, description: str) -> None:
    skills_dir = Path(".opencode/skills"); skills_dir.mkdir(parents=True, exist_ok=True)
    d = skills_dir / name; d.mkdir(exist_ok=True)
    (d / "SKILL.md").write_text(
        "---\nname: {n}\ndescription: |-\n  {desc}\n---\n\n"
        "# {title}\n\nLoop: LOOK -> DECIDE -> ACT -> VERIFY. Refs reset per snapshot.\n\n"
        "## Parameters\n(describe inputs)\n\n## Steps\n(ordered browser_* calls)\n\n"
        "## Success check\n(browser_wait_for_text proof)\n\n"
        "## If stuck\nSee sin-browser-automation/reference/error-recovery.md\n".format(
            n=name, desc=description, title=name.replace("-", " ").title()))
    (d / "reference").mkdir(exist_ok=True)
    print("created {}".format(d))


def validate_skill(name: str) -> bool:
    from sin_browser_tools.tools import catalog
    md = Path(".opencode/skills") / name / "SKILL.md"
    if not md.exists():
        print("missing {}".format(md)); return False
    content = md.read_text()
    if not content.startswith("---"):
        print("missing frontmatter"); return False
    fm_name = None
    for line in content.split("\n")[1:]:
        if line.startswith("---"):
            break
        if line.startswith("name:"):
            fm_name = line.split(":", 1)[1].strip()
    if fm_name != name:
        print("name '{}' != folder '{}'".format(fm_name, name)); return False
    tools = set(catalog.discover())
    for line in content.split("\n"):
        for tok in line.replace("(", " ").split():
            if tok.startswith("browser_") and tok.rstrip("(),.`") not in tools:
                print("unknown tool {}".format(tok)); return False
    print("ok: {} valid".format(name)); return True


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--name"); p.add_argument("--description", default="")
    p.add_argument("--validate"); p.add_argument("--list", action="store_true")
    a = p.parse_args()
    if a.validate:
        sys.exit(0 if validate_skill(a.validate) else 1)
    if a.list:
        sd = Path(".opencode/skills")
        [print(" ", d.name) for d in sorted(sd.iterdir())] if sd.exists() else None
        return
    if a.name:
        generate_skill(a.name, a.description)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
```

---

## 9. Tests

- `tests/test_playbook.py`: save → load roundtrip, ranking (besseres Variant
  zuerst), Metrik-Merge über mehrere Runs, `keep_top`-Trimmen.
- `tests/test_learning_tools.py`: suggest(not_found), record→suggest(ok),
  compare-Sortierung.
- `tests/test_skill_generator.py`: generate erstellt valide Struktur; validate
  erkennt Name-Mismatch und unbekannte Tools.
- `tests/test_screen_record.py`: Nicht-macOS → `unsupported`; Backend-Detection;
  `extract_frames` ohne ffmpeg → `[]`. macOS-Integration `skipif`.
- Smoke: `catalog.discover()` enthält die neuen `browser_playbook_*` +
  `browser_screen_record_*` Tools; Tool-Count-Assertion erhöhen.

---

## 10. GitHub Issue (wird zusätzlich als echtes Issue angelegt)

**Titel:** `feat: OpenCode skills — browser automation, skill-authoring & learning-by-doing (incl. macOS screen-record + vision)`

**Body:** siehe `docs/ISSUE_OPENCODE_SKILLS.md` (Acceptance Criteria,
Implementierungsreihenfolge, Risiken). Verlinkt diesen Plan.

---

## 11. Verkabelung & Rollout

1. `tools/catalog.py`: `TOOL_MODULES += [learning, screen_record]`.
2. `tools/__init__.py`: Re-Export `learning`, `screen_record`.
3. `.gitignore`: `.sin_recordings/`, `.sin_playbooks/`.
4. `pyproject.toml`: optionaler Extra `vision`/`media` (ffmpeg ist System-Tool,
   kein pip-Paket — nur dokumentieren).
5. `.opencode/skills/`: drei Skills + reference/ + templates/.
6. `docs/PERMISSIONS_MACOS.md`: Screen-Recording-Permission + ffmpeg-Install.
7. `AGENTS.md`/`COOKBOOK.md`: Learning-Loop + „bei Fehler aufzeichnen"-Regel.
8. Tests grün (`python -m pytest`), dann commit + push `main`.

## 12. Offene Entscheidungen (für dich)
1. **Recorder-Backend-Default:** ffmpeg (flexibler, Crop/fps) vor `screencapture`
   — ok? (Plan: ja.)
2. **Auto-Record bei Fehler** standardmäßig AN (`SIN_AUTO_RECORD_ON_FAILURE=true`)
   oder opt-in?
3. **Vision-Pipeline:** `tools/vision.py` um `analyze_images(paths, prompt)`
   erweitern (Mehrbild) — oder pro Frame einzeln analysieren? (Plan: Mehrbild,
   Fallback Einzelbild.)
4. Issue zusätzlich zum Plan anlegen? (Du hast „erstelle … issue dazu" gesagt →
   Plan: ja, via `gh`.)

