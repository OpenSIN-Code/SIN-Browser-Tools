"""
Example 5: Multi-Tab Workflow

This example demonstrates working with multiple tabs:
- Opening new tabs
- Switching between tabs
- Closing tabs
"""

import asyncio

from sin_browser_tools.core import manager
from sin_browser_tools.tools import accessibility, navigation


async def main():
    await manager.start_local()

    try:
        # Navigate initial tab
        await navigation.browser_navigate("https://example.com")
        print("Tab 0: example.com")

        # Open a second tab
        await navigation.browser_new_tab("https://httpbin.org")
        print("Tab 1: httpbin.org (now active)")

        # Open a third tab without navigating
        await navigation.browser_new_tab()
        await navigation.browser_navigate("https://jsonplaceholder.typicode.com")
        print("Tab 2: jsonplaceholder.typicode.com (now active)")

        # List all open tabs
        tabs = await navigation.browser_list_tabs()
        print(f"\nOpen tabs ({tabs['count']}):")
        for i, tab in enumerate(tabs["tabs"]):
            active = " (active)" if tab["active"] else ""
            print(f"  [{i}] {tab['title'][:30]} - {tab['url'][:40]}{active}")

        # Switch back to first tab
        await navigation.browser_switch_tab(0)
        print("\nSwitched to tab 0")

        # Verify we're on example.com
        url = await navigation.browser_get_url()
        print(f"Current URL: {url['url']}")

        # Take snapshot of this tab
        snapshot = await accessibility.browser_snapshot()
        print(f"Tab 0 has {snapshot['ref_count']} elements")

        # Close the middle tab (httpbin)
        await navigation.browser_close_tab(1)
        print("\nClosed tab 1 (httpbin)")

        # List tabs again
        tabs = await navigation.browser_list_tabs()
        print(f"Remaining tabs: {tabs['count']}")

    finally:
        await manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
