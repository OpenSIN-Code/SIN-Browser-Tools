"""
Example 4: Screenshot and PDF Generation

This example shows vision tools for capturing page content.
"""

import asyncio
import base64
from pathlib import Path

from sin_browser_tools.core import manager
from sin_browser_tools.tools import navigation, vision


async def main():
    await manager.start_local()

    try:
        # Navigate to a visually interesting page
        await navigation.browser_navigate("https://example.com")

        # 1. Take a screenshot (viewport only)
        screenshot = await vision.browser_screenshot(full_page=False)
        print(f"Screenshot taken: {len(screenshot['data'])} bytes (base64)")

        # Save screenshot to file
        img_data = base64.b64decode(screenshot["data"])
        Path("screenshot_viewport.png").write_bytes(img_data)
        print("Saved: screenshot_viewport.png")

        # 2. Full page screenshot
        full_screenshot = await vision.browser_screenshot(full_page=True)
        img_data = base64.b64decode(full_screenshot["data"])
        Path("screenshot_full.png").write_bytes(img_data)
        print("Saved: screenshot_full.png")

        # 3. Screenshot a specific element
        elem_screenshot = await vision.browser_screenshot_element("h1")
        if "data" in elem_screenshot:
            img_data = base64.b64decode(elem_screenshot["data"])
            Path("screenshot_h1.png").write_bytes(img_data)
            print("Saved: screenshot_h1.png")

        # 4. Generate PDF (headless only)
        pdf = await vision.browser_pdf(landscape=False, print_background=True)
        if "data" in pdf:
            pdf_data = base64.b64decode(pdf["data"])
            Path("page.pdf").write_bytes(pdf_data)
            print("Saved: page.pdf")
        else:
            print("PDF generation requires headless mode")

        # 5. Extract visible text
        text = await vision.browser_get_text()
        print(f"\nExtracted text ({len(text['text'])} chars):")
        print(text["text"][:200])

        # 6. Find all images on page
        images = await vision.browser_get_images()
        print(f"\nFound {len(images['images'])} images")

    finally:
        await manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
