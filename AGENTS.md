# AGENTS.md — SIN-Browser-Tools Agent Reference

> **v0.3.0+**: 96 MCP tools, unified `{"ok": true/false, ...}` contract, Evidence Layer with CDP.

## Return Contract (Unified)

**Every tool returns** (or throws):
```json
{
  "ok": true,                    // ← boolean success flag (NEW in v0.3.0)
  "status": "clicked",           // original semantic status (preserved)
  "result": "...",               // ← tool-specific data
  "error": "...",                // ← error message if ok=false
  "tool": "browser_click"        // ← which tool
}
```

**Decision tree:**
- `ok: true` → proceed (status describes *what happened*, not success)
- `ok: false` → error state (check `error` field for details)

Example:
```
browser_click(...) -> {"ok":true, "status":"clicked", "ref":"@e7"}
browser_wait_for_text("Not There") -> {"ok":false, "error":"timeout after 5s"}
```

---

## Evidence & Debugging (NEW)

### Start Recording Evidence
```
browser_diag_start(label="my_session")
# -> {"status":"started", "session": {"dir": ".sin_evidence/...", ...}}
```

### Wrap Actions with Before/After Proof
```
browser_diag_action(action="click_login", tool="browser_click", args={"ref":"@e42"}, ref="@e42")
# -> {"ok":true, "step_id":"s0001", "before":{"screenshot":"...png", "element":{...}}, "after":{...}}
```

### Query Correlated Events
```
browser_diag_query(step_id="s0001", domain="network", contains="api/login")
# -> {"events": [...], "count":3, "failures":1}
```

### Generate Report
```
browser_diag_stop(generate_report_after=True)
browser_diag_report() -> {"report_md": "...", "report_html": "..."}
```

See `docs/DIAGNOSTICS.md` for full Evidence API (11 tools, 100+ options).

---

## Core Tools by Category

### Navigation & Waits (9 tools)
| Tool | Args | Returns |
|---|---|---|
| `browser_navigate(url)` | `url` | `{"ok":true, "status":"navigated"}` |
| `browser_wait_for_load(state)` | `state` ∈ `load\|domcontentloaded\|networkidle` | `{"ok":true, "loaded_at_ms":1234}` |
| `browser_wait_for_text(text, timeout)` | `text`, `timeout` (s) | `{"ok":true, "found":true, "element":"@e7"}` |
| `browser_wait_for_response(url, timeout)` | `url` regex, `timeout` | `{"ok":true, "status":200, "body":"..."}` |
| `browser_wait_for_request(url, timeout)` | `url` regex, `timeout` | `{"ok":true, "request":{"method":"POST", ...}}` |
| `browser_wait_for_element(selector, timeout)` | CSS/XPath, `timeout` | `{"ok":true, "ref":"@e42"}` |
| `browser_reload()` | — | `{"ok":true, "status":"reloaded"}` |
| `browser_go_back()` | — | `{"ok":true, "navigated":true}` |
| `browser_go_forward()` | — | `{"ok":true, "navigated":true}` |

### Interaction (20+ tools)
| Tool | Args | Returns |
|---|---|---|
| `browser_click(ref)` | `ref` ("@eN") | `{"ok":true, "status":"clicked"}` |
| `browser_type(ref, text, delay_ms)` | `ref`, `text`, `delay_ms` | `{"ok":true, "chars_typed":5}` |
| `browser_fill(ref, text)` | `ref`, `text` | `{"ok":true, "filled":true}` |
| `browser_select(ref, option)` | `ref`, `option` label or value | `{"ok":true, "selected":"Option A"}` |
| `browser_check(ref)` / `uncheck(ref)` | `ref` | `{"ok":true, "checked":true}` |
| `browser_upload_file(ref, file_path)` | `ref`, path | `{"ok":true, "uploaded":true}` |
| `browser_download(expect_filename)` | `expect_filename` regex (opt) | `{"ok":true, "filename":"data.csv", "path":"/tmp/..."}` |
| `browser_double_click(ref)` | `ref` | `{"ok":true, "status":"double_clicked"}` |
| `browser_right_click(ref)` | `ref` | `{"ok":true, "context_menu":true}` |
| `browser_hover(ref, duration_ms)` | `ref`, `duration_ms` (opt) | `{"ok":true, "hovered":true}` |
| `browser_drag_and_drop(source_ref, target_ref)` | source, target | `{"ok":true, "dropped":true}` |
| `browser_press(key)` | `key` (Tab, Enter, Escape, etc.) | `{"ok":true, "key":"Enter"}` |
| `browser_accept_dialog()` | — | `{"ok":true, "message":"..."}` |
| `browser_dismiss_dialog()` | — | `{"ok":true, "dismissed":true}` |

### Snapshots & Content (8 tools)
| Tool | Args | Returns |
|---|---|---|
| `browser_snapshot()` | — | `{"ok":true, "tree":"@e1 Button...", "count":42}` |
| `browser_snapshot_full_oopif()` | — | `{"ok":true, "tree":"...", "oopif_count":2}` |
| `browser_screenshot(filename)` | `filename` (opt) | `{"ok":true, "saved":"/path/screenshot.png"}` |
| `browser_get_text(ref)` | `ref` (opt, default all) | `{"ok":true, "text":"Hello World"}` |
| `browser_get_links()` | — | `{"ok":true, "links":[{"href":"...", "text":"..."}]}` |
| `browser_get_attribute(ref, attr)` | `ref`, `attr` | `{"ok":true, "value":"xyz"}` |
| `browser_get_cookies()` | — | `{"ok":true, "cookies":[{"name":"...", "value":"..."}]}` |
| `browser_get_html(selector)` | `selector` (opt) | `{"ok":true, "html":"<div>..."}` |

### Assertions (5 tools) — NEW
| Tool | Args | Returns |
|---|---|---|
| `browser_assert_url(pattern)` | URL regex | `{"ok":true, "url":"https://...", "matched":true}` |
| `browser_assert_contains(text)` | substring | `{"ok":false, "error":"text not found"}` |
| `browser_assert_title_matches(regex)` | title regex | `{"ok":true, "title":"Login"}` |
| `browser_assert_element_visible(ref)` | `ref` | `{"ok":true, "visible":true}` |
| `browser_assert_count(selector, count)` | CSS, count | `{"ok":true, "found":5, "expected":5, "matched":true}` |

### Extraction (2 tools) — NEW
| Tool | Args | Returns |
|---|---|---|
| `browser_extract(prompt, schema)` | `prompt` (instructions), `schema` (JSONSchema) | `{"ok":true, "data":{...}, "raw":"..."}` |
| `browser_extract_list(item_selector, schema)` | CSS selector, schema | `{"ok":true, "items":[...], "count":5}` |

### CAPTCHA & Bot Detection (2 tools) — NEW
| Tool | Args | Returns |
|---|---|---|
| `browser_detect_captcha()` | — | `{"ok":true, "found":true, "type":"recaptcha_v3"}` |
| `browser_bypass_cloudflare(timeout)` | `timeout` (s, default 30) | `{"ok":true, "bypassed":true, "waited_ms":2345}` |

### Cookies & Identity (3 tools) — NEW
| Tool | Args | Returns |
|---|---|---|
| `browser_set_cookie(name, value, domain, expires)` | all (name required) | `{"ok":true, "set":true}` |
| `browser_delete_cookie(name, domain)` | `name`, `domain` (opt) | `{"ok":true, "deleted":true, "count":1}` |
| `browser_set_identity(user_agent, locale, timezone)` | all optional | `{"ok":true, "set":{"ua":"...", "locale":"de-DE", "tz":"Europe/Berlin"}}` |

### Network Control (3 tools) — NEW
| Tool | Args | Returns |
|---|---|---|
| `browser_network_offline(offline)` | boolean | `{"ok":true, "offline":true}` |
| `browser_throttle(download_mbps, upload_mbps, latency_ms)` | all (default: 4G) | `{"ok":true, "throttled":true}` |
| `browser_block_urls(patterns)` | list of regex | `{"ok":true, "blocked_patterns":3}` |

### Storage & Sessions (6 tools)
| Tool | Args | Returns |
|---|---|---|
| `browser_get_storage(key)` | `key` | `{"ok":true, "value":"..."}` |
| `browser_set_storage(key, value)` | `key`, `value` | `{"ok":true, "set":true}` |
| `browser_clear_storage()` | — | `{"ok":true, "cleared":true}` |
| `browser_save_session(label)` | `label` | `{"ok":true, "file":"/tmp/session.json"}` |
| `browser_restore_session(label_or_path)` | `label` or path | `{"ok":true, "restored":true}` |
| `browser_list_sessions()` | — | `{"ok":true, "sessions":[...], "count":3}` |

### Frames & Windows (6 tools)
| Tool | Args | Returns |
|---|---|---|
| `browser_list_frames()` | — | `{"ok":true, "frames":[{"name":"...", "url":"..."}]}` |
| `browser_scan_frames(pattern, regex)` | text pattern OR regex | `{"ok":true, "matching_frames":1, "frames":[...]}` |
| `browser_list_windows()` | — | `{"ok":true, "windows":[{"id":"...", "title":"..."}]}` |
| `browser_switch_window(id)` | window `id` | `{"ok":true, "switched":true}` |
| `browser_close_window(id)` | window `id` (opt, closes current) | `{"ok":true, "closed":true}` |
| `browser_screenshot_in_frame(frame_name, selector, pierce_shadow)` | frame name, selector, bool | `{"ok":true, "saved":"...png"}` |

### Accessibility & Advanced (10+ tools)
| Tool | Args | Returns |
|---|---|---|
| `browser_snapshot_accessibility()` | — | `{"ok":true, "tree":"Role Tree..."}` |
| `browser_find_by_role(role, name)` | `role` (button, link, etc.), `name` (opt) | `{"ok":true, "ref":"@e7", "label":"..."}` |
| `browser_find_by_label(label)` | label text | `{"ok":true, "input_ref":"@e42"}` |
| `browser_find_by_placeholder(text)` | placeholder | `{"ok":true, "ref":"@e99"}` |
| `browser_find_by_alt_text(alt)` | alt text | `{"ok":true, "image_ref":"@e15"}` |
| `browser_cdp(method, params)` | raw CDP method + params (JSON) | raw CDP result |
| `browser_execute_script(js_code)` | JavaScript string | `{"ok":true, "result":"..."}` |
| `browser_inject_css(selector, css)` | CSS selector, CSS rules | `{"ok":true, "injected":true}` |
| `browser_wait_for_function(js_code, timeout)` | JS that returns boolean | `{"ok":true, "result":true, "waited_ms":234}` |

---

## Common Patterns

### Login Flow with Evidence
```
browser_diag_start(label="login_attempt")
browser_navigate("https://app.example/login")
browser_diag_action("fill_email", "browser_fill", {"ref":"@e1", "text":"user@example.com"}, ref="@e1")
browser_diag_action("fill_password", "browser_fill", {"ref":"@e2", "text":"secret"}, ref="@e2")
browser_diag_action("click_submit", "browser_click", {"ref":"@e3"}, ref="@e3")
browser_diag_query(step_id="s0002", domain="network", contains="login")
browser_diag_stop(generate_report_after=True)
```

### Extract Structured Data
```
browser_navigate("https://example.com/products")
browser_wait_for_load("networkidle")
schema = {
  "type": "object",
  "properties": {
    "products": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "price": {"type": "number"},
          "in_stock": {"type": "boolean"}
        }
      }
    }
  }
}
browser_extract(prompt="Extract all products", schema=schema)
```

### Handle CAPTCHAs
```
browser_detect_captcha()  # -> {"ok":true, "found":true, "type":"recaptcha_v3"}
if "recaptcha" in result.get("type", ""):
    # Manual solve required, or use third-party service
    browser_wait_for_text("Success", timeout=60)  # wait for human
```

### Network Simulation
```
browser_throttle(download_mbps=4, upload_mbps=1, latency_ms=50)  # 4G
browser_navigate("https://slow-site.example")
browser_screenshot()  # see how it renders on slow connection
browser_throttle(download_mbps=100, upload_mbps=100, latency_ms=0)  # reset
```

---

## Error Handling (Decision Tree)

| Situation | Solution |
|---|---|
| Element not found (`ok:false, error:"timeout"`) | Use `browser_snapshot()` to see current page, re-find the ref |
| Text not visible (hidden, in shadow DOM) | Try `browser_snapshot_full_oopif()`, then `browser_scan_frames()` |
| Click didn't work (overlay?) | `browser_screenshot()` to see what's covering it; close overlay first |
| Network request failed | `browser_diag_query(domain="network", only_failures=True)` to see errors |
| CAPTCHA appeared | `browser_detect_captcha()` + manual/3rd-party solve + `browser_wait_for_load()` |
| Page stuck / not responding | `browser_wait_for_load("networkidle", timeout=30)` then `browser_screenshot()` |

---

## Configuration & Startup

**Environment Variables:**
```bash
HEADLESS=1                      # run headless (default: true)
PROXY_URL=http://proxy:8080     # route traffic via proxy
STEALTH=1                       # enable anti-bot stealth mode
```

**Manager Defaults (configurable):**
```python
manager.user_agent = "Mozilla/5.0 ... Chrome/120"  # set before context creation
manager.locale = "de-DE"                           # locale for context
manager.timezone = "Europe/Berlin"                 # timezone for context
```

See `docs/code/` for per-module API docs and pitfalls.
