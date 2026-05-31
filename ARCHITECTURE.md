# Architecture Overview

SIN-Browser-Tools is a native browser automation library with three integration layers:

## Core Components

**SINBrowserManager** - Main orchestrator
- Manages Playwright browser lifecycle
- Supports local browsers or remote CDP connections
- Handles dialog events asynchronously

**ElementRegistry** - Ref-ID mapping system
- Maps @e1, @e2, etc. to Playwright handles or CDP descriptors
- CDP descriptors carry `backendDOMNodeId` + `role`/`name` + the **owning
  Playwright `Frame`**. `backendDOMNodeId`s are target-local, so the owning
  frame is required to resolve / click nodes that live inside a cross-origin
  OOPIF (separate renderer target)
- Enables robust element targeting across OOPIFs and Shadow-DOM
- Auto-increments counter for each new element; cleared on every snapshot

## OOPIF accessibility & click routing

Cross-origin iframes run as **OOPIFs** (out-of-process iframes) in their own
renderer target. `Accessibility.getFullAXTree(pierce=True)` on the page target
pierces Shadow-DOM and same-origin subframes but **stops at OOPIF boundaries**.

- **Snapshot** (`tools/accessibility.py`): scans the main frame with `pierce`,
  then opens a dedicated CDP session per cross-origin frame and merges the
  trees. Reports `oopif_count`. This is the GMX / web.de mail-list fix.
- **Click** (`tools/interaction.py`): two strategies with fallback —
  (1) Playwright role-locator on the node's owning frame (Playwright routes
  input into the correct OOPIF renderer natively), then
  (2) frame-scoped CDP coordinates dispatched as top-level mouse input.

**Tool catalog** (`tools/catalog.py`) - single source of truth
- Auto-discovers every `browser_*` coroutine across the tool modules
- Generates MCP `inputSchema` from each function signature
- Tool names are the function names verbatim (`browser_navigate`), which are
  valid under the MCP/Anthropic schema `^[a-zA-Z0-9_-]{1,64}$`. A slash form
  (`browser/navigate`) is rejected by Claude Desktop / Cursor / Cline and would
  silently disable every tool.
- Both the MCP server and the OpenSIN skill registry consume the catalog, so the
  advertised surface can never drift from the implementation.

**46 Tools** across categories:
- **Accessibility**: snapshot, snapshot_full_oopif
- **Navigation**: navigate, back, forward, reload, scroll, press, get_url, set_viewport, wait_for*, tabs
- **Interaction**: click, click_cdp, double_click, right_click, hover, drag, select_option, check, type, fill, upload_file
- **Vision**: vision/screenshot, screenshot_element, pdf, get_images, get_text
- **Dialog**: dialog, wait_for_dialog
- **Extraction**: console, cdp, get_html, get_links, get_attribute, storage, cookies

## Integration Layers

1. **MCP Server** - Claude Desktop, Cursor, Cline compatible
2. **OpenSIN CLI** - `sin-browser <command>` interface
3. **Python API** - Direct import and use

## Design Principles

- Vision-first navigation (no HTML parsing)
- JSON-serializable results
- Async/await throughout
- Zero-configuration defaults
- Multi-runtime support (local + CDP)
