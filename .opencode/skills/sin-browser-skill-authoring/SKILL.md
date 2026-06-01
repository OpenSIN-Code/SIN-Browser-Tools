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
     --description "Log into GMX and return the latest 6-digit OTP from the newest email."
   ```
   This writes `.opencode/skills/<name>/SKILL.md` with default skeleton.
5. **Validate**: `python -m sin_browser_tools.skills.generator --validate <name>`
   checks frontmatter, name==folder, and that every referenced tool exists in
   the catalog.

## SKILL.md template

See the `sin-browser-automation` skill. The body MUST: state the loop reminder,
the ordered steps with the correct tool per step, parameters, success check
(a `browser_wait_for_text` proof), and an error-recovery pointer.

## Rules

- Never bake real credentials into a skill. Reference the session vault
  (`browser_*` cookie/storage tools) or a `{{secret_ref}}`.
- Every step names the exact `browser_*` tool. No vague "click around".
- End with a VERIFY step that proves success.
- If the flow failed on a previous attempt, use `playbook_suggest(task, url)`
  to see if a better trajectory already exists.
