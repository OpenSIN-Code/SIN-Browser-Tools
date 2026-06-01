"""
SIN-Browser-Tools Debug Helper

A developer utility for debugging browser automation scripts.
Provides an interactive REPL and diagnostic tools.

Usage:
    python -m sin_browser_tools.debug
    # or
    python examples/debug_helper.py
"""

import asyncio
import json
import sys
from typing import Any

from sin_browser_tools.core import manager
from sin_browser_tools.tools import (
    accessibility,
    extraction,
    frames,
    navigation,
    vision,
)


class DebugHelper:
    """Interactive debug helper for SIN-Browser-Tools development."""

    def __init__(self):
        self.history: list[dict] = []

    async def start(self, headless: bool = False):
        """Start browser in debug mode (visible by default)."""
        print("[DEBUG] Starting browser in debug mode...")
        await manager.start_local(headless=headless, stealth=False)
        print(f"[DEBUG] Browser started. Headless={headless}")

    async def goto(self, url: str):
        """Navigate and print snapshot summary."""
        result = await navigation.browser_navigate(url)
        self._log("navigate", {"url": url}, result)
        await self.snapshot_summary()
        return result

    async def snapshot_summary(self):
        """Print a summary of the current page state."""
        snapshot = await accessibility.browser_snapshot()
        url = await navigation.browser_get_url()

        print(f"\n{'='*60}")
        print(f"URL: {url['url']}")
        print(f"Title: {url['title']}")
        print(f"Elements: {snapshot['ref_count']} refs (@e1-@e{snapshot['ref_count']})")
        print(f"{'='*60}")

        # Print first 1000 chars of tree
        tree = snapshot["tree"]
        if len(tree) > 1000:
            print(tree[:1000])
            print(f"... ({len(tree) - 1000} more chars)")
        else:
            print(tree)

        self._log("snapshot", {}, {"ref_count": snapshot["ref_count"]})
        return snapshot

    async def frames_info(self):
        """Print detailed frame information."""
        frame_list = await frames.browser_list_frames()
        print(f"\n[FRAMES] {frame_list['count']} frames found:")
        for i, f in enumerate(frame_list["frames"]):
            print(f"  [{i}] name='{f['name']}' url={f['url'][:60]}")
        return frame_list

    async def scan_all_frames(self, pattern: str = None):
        """Scan all frames for text content."""
        result = await frames.browser_scan_frames(pattern=pattern)
        print(f"\n[SCAN] Scanned {result['total_frames']} frames")
        print(f"       Matching: {result['matching_frames']}")
        for f in result["frames"]:
            print(f"\n  Frame {f['index']} (name='{f['name']}'):")
            print(f"    Text length: {f['text_length']}")
            if f.get("matches"):
                print(f"    Matches: {f['matches'][:3]}")
            print(f"    Preview: {f['text'][:200]}...")
        return result

    async def element_at(self, ref: str):
        """Get detailed info about an @eN ref."""
        # Refs are stored in manager.registry
        registry = getattr(manager._get_instance(), "_registry", {})
        if ref in registry:
            info = registry[ref]
            print(f"\n[REF] {ref}:")
            print(f"  Role: {info.get('role', 'unknown')}")
            print(f"  Name: {info.get('name', '')}")
            print(f"  Bounds: {info.get('bounds', 'unknown')}")
            return info
        else:
            print(f"[REF] {ref} not found in registry")
            return None

    async def eval_js(self, expr: str):
        """Evaluate JavaScript in the page."""
        result = await extraction.browser_console(expr)
        print(f"\n[EVAL] {expr}")
        print(f"       => {result.get('result', result.get('error', 'no result'))}")
        self._log("console", {"expression": expr}, result)
        return result

    async def screenshot(self, path: str = "debug_screenshot.png"):
        """Take a screenshot and save to file."""
        import base64
        from pathlib import Path

        result = await vision.browser_screenshot(full_page=False)
        if "data" in result:
            img_data = base64.b64decode(result["data"])
            Path(path).write_bytes(img_data)
            print(f"[SCREENSHOT] Saved to {path}")
        return result

    async def html(self, selector: str = None, max_length: int = 2000):
        """Get HTML content."""
        result = await extraction.browser_get_html(selector, max_length=max_length)
        html = result.get("html", "")
        print(f"\n[HTML] {selector or 'full page'} ({len(html)} chars):")
        print(html[:max_length])
        return result

    def _log(self, action: str, params: dict, result: Any):
        """Log action to history."""
        self.history.append({
            "action": action,
            "params": params,
            "result_summary": str(result)[:200],
        })

    def print_history(self):
        """Print action history."""
        print("\n[HISTORY]")
        for i, h in enumerate(self.history):
            print(f"  {i+1}. {h['action']}({h['params']}) => {h['result_summary'][:50]}")

    async def cleanup(self):
        """Cleanup browser."""
        await manager.cleanup()
        print("[DEBUG] Browser closed")


async def interactive_repl():
    """Run an interactive debug REPL."""
    debug = DebugHelper()
    await debug.start(headless=False)

    print("\n" + "="*60)
    print("SIN-Browser-Tools Debug REPL")
    print("="*60)
    print("Commands:")
    print("  goto <url>        - Navigate to URL")
    print("  snap              - Show page snapshot summary")
    print("  frames            - List all frames")
    print("  scan [pattern]    - Scan all frames for text")
    print("  eval <js>         - Evaluate JavaScript")
    print("  html [selector]   - Get HTML content")
    print("  shot [filename]   - Take screenshot")
    print("  ref <@eN>         - Get info about element ref")
    print("  history           - Show action history")
    print("  quit              - Exit")
    print("="*60 + "\n")

    while True:
        try:
            line = input("debug> ").strip()
            if not line:
                continue

            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "goto" and arg:
                await debug.goto(arg)
            elif cmd == "snap":
                await debug.snapshot_summary()
            elif cmd == "frames":
                await debug.frames_info()
            elif cmd == "scan":
                await debug.scan_all_frames(arg if arg else None)
            elif cmd == "eval" and arg:
                await debug.eval_js(arg)
            elif cmd == "html":
                await debug.html(arg if arg else None)
            elif cmd == "shot":
                await debug.screenshot(arg if arg else "debug_screenshot.png")
            elif cmd == "ref" and arg:
                await debug.element_at(arg)
            elif cmd == "history":
                debug.print_history()
            else:
                print(f"Unknown command: {cmd}")

        except KeyboardInterrupt:
            print("\n[Interrupted]")
            break
        except Exception as e:
            print(f"[ERROR] {e}")

    await debug.cleanup()


if __name__ == "__main__":
    asyncio.run(interactive_repl())
