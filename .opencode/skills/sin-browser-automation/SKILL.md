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

Never chain two ACT steps without a LOOK. Refs reset on every snapshot.

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

## Golden rules

1. Snapshot before every act. 2. Only refs from the latest snapshot.
3. Target by ref, not guessed CSS. 4. One action at a time.
5. A failed click is NOT repeated 5x — switch to `browser_click_cdp` or consult
   error-recovery. 6. Wait for load/text before snapshotting. 7. Read each tool
   result's `ok`/`error`; on `ok:false`, STOP and act on `error`.
8. If you fail mid-run, `screen_record_analyze` will tell you what went wrong.
