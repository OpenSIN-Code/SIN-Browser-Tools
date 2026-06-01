# Window Control & macOS Spaces

## Overview

SIN-Browser-Tools provides two complementary layers of window management:

1. **Window Control (cross-platform)** - CDP-based window sizing, positioning, and state management
2. **macOS Spaces (macOS-only)** - Move browser windows between virtual desktops

## Window Control Tools

All window tools require **headful mode** (`SIN_HEADLESS=false` or `headless=False`).

### Available Tools

| Tool | Description |
|------|-------------|
| `browser_get_window_bounds` | Read current position, size, and state |
| `browser_set_window_bounds` | Set exact pixel position/size |
| `browser_set_window_mode` | Preset sizes: small/medium/large/maximized/fullscreen |
| `browser_maximize_window` | Maximize window |
| `browser_minimize_window` | Minimize to dock/taskbar |
| `browser_fullscreen_window` | Enter fullscreen |
| `browser_restore_window` | Restore from max/min/fullscreen |
| `browser_move_window` | Move window to screen position |

### Window Modes

| Mode | Size |
|------|------|
| `small` | 1024 x 720 |
| `medium` | 1280 x 800 |
| `large` | 1600 x 1000 |
| `maximized` | OS-determined |
| `fullscreen` | Full screen |

### Example Usage

```python
# Resize window to medium preset
await browser_set_window_mode("medium")

# Move window to top-left corner
await browser_move_window(left=0, top=0)

# Set exact size
await browser_set_window_bounds(width=1400, height=900)

# Minimize while agent works
await browser_minimize_window()
# ... do background work ...
await browser_restore_window()
```

## macOS Spaces Tools

Move the browser to another virtual desktop (Space) so it runs "in the background" without cluttering the user's active workspace.

### Available Tools

| Tool | Description |
|------|-------------|
| `browser_list_spaces` | List all available Spaces |
| `browser_create_space` | Create a new Space |
| `browser_move_to_space` | Move browser to specific Space (1-based index) |
| `browser_get_window_space` | Query which Space the browser is on |
| `browser_send_to_background_space` | Auto-find/create a background Space and move there |

### Backend Priority

SIN-Browser-Tools auto-detects the best available backend:

1. **Hammerspoon** (recommended) - Only needs Accessibility permission
2. **yabai** - More powerful, but requires partial SIP disable
3. **AppleScript** - Limited fallback (cannot move between Spaces)

Override with `SIN_SPACE_BACKEND=hammerspoon|yabai|applescript`.

### Example: Background Automation

```python
# Move browser to a dedicated background Space
result = await browser_send_to_background_space(create_if_needed=True)
# Browser is now on Space 3 (for example)
# User continues working on Space 1 undisturbed

# ... agent performs automation ...

# When done, optionally bring back
await browser_move_to_space(1)  # Return to user's Space
```

## Configuration

### Environment Variables

```bash
# Headful mode (required for window control)
SIN_HEADLESS=false

# Initial window mode at launch
SIN_WINDOW_MODE=medium  # default|small|medium|large|maximized|fullscreen

# Custom initial size
SIN_WINDOW_WIDTH=1280
SIN_WINDOW_HEIGHT=800

# Initial position (optional)
SIN_WINDOW_LEFT=100
SIN_WINDOW_TOP=100

# Spaces backend (macOS)
SIN_SPACE_BACKEND=auto  # auto|yabai|hammerspoon|applescript
```

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `needs headful` | Running in headless mode | Set `SIN_HEADLESS=false` |
| `No Spaces backend` | Missing yabai/Hammerspoon | Install one; see `PERMISSIONS_MACOS.md` |
| `window not found` | PID lookup failed | Ensure browser is started |
| `move failed` | Missing permissions | Grant Accessibility permission |

## Technical Details

### CDP Window Control

Window control uses the Chrome DevTools Protocol:

- `Browser.getWindowForTarget` - Get window ID for current target
- `Browser.setWindowBounds` - Set position, size, or state

Important: `windowState` changes (maximized, fullscreen) cannot be combined with bounds changes. The implementation automatically handles state transitions.

### Spaces Implementation

The Spaces feature uses external tools because macOS has no public API:

- **Hammerspoon**: `hs.spaces.moveWindowToSpace(windowID, spaceID)`
- **yabai**: `yabai -m window <id> --space <n>`

Window identification is done via the browser's PID (resolved during `start_local()`).
