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

See `reference/screen-record.md` and `sin-browser-automation`'s error-recovery.
