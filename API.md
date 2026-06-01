# API Reference

All tools are exposed over MCP as `browser_<action>` (valid names matching
`^[a-zA-Z0-9_-]{1,64}$`). Call `browser_list_tools` at runtime for the live,
self-describing catalog with parameter schemas.

## Meta
- `browser_list_tools(filter: str = None)` - List every tool with its params

## Accessibility
- `browser_snapshot()` - Accessibility tree with Ref-IDs (main document)
- `browser_snapshot_full_oopif(pierce: bool = True)` - Tree across OOPIFs / Shadow-DOM

## Navigation
- `browser_navigate(url: str)` - Navigate to URL
- `browser_back()` / `browser_forward()` / `browser_reload()` - History controls
- `browser_scroll(direction: str, amount: int)` - Scroll page
- `browser_press(key: str)` - Press a key / combo (e.g. `Control+A`)
- `browser_get_url()` - Current URL + title
- `browser_set_viewport(width: int, height: int)` - Resize viewport
- `browser_wait_for(selector, state, timeout)` - Wait for selector state
- `browser_wait_for_text(text, timeout)` - Wait for text to appear
- `browser_wait_for_load(state, timeout)` - Wait for a load state

## Tabs
- `browser_list_tabs()` - List open tabs
- `browser_new_tab(url: str = None)` - Open (and optionally navigate) a tab
- `browser_switch_tab(index: int)` - Switch active tab
- `browser_close_tab(index: int = None)` - Close a tab (defaults to active)

## Interaction
- `browser_click(target: str)` - Click (@eN or selector; auto CDP for OOPIF)
- `browser_click_cdp(target: str)` - Force a native CDP click
- `browser_click_by_text(text: str, exact: bool)` - Click by visible text (selector fallback)
- `browser_double_click(target)` / `browser_right_click(target)` - Click variants
- `browser_hover(target)` - Hover an element
- `browser_drag(source, target)` - Drag and drop
- `browser_select_option(target, value, label)` - Select a `<select>` option
- `browser_check(target, checked: bool)` - Check / uncheck a control
- `browser_click_checkbox_by_text(label_text, exact, frame_name, frame_url)` - Click a checkbox by its visible label, pierces shadow DOM, SPA-safe (Issue #21)
- `browser_type(target, text, clear: bool)` - Type text
- `browser_fill(target, value)` - Clear + fill an input
- `browser_upload_file(target, file_path)` - Upload a file
- `browser_find_by_text(text: str, exact: bool)` - Find elements by visible text (returns @eN refs)

## Vision
- `browser_vision(full_page: bool)` / `browser_screenshot(full_page: bool)` - Page screenshot (Base64 PNG)
- `browser_screenshot_element(selector: str)` - Screenshot one element
- `browser_pdf(landscape, print_background)` - Render page to PDF (headless only)
- `browser_get_images()` - List all images
- `browser_get_text(selector: str)` - Extract visible text

## Extraction
- `browser_console(expression: str)` - Evaluate JavaScript
- `browser_cdp(method: str, params: dict)` - Send a raw CDP command
- `browser_get_html(selector, max_length)` - Raw HTML (page or element)
- `browser_get_links()` - All hyperlinks (text, href, visibility)
- `browser_get_attribute(selector, name)` - Read an attribute
- `browser_storage(area, action, key, value)` - Read/write local/session storage
- `browser_get_cookies(url)` / `browser_set_cookie(...)` / `browser_clear_cookies()` - Cookies

## Dialog
- `browser_dialog(action: str, prompt_text: str)` - Handle a JS dialog
- `browser_wait_for_dialog(timeout: float)` - Wait for a dialog

## Frames (Issue #11, #12, #15)
- `browser_list_frames()` - List all frames (main, OOPIFs, same-process)
- `browser_eval_in_frame(expr: str, frame_name: str, frame_url: str)` - Run JS in specific frame
- `browser_snapshot_in_frame(frame_name, frame_url, selector, pierce_shadow)` - Walk frame DOM, pierce open shadow roots
- `browser_click_in_frame(selector, frame_name, frame_url, index, text)` - Click a (shadow-DOM) element inside one frame, e.g. GMX/web.de mail rows (Issue #12)
- `browser_scan_frames(pattern, regex, include_empty)` - Scan ALL frames for text content (unnamed iframe support)

See README for usage examples.
