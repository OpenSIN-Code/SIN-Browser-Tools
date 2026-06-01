"""
Example 3: Shadow DOM and Frame Traversal

This example demonstrates the frame tools for accessing content
inside shadow DOM and iframes (like GMX webmail, web components, etc.)
"""

import asyncio

from sin_browser_tools.core import manager
from sin_browser_tools.tools import frames, navigation


async def main():
    await manager.start_local()

    try:
        # Navigate to a page with iframes
        # (Using a data URL for demonstration)
        html = """
        <html>
        <body>
            <h1>Main Page</h1>
            <iframe name="content-frame" srcdoc="
                <h2>Inside Frame</h2>
                <p>This content is in an iframe</p>
                <my-component></my-component>
                <script>
                    customElements.define('my-component', class extends HTMLElement {
                        constructor() {
                            super();
                            const shadow = this.attachShadow({mode: 'open'});
                            shadow.innerHTML = '<p>Shadow DOM content: Secret Message</p>';
                        }
                    });
                </script>
            "></iframe>
        </body>
        </html>
        """
        await navigation.browser_navigate(f"data:text/html,{html}")

        # 1. List all frames on the page
        frame_list = await frames.browser_list_frames()
        print(f"Found {frame_list['count']} frames:")
        for f in frame_list["frames"]:
            print(f"  - name='{f['name']}' url={f['url'][:50]}")

        # 2. Evaluate JavaScript in a specific frame
        result = await frames.browser_eval_in_frame(
            "document.querySelector('h2')?.textContent",
            frame_name="content-frame"
        )
        print(f"\nFrame eval result: {result['result']}")

        # 3. Snapshot frame with shadow DOM piercing
        snapshot = await frames.browser_snapshot_in_frame(
            frame_name="content-frame",
            selector="p",
            pierce_shadow=True
        )
        print(f"\nFound {snapshot['count']} <p> elements (including shadow DOM):")
        for item in snapshot["items"]:
            print(f"  - {item['text']}")

        # 4. Scan ALL frames for text (useful for unnamed iframes)
        scan = await frames.browser_scan_frames(pattern="Secret")
        print(f"\nScanned {scan['total_frames']} frames, {scan['matching_frames']} matched 'Secret'")
        for f in scan["frames"]:
            print(f"  Frame {f['index']}: {f['matches']}")

    finally:
        await manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
