# macOS Permissions for Spaces Control

To move browser windows between macOS Spaces (virtual desktops), SIN-Browser-Tools requires one of two external tools: **Hammerspoon** or **yabai**.

## Quick Decision Guide

| Need | Recommendation |
|------|----------------|
| Simple Spaces control, minimal setup | **Hammerspoon** |
| Advanced tiling/window management | **yabai** |
| No extra tools | AppleScript fallback (limited) |

## Option 1: Hammerspoon (Recommended)

Hammerspoon is a macOS automation tool that provides `hs.spaces` for Space management. It requires **only Accessibility permission** (no SIP changes).

### Installation

```bash
brew install --cask hammerspoon
```

### Setup

1. **Launch Hammerspoon** from Applications
2. **Grant Accessibility Permission**:
   - System Settings → Privacy & Security → Accessibility
   - Enable Hammerspoon
3. **Install CLI tool** (for SIN-Browser-Tools to invoke):
   - Open Hammerspoon Console (click menubar icon → Console)
   - Run: `hs.ipc.cliInstall()`
4. **Verify**:
   ```bash
   hs -c "return hs.spaces.allSpaces()"
   ```
   Should return a table of space IDs.

### Minimal Hammerspoon Config

Add to `~/.hammerspoon/init.lua`:

```lua
-- Enable IPC for CLI access (required for SIN-Browser-Tools)
require("hs.ipc")

-- Optional: Reload config shortcut
hs.hotkey.bind({"cmd", "alt", "ctrl"}, "R", function()
  hs.reload()
end)
```

Then reload: `hs -c "hs.reload()"` or Cmd+Alt+Ctrl+R.

## Option 2: yabai

yabai is a tiling window manager with powerful Space control. Moving windows between Spaces requires the **scripting addition**, which needs partial SIP disable.

### Installation

```bash
brew install koekeishiya/formulae/yabai
```

### SIP Configuration (for window moving)

To move windows between Spaces, yabai needs its scripting addition:

1. **Reboot into Recovery Mode**: Hold Cmd+R during boot
2. **Open Terminal** (Utilities → Terminal)
3. **Partially disable SIP**:
   ```bash
   csrutil enable --without debug --without fs
   ```
4. **Reboot normally**

### Enable Scripting Addition

```bash
# First time setup
sudo yabai --install-sa

# Load on startup (add to .yabairc)
yabai -m signal --add event=dock_did_restart action="sudo yabai --load-sa"
sudo yabai --load-sa
```

### Grant Accessibility

System Settings → Privacy & Security → Accessibility → Enable yabai

### Verify

```bash
yabai -m query --spaces
yabai -m query --windows
```

## Option 3: AppleScript Fallback

If neither Hammerspoon nor yabai is installed, SIN-Browser-Tools falls back to AppleScript. This backend can:

- ✅ Activate/focus windows
- ❌ **Cannot move windows between Spaces**
- ❌ **Cannot list or create Spaces**

The Space-related tools will return `{"status": "unsupported", ...}`.

## Verifying Your Setup

Run this to check which backend SIN-Browser-Tools will use:

```python
from sin_browser_tools.core.spaces import detect_backend

backend = detect_backend()
if backend:
    print(f"Using backend: {backend.name}")
else:
    print("No backend available")
```

Or from shell:

```bash
python -c "from sin_browser_tools.core.spaces import detect_backend; b=detect_backend(); print(b.name if b else 'none')"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `hs: command not found` | Run `hs.ipc.cliInstall()` in Hammerspoon Console |
| Hammerspoon can't move windows | Grant Accessibility permission in System Settings |
| yabai move fails | Install scripting addition; check SIP status with `csrutil status` |
| `No Spaces backend available` | Install Hammerspoon or yabai |

## Security Notes

- **Hammerspoon**: Safest option. Only needs Accessibility permission.
- **yabai scripting addition**: Requires partial SIP disable. Only do this if you understand the implications.
- **Both tools**: Only grant Accessibility to apps you trust.
