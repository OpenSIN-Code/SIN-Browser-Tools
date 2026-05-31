# Architecture Overview

SIN-Browser-Tools is a native browser automation library with three integration layers:

## Core Components

**SINBrowserManager** - Main orchestrator
- Manages Playwright browser lifecycle
- Supports local browsers or remote CDP connections
- Handles dialog events asynchronously

**ElementRegistry** - Ref-ID mapping system
- Maps @e1, @e2, etc. to element handles
- Enables robust cross-session element targeting
- Auto-increments counter for each new element

**18 Tools** across 6 categories:
- **Accessibility**: browser_snapshot (accessibility tree with Ref-IDs)
- **Navigation**: navigate, back, scroll, press
- **Interaction**: click, type, fill, upload_file
- **Vision**: screenshot, get_images, get_text
- **Dialog**: dialog, wait_for_dialog
- **Extraction**: console, cdp

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
