# API Reference

All 18 tools with signatures and examples.

## Accessibility
- `browser_snapshot()` - Returns accessibility tree with Ref-IDs

## Navigation
- `browser_navigate(url: str)` - Navigate to URL
- `browser_back()` - Go back in history
- `browser_scroll(direction: str, amount: int)` - Scroll page
- `browser_press(key: str)` - Press keyboard key

## Interaction
- `browser_click(target: str)` - Click element (@eN or selector)
- `browser_type(target: str, text: str, clear: bool)` - Type text
- `browser_fill(target: str, value: str)` - Fill input
- `browser_upload_file(target: str, file_path: str)` - Upload file

## Vision
- `browser_vision(full_page: bool)` - Screenshot as Base64 PNG
- `browser_screenshot(full_page: bool)` - Alias for browser_vision
- `browser_get_images()` - List all images on page
- `browser_get_text(selector: str)` - Extract visible text

## Dialog
- `browser_dialog(action: str, prompt_text: str)` - Handle JS dialogs
- `browser_wait_for_dialog(timeout: float)` - Wait for dialog

## Extraction
- `browser_console(expression: str)` - Execute JavaScript
- `browser_cdp(method: str, params: dict)` - Send CDP command

See README for usage examples.
