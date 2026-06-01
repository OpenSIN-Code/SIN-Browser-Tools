# COOKBOOK.md — Copy-paste recipes for agents

Each recipe is a full, ordered sequence. Run the steps top to bottom. Replace
`@eN` with the real ref you read from the snapshot directly before. Read
`AGENTS.md` first — these recipes assume the LOOK -> DECIDE -> ACT -> VERIFY loop.

Legend: lines starting with `#` are notes, not tool calls.

---

## Recipe 1 — Log in to a website

```text
browser_navigate("https://example.com/login")
browser_wait_for_load("networkidle")
browser_snapshot
# find the username field, e.g. @e3 "textbox Email"
browser_type("@e3", "user@example.com")
browser_snapshot
# find the password field, e.g. @e4 "textbox Password"
browser_type("@e4", "hunter2")
browser_snapshot
# find the submit button, e.g. @e5 "button Sign in"
browser_click("@e5")
browser_wait_for_text("Dashboard")     # proof the login worked
browser_snapshot                        # VERIFY you are logged in
```

If `browser_click("@e5")` does nothing: retry with `browser_click_cdp("@e5")`.

---

## Recipe 2 — Read an email in a webmail OOPIF (GMX / web.de)

The mail list is a cross-origin iframe. Normal snapshot/click can miss it.

```text
browser_navigate("https://www.gmx.net")
browser_wait_for_load("networkidle")
# handle the cookie/consent wall if present:
browser_snapshot
# click the consent button BY TEXT — no need to eyeball/parse a ref:
browser_click_by_text("Accept all")
browser_wait_for_load("networkidle")
# now log in (see Recipe 1) ...
# then OPEN the inbox content — use the OOPIF-aware snapshot:
browser_snapshot_full_oopif
# find the message by subject text instead of regex-matching the snapshot:
browser_find_by_text("Your statement")   # -> {"matches": [{"ref": "@e44", ...}]}
browser_click("@e44")                     # auto-routes through the OOPIF-safe path
browser_wait_for_text("Reply")
browser_snapshot_full_oopif               # VERIFY: message body is visible
browser_get_text                          # read the email content
```

Key point: webmail = `browser_snapshot_full_oopif` + click by text/ref.

> Prefer `browser_find_by_text` / `browser_click_by_text` over hand-rolled
> regex against the snapshot string. The snapshot **text** format can change
> (role names, quoting, `(unlabeled)`, OOPIF prefixes); these helpers query the
> structured ref registry directly and are stable.

---

## Recipe 3 — Search and click a result

```text
browser_navigate("https://duckduckgo.com")
browser_wait_for_load("networkidle")
browser_snapshot
# search box, e.g. @e1 "searchbox"
browser_type("@e1", "vercel sandbox docs")
browser_press("Enter")
browser_wait_for_load("networkidle")
browser_snapshot
# first result link, e.g. @e9 "link Vercel Sandbox"
browser_click("@e9")
browser_wait_for_load("networkidle")
browser_snapshot                        # VERIFY you are on the result page
```

---

## Recipe 4 — Fill and submit a multi-field form

```text
browser_snapshot
browser_type("@e3", "Jane")             # First name
browser_type("@e4", "Doe")              # Last name
browser_select_option("@e5", label="Germany")   # Country dropdown
browser_check("@e6", checked=True)      # Accept terms checkbox
browser_snapshot                        # re-look before submitting
browser_click("@e7")                    # Submit
browser_wait_for_text("Thank you")
browser_snapshot
```

After EACH field, the page may re-render. If a later ref fails, snapshot again.

---

## Recipe 5 — Handle a popup / JavaScript dialog

```text
# You clicked something and a native alert/confirm appeared.
browser_wait_for_dialog(timeout=5)
browser_dialog("accept")                # or "dismiss"
browser_snapshot
```

---

## Recipe 6 — A click opened a new tab

```text
browser_click("@e12")                   # link with target=_blank
browser_list_tabs                       # see all open tabs + their index
browser_switch_tab(1)                   # focus the new tab
browser_wait_for_load("networkidle")
browser_snapshot                        # refs now refer to the new tab
```

---

## Recipe 7 — Content is below the fold

```text
browser_snapshot
# the element you need isn't in the tree yet
browser_scroll(direction="down", amount=800)
browser_snapshot                        # now the element appears as a fresh ref
browser_click("@e21")
```

---

## Recipe 8 — Extract structured data from a page

```text
browser_navigate("https://example.com/pricing")
browser_wait_for_load("networkidle")
browser_get_text                        # all visible text
browser_get_links                       # every link + href
browser_get_html(selector=".pricing")   # raw HTML of one region
```

---

## Recipe 9 — Read an email body in an unnamed iframe (Issue #15)

Some webmail sites (GMX, web.de) render the email body in an unnamed `about:blank`
iframe that neither the normal snapshot nor URL-based targeting can access.
Use `browser_scan_frames` to find and extract content from all frames.

```text
# After clicking an email, you need to extract the body content.
# The snapshot shows the mail list, but the body is in a hidden frame.
browser_scan_frames(pattern="Your OTP code")
# Output: {"matching_frames": 1, "frames": [{"index": 2, "text": "... Your OTP code is: 123456 ..."}]}
browser_eval_in_frame("document.body.innerText", frame_name="email-body")
# or, for structured extraction:
browser_scan_frames(regex=r"\d{6}")  # find 6-digit codes in any frame
```

If the frame has no name (unnamed `<iframe>`), `browser_scan_frames` is your only option.

---

## Recipe 10 — Pierce shadow DOM in a same-process iframe (Issue #11)

Pages like the GMX mail list render emails as custom elements (`<list-mail-item>`)
inside open shadow DOM. A normal snapshot cannot see them. Use `browser_snapshot_in_frame`
with `pierce_shadow=True`.

```text
browser_snapshot_full_oopif             # see all frames
# Find the mail frame by its name or URL substring:
browser_snapshot_in_frame(frame_name="mail", selector="list-mail-item")
# Output: {"count": 3, "items": [{"text": "Invoice 2026-01"}, ...]}
browser_snapshot_in_frame(frame_url="webmailer.gmx.net", selector=".subject")
# With pierce_shadow=True (default), subjects inside shadow roots are readable.
```

---

## Anti-patterns (do NOT do these)

- Acting twice in a row without a snapshot between them.
- Reusing an `@eN` ref after the page changed.
- Repeating the exact same failed click more than twice — switch tools instead.
- Guessing CSS selectors when you already have refs from a snapshot.
- Calling `browser_snapshot` on a webmail/iframe page and giving up when the
  content is missing — use `browser_snapshot_full_oopif`.
- Snapshotting immediately after `browser_navigate` without `browser_wait_for_load`.
```
