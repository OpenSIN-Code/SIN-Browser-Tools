# `tools/vision.py`

Visual capture and text/media extraction: screenshots, PDF, images, page text.

## Tools

| Tool | Signature | Description |
| --- | --- | --- |
| `browser_vision` | `(full_page=False)` | Screenshot → Base64 PNG (+ url). |
| `browser_screenshot` | `(full_page=False)` | Alias of `browser_vision`. |
| `browser_screenshot_element` | `(selector)` | Screenshot a single element — far cheaper on model context. |
| `browser_get_images` | `()` | All `<img>` with `src`, `alt`, natural width/height. |
| `browser_get_text` | `(selector="body")` | `innerText` of a selector (truncated to 8000 chars). |
| `browser_pdf` | `(landscape=False, print_background=True)` | Render page to a Base64 PDF. |

## Return shapes
- Image tools return `{"format": "png", "base64": "...", ...}`.
- `browser_pdf` returns `{"format": "pdf", "base64": "...", "bytes": N, "url": ...}`.

## Gotchas
- **PDF requires headless Chromium.** In headed mode Chromium cannot generate a
  PDF; `browser_pdf` catches this and returns a clear
  `{"error": "PDF generation failed (headless Chromium only): ..."}` instead of
  an opaque Playwright exception.
- `browser_get_text` is capped at 8000 chars; use `extraction.browser_get_html`
  with a higher `max_length` when you need the raw markup.
- Prefer `browser_screenshot_element` over a full-page screenshot when you only
  need one component — full-page Base64 blobs are large and expensive in context.
- These tools operate on the **active page**; switch tabs first if needed.
