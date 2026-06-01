"""
Example 1: Basic Navigation and Snapshot

This example demonstrates the fundamental loop:
1. Navigate to a page
2. Take a snapshot to see elements
3. Interact with elements using @eN refs
4. Verify the result
"""

import asyncio

from sin_browser_tools.core import manager
from sin_browser_tools.tools import accessibility, interaction, navigation


async def main():
    # Start browser (headless by default)
    await manager.start_local()

    try:
        # 1. Navigate to a page
        await navigation.browser_navigate("https://example.com")
        print("Navigated to example.com")

        # 2. Take a snapshot to see what's on the page
        snapshot = await accessibility.browser_snapshot()
        print(f"Found {snapshot['ref_count']} interactive elements")
        print("Page structure:")
        print(snapshot["tree"][:500])  # First 500 chars

        # 3. Get the URL to verify
        url_info = await navigation.browser_get_url()
        print(f"Current URL: {url_info['url']}")
        print(f"Page title: {url_info['title']}")

    finally:
        # Always cleanup
        await manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
