# AGENTS.md — How to drive SIN-Browser-Tools (read this first)

You are an automation agent. This page is your operating manual. Follow it
literally. Do **not** improvise. If a step says "do X", do exactly X.

---

## 0. The only loop you ever run

Browser automation is **blind without a snapshot**. You can NOT click what you
have not seen. Repeat this loop for every single action:

```
1. LOOK     -> browser_snapshot          (get the page as @e1, @e2, ... refs)
2. DECIDE   -> pick ONE @eN ref to act on
3. ACT      -> browser_click / browser_type / ... using that @eN
4. VERIFY   -> browser_snapshot again, confirm the page changed as expected
```

Never chain two ACT steps without a LOOK in between. The page changes after
every click; old refs (@e3 from a previous snapshot) are **stale and invalid**.

---

## 0.5 Before the loop: is the browser installed?

This library drives a real Chromium browser. It must be installed once. If your
very first tool call fails with *"Executable doesn't exist"* or *"run `playwright
install`"*, the browser binary is missing. Fix it with this shell command (run
ONCE, not per action):

```bash
python -m playwright install chromium
```

This is a one-time machine setup step, not something you do inside the loop.

---

## 1. Golden rules (break these and you will fail)

1. **Always snapshot before you act.** No exceptions.
2. **Only use `@eN` refs from your most recent snapshot.** A snapshot resets all
   refs. `@e5` from two steps ago is garbage now.
3. **You target elements by ref (`@e7`) — not by guessing CSS selectors.**
   The snapshot gives you the refs. Use them.
4. **One action at a time.** Click, then look, then decide. No batching.
5. **If a click does nothing, do NOT repeat it 5 times.** Go to the Error table
   (section 4). The usual fix is `browser_click_cdp` instead of `browser_click`.
6. **Wait for the page, don't race it.** After navigation or a click that loads
   content, call `browser_wait_for_load` or `browser_wait_for_text` before the
   next snapshot.
7. **Read the tool result.** Every tool returns a dict with `ok`/`error`. If
   `ok` is false, STOP and read the `error` string — it tells you what to do.

---

## 2. First three calls of any session

```text
browser_list_tools()                      # see exactly what exists
browser_navigate("https://...")           # go to the start page
browser_snapshot()                        # LOOK — now you have refs
```

That's it. From here you are in the loop from section 0.

---

## 3. Which tool do I use? (decision shortcuts)

| I want to...                          | Use this tool                       |
|---------------------------------------|-------------------------------------|
| See the page / get refs              | `browser_snapshot`                  |
| See a page with cross-origin iframes | `browser_snapshot_full_oopif`       |
| Click a normal button/link          | `browser_click("@e7")`              |
| Click and it didn't work            | `browser_click_cdp("@e7")`          |
| Type into a field                   | `browser_type("@e3", "text")`       |
| Pick a dropdown value               | `browser_select_option("@e4", ...)` |
| Go to a URL                         | `browser_navigate(url)`             |
| Wait for content to appear          | `browser_wait_for_text("Inbox")`    |
| Read visible text                   | `browser_get_text()`                |
| Take a picture (for yourself)       | `browser_screenshot()`              |
| Accept/dismiss a popup              | `browser_dialog("accept")`          |
| A new tab/window opened             | `browser_list_tabs` + `browser_switch_tab` |

When unsure, call `browser_list_tools("keyword")` to search by name.

---

## 4. Error -> Fix table (this is where you go when stuck)

| Symptom                                            | What it means                          | Do this                                                            |
|----------------------------------------------------|----------------------------------------|--------------------------------------------------------------------|
 | `Executable doesn't exist` / `run playwright install`| Chromium browser not installed       | Run once in the shell: `python -m playwright install chromium`     |
 | Click "succeeds" but nothing changes               | Element is inside an OOPIF / overlay   | Retry with `browser_click_cdp("@eN")`                              |
| `ref @eN not found` / `unknown ref`                | You used a stale ref                   | Call `browser_snapshot` again, use a FRESH ref                     |
| Snapshot is missing the email list / iframe content| Content lives in a cross-origin iframe | Use `browser_snapshot_full_oopif()` instead of `browser_snapshot`  |
| Element "not visible" / "not stable"               | Page still loading or element off-screen| `browser_wait_for_load`, then `browser_scroll`, then re-snapshot   |
| Nothing happens after navigate                     | You snapshotted too early              | `browser_wait_for_load("networkidle")` then snapshot               |
| A dialog/alert blocks everything                   | Native JS dialog is open               | `browser_dialog("accept")` or `browser_dialog("dismiss")`          |
| Action target opened a new window                  | Focus is on the old tab                | `browser_list_tabs`, then `browser_switch_tab(index)`              |
| Typing goes nowhere                                | Field not focused                      | `browser_click("@eN")` the field first, then `browser_type`        |

**The single most common fix:** if `browser_click` looks like it worked but the
snapshot didn't change, switch to `browser_click_cdp`. It routes the click into
out-of-process iframes (e.g. GMX / web.de mail lists) correctly.

---

## 5. OOPIF in one paragraph (why your clicks sometimes vanish)

Some sites (GMX, web.de, embedded checkouts, ad frames) put the real content in
a **cross-origin iframe** that runs in a separate browser process ("OOPIF"). A
normal `browser_snapshot` can miss it, and a normal `browser_click` can land on
the wrong layer. The fix is built in: use `browser_snapshot_full_oopif()` to
SEE inside those frames, and `browser_click_cdp("@eN")` to CLICK inside them.
You do not need to understand the internals — just use those two tools when the
Error table tells you to.

---

## 6. A complete, correct example (do it like this)

Task: open the first email in a GMX inbox.

```text
browser_navigate("https://www.gmx.net")
browser_wait_for_load("networkidle")
browser_snapshot_full_oopif()        # mail list lives in an OOPIF
# -> read the tree, find: @e42 "Email from ... – subject ..."
browser_click_cdp("@e42")            # CDP click routes into the OOPIF
browser_wait_for_text("Reply")       # wait for the email view
browser_snapshot_full_oopif()        # VERIFY: the email is now open
```

Notice: snapshot -> pick ref -> act -> wait -> snapshot to verify. Always.

---

## 7. When you are truly stuck

1. `browser_snapshot_full_oopif()` — make sure you actually see everything.
2. `browser_screenshot()` — look at the pixels; maybe an overlay/cookie banner
   is covering the page. If so, close it (find its @eN and click it) first.
3. `browser_get_text()` — confirm what text is really on the page.
4. Re-read the Error table. Pick the matching row. Do exactly what it says.

Do not loop forever. After 3 failed attempts on the same element, change the
strategy (different tool from the table), don't repeat the same call.

See `COOKBOOK.md` for full task recipes.
