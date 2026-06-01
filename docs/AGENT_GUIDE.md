# SIN-Browser-Tools: Agent Guide & Best Practices

Comprehensive guide for AI agents using SIN-Browser-Tools.

## Current Tool Inventory (75+ tools)

### Navigation & Pages
| Tool | Purpose |
|------|---------|
| `browser_navigate` | Go to URL |
| `browser_back/forward/reload` | History navigation |
| `browser_get_url` | Current URL + title |
| `browser_scroll` | Scroll by pixels |
| `browser_press` | Keyboard input (Enter, Escape, etc.) |
| `browser_set_viewport` | Resize viewport |

### Tab Management
| Tool | Purpose |
|------|---------|
| `browser_list_tabs` | List all tabs with index, URL, title |
| `browser_new_tab` | Open new tab (optionally navigate) |
| `browser_switch_tab` | Switch to tab by index |
| `browser_close_tab` | Close tab (defaults to active) |

### Window Control (NEW - Issue #27)
| Tool | Purpose |
|------|---------|
| `browser_get_window_bounds` | Read position/size/state |
| `browser_set_window_bounds` | Set exact pixel bounds |
| `browser_set_window_mode` | Presets: small/medium/large/maximized/fullscreen |
| `browser_maximize/minimize/fullscreen/restore_window` | State control |
| `browser_move_window` | Position on screen |

### macOS Spaces (NEW - Issue #27)
| Tool | Purpose |
|------|---------|
| `browser_list_spaces` | List virtual desktops |
| `browser_create_space` | Create new Space |
| `browser_move_to_space` | Move browser to Space (1-based) |
| `browser_get_window_space` | Query current Space |
| `browser_send_to_background_space` | Auto-background mode |

### Interaction
| Tool | Purpose |
|------|---------|
| `browser_click` | Click by selector |
| `browser_click_by_text` | Click by visible text |
| `browser_click_checkbox_react` | Toggle React checkboxes |
| `browser_double_click` | Double-click |
| `browser_right_click` | Context menu |
| `browser_hover` | Hover over element |
| `browser_drag` | Drag and drop |
| `browser_fill` | Fill input field |
| `browser_fill_react` | Fill React controlled inputs |
| `browser_type` | Type character by character |
| `browser_select_option` | Select dropdown option |
| `browser_upload_file` | File upload |

### Waiting (SPA-safe)
| Tool | Purpose |
|------|---------|
| `browser_wait_for` | Wait for selector state |
| `browser_wait_for_text` | Wait for text (Shadow DOM support!) |
| `browser_wait_for_load` | Wait for load state |
| `browser_wait_for_spa_transition` | MutationObserver-based DOM waiter |
| `browser_wait_for_dialog` | Wait for alert/confirm/prompt |

### Extraction & Vision
| Tool | Purpose |
|------|---------|
| `browser_snapshot` | Accessibility tree (recommended!) |
| `browser_snapshot_full_oopif` | Deep snapshot across all frames |
| `browser_screenshot` | Full page screenshot |
| `browser_screenshot_element` | Element screenshot |
| `browser_vision` | Vision model analysis |
| `browser_get_text` | Extract text content |
| `browser_get_html` | Get HTML |
| `browser_get_links` | Extract all links |
| `browser_get_images` | Extract all images |
| `browser_get_attribute` | Get element attribute |

### Frames & iframes
| Tool | Purpose |
|------|---------|
| `browser_list_frames` | List all frames |
| `browser_scan_frames` | Deep frame scan |
| `browser_click_in_frame` | Click inside iframe |
| `browser_eval_in_frame` | Execute JS in frame |
| `browser_snapshot_in_frame` | Snapshot specific frame |

### Cookies & Storage
| Tool | Purpose |
|------|---------|
| `browser_get_cookies` | Get all cookies |
| `browser_set_cookie` | Set a cookie |
| `browser_clear_cookies` | Clear cookies |
| `browser_storage` | localStorage/sessionStorage |

### Dialog Handling
| Tool | Purpose |
|------|---------|
| `browser_dialog` | Handle alert/confirm/prompt |
| `browser_wait_for_dialog` | Wait for dialog to appear |

### Recording & Learning
| Tool | Purpose |
|------|---------|
| `browser_playbook_record` | Record interactions |
| `browser_playbook_list` | List recorded playbooks |
| `browser_playbook_compare` | Compare recordings |
| `browser_playbook_suggest` | Get suggestions |
| `browser_screen_record_start/stop/analyze` | Video recording |

### Low-Level
| Tool | Purpose |
|------|---------|
| `browser_cdp` | Raw CDP command |
| `browser_console` | Console messages |
| `browser_eval_in_frame` | Execute JavaScript |
| `browser_pdf` | Export as PDF |

---

## What's Missing? Gap Analysis

### 1. Parallel Sessions / Multi-Context (Priority: HIGH)

**Current state:** Single BrowserContext, single active page  
**Missing:**
- `browser_create_context` - Create isolated browser context
- `browser_list_contexts` - List all contexts
- `browser_switch_context` - Switch active context
- `browser_close_context` - Close context and all its pages
- `browser_run_parallel` - Run actions in parallel across contexts

**Why important:** AI agents often need to:
- Compare two versions of a page side-by-side
- Run parallel searches
- Maintain logged-in and logged-out sessions
- A/B testing scenarios

**Implementation hint (from browser-use):**
```python
# Each context = isolated session (cookies, storage, etc.)
context1 = await browser.new_context()
context2 = await browser.new_context()  # Completely isolated!
```

### 2. Network Interception Tools (Priority: MEDIUM)

**Current state:** `NetworkInterceptor` class exists but not exposed as tools  
**Missing MCP tools:**
- `browser_intercept_start` - Start intercepting URLs matching pattern
- `browser_intercept_stop` - Stop interception
- `browser_intercept_get` - Get intercepted responses
- `browser_intercept_wait` - Wait for specific API response
- `browser_mock_response` - Mock API responses

**Why important:** Modern SPAs load data via XHR/Fetch. Intercepting is 100x more reliable than DOM parsing.

### 3. Stealth / Anti-Detection (Priority: MEDIUM)

**Current state:** Basic Playwright  
**Missing:**
- `browser_set_stealth_mode` - Enable stealth patches
- `browser_rotate_proxy` - Change proxy
- `browser_randomize_fingerprint` - Randomize canvas/WebGL/etc.

**Why important:** Production agents fail on sites with bot detection.

### 4. Persistent Sessions (Priority: MEDIUM)

**Current state:** Sessions lost on restart  
**Missing:**
- `browser_save_session` - Save cookies/storage to file
- `browser_load_session` - Restore session from file
- `browser_export_profile` - Export full browser profile
- `browser_import_profile` - Import browser profile

### 5. Batch/Bulk Operations (Priority: LOW)

**Missing:**
- `browser_click_all` - Click all matching elements
- `browser_fill_form` - Fill entire form from dict
- `browser_extract_table` - Extract table as structured data

### 6. Observability (Priority: LOW)

**Current state:** Basic logging  
**Missing:**
- `browser_trace_start` - Start Playwright trace
- `browser_trace_stop` - Stop and save trace
- `browser_har_export` - Export HAR file

---

## Best Practices for Agents

### 1. Use Accessibility Trees, Not Screenshots

```python
# GOOD - Fast, structured, reliable
snapshot = await browser_snapshot()

# AVOID - Slow, expensive, error-prone
screenshot = await browser_screenshot()
result = await vision_model.analyze(screenshot)
```

**Exception:** Use vision only when content requires visual interpretation (charts, images, CAPTCHAs).

### 2. Wait for Content, Don't Sleep

```python
# BAD - Wastes time or races
await asyncio.sleep(3)

# GOOD - Precise waiting
await browser_wait_for_text("Step 2: Confirm")
await browser_wait_for_spa_transition("Welcome back")
await browser_wait_for("#submit-button", state="visible")
```

### 3. Use Network Interception for Data Extraction

```python
# BAD - Fragile DOM parsing
emails = await browser_get_text(".email-list .subject")

# GOOD - Intercept the API response
interceptor = NetworkInterceptor(page)
interceptor.add_pattern("/api/messages")
await interceptor.start()
await browser_click("Refresh")
data = await interceptor.wait_for_pattern("/api/messages")
```

### 4. Handle Popups and Dialogs Proactively

```python
# Set up dialog handler BEFORE triggering action
await browser_dialog(action="accept")  # Pre-configure
await browser_click("Delete")  # Triggers confirm dialog
```

### 5. Use Atomic Operations with Retry

```python
# Wrap critical operations
async def click_with_retry(selector, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            await browser_click(selector)
            return
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            await browser_wait_for(selector, timeout=2000)
```

### 6. Isolate Sessions for Different Users/Contexts

```python
# When parallel contexts are available:
admin_ctx = await browser_create_context(name="admin")
user_ctx = await browser_create_context(name="user")

# Admin actions
await browser_switch_context("admin")
await browser_navigate("/admin/dashboard")

# User actions (isolated cookies, storage)
await browser_switch_context("user")
await browser_navigate("/user/profile")
```

### 7. Use Element References (@eN)

The snapshot tools return element references like `@e15`. Use them for reliable targeting:

```python
snapshot = await browser_snapshot()
# Snapshot shows: [button @e15] "Submit"

await browser_click("@e15")  # Precise, won't match wrong element
```

### 8. Background the Browser on macOS

```python
# Move browser to background Space so user isn't disturbed
await browser_send_to_background_space()

# ... do automation ...

# Optionally bring back
await browser_move_to_space(1)
```

### 9. Structure Your Agent Flow

```
1. NAVIGATE → Go to URL
2. WAIT → For page to stabilize (wait_for_load, wait_for_text)
3. SNAPSHOT → Get accessibility tree
4. PLAN → Decide next action based on snapshot
5. ACT → Click, fill, etc.
6. VERIFY → Snapshot again to confirm result
7. REPEAT or COMPLETE
```

### 10. Error Recovery Patterns

```python
async def resilient_login(email, password):
    # Navigate with retry
    for _ in range(3):
        try:
            await browser_navigate("https://app.example.com/login")
            await browser_wait_for_text("Sign in", timeout=10000)
            break
        except:
            await browser_reload()
    
    # Fill with SPA-awareness
    await browser_fill_react("#email", email)
    await browser_fill_react("#password", password)
    
    # Click and wait for result
    await browser_click("Sign in")
    
    # Verify success OR handle error
    result = await browser_wait_for_text("Dashboard", timeout=15000)
    if not result["found"]:
        error = await browser_wait_for_text("Invalid credentials", timeout=1000)
        if error["found"]:
            raise LoginError("Invalid credentials")
        raise LoginError("Unknown login failure")
```

---

## Tool Selection Decision Tree

```
Need to see page content?
├── Structured data → browser_snapshot (fast, reliable)
├── Visual layout → browser_screenshot + vision
└── Specific text → browser_get_text

Need to wait?
├── For element → browser_wait_for(selector)
├── For text → browser_wait_for_text(text)
├── For SPA update → browser_wait_for_spa_transition
├── For network → browser_wait_for_load("networkidle")
└── For dialog → browser_wait_for_dialog

Need to interact?
├── Click button → browser_click or browser_click_by_text
├── Fill input → browser_fill (or browser_fill_react for React)
├── Select dropdown → browser_select_option
├── Upload file → browser_upload_file
├── Keyboard → browser_press

Need data extraction?
├── From DOM → browser_get_text, browser_get_links, browser_get_html
├── From API → NetworkInterceptor pattern
└── From table → Extract and parse manually (or future browser_extract_table)

Need multiple tabs?
├── Open → browser_new_tab
├── Switch → browser_switch_tab
├── Close → browser_close_tab
└── List → browser_list_tabs

Need window control?
├── Resize → browser_set_window_mode or browser_set_window_bounds
├── Minimize → browser_minimize_window
├── Fullscreen → browser_fullscreen_window
└── Background (macOS) → browser_send_to_background_space
```

---

## Environment Variables Reference

```bash
# Browser mode
SIN_HEADLESS=false          # true for headless, false for visible window

# Window (headful only)
SIN_WINDOW_MODE=medium      # small|medium|large|maximized|fullscreen
SIN_WINDOW_WIDTH=1280       # Custom width
SIN_WINDOW_HEIGHT=800       # Custom height

# macOS Spaces
SIN_SPACE_BACKEND=auto      # auto|yabai|hammerspoon|applescript

# Timeouts
SIN_DEFAULT_TIMEOUT=30000   # Default timeout in ms

# Debug
SIN_DEBUG=true              # Enable debug logging
```
