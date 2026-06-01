# Examples

Usage examples for SIN-Browser-Tools.

## Quick Start

Before running examples, install dependencies:

```bash
pip install -e ".[dev]"
python -m playwright install chromium
```

## Examples

| File | Description |
|------|-------------|
| `01_basic_navigation.py` | Navigate, snapshot, and extract page info |
| `02_form_interaction.py` | Fill forms, click buttons, handle inputs |
| `03_shadow_dom_frames.py` | Access content in shadow DOM and iframes |
| `04_screenshots_pdf.py` | Capture screenshots and generate PDFs |
| `05_multi_tab.py` | Work with multiple browser tabs |
| `debug_helper.py` | Interactive REPL for debugging |

## Running Examples

```bash
# Run a specific example
python examples/01_basic_navigation.py

# Interactive debug session
python examples/debug_helper.py
```

## Debug Helper Commands

The debug helper provides an interactive REPL:

```
debug> goto https://example.com    # Navigate
debug> snap                        # Show page snapshot
debug> frames                      # List all frames
debug> scan Invoice                # Search all frames for text
debug> eval document.title         # Run JavaScript
debug> html h1                     # Get element HTML
debug> shot                        # Take screenshot
debug> ref @e1                     # Inspect element ref
debug> history                     # Show action history
debug> quit                        # Exit
```
