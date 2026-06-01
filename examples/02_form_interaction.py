"""
Example 2: Form Interaction

This example shows how to:
- Fill out form fields
- Click buttons
- Handle form submission
"""

import asyncio

from sin_browser_tools.core import manager
from sin_browser_tools.tools import accessibility, extraction, interaction, navigation


async def main():
    await manager.start_local()

    try:
        # Navigate to a form page (using httpbin as example)
        await navigation.browser_navigate("https://httpbin.org/forms/post")

        # Take snapshot to see form elements
        snapshot = await accessibility.browser_snapshot()
        print(f"Found {snapshot['ref_count']} elements")

        # Fill form fields using CSS selectors
        await interaction.browser_fill('input[name="custname"]', "John Doe")
        await interaction.browser_fill('input[name="custtel"]', "555-1234")
        await interaction.browser_fill('input[name="custemail"]', "john@example.com")

        # Select a pizza size (radio button)
        await interaction.browser_click('input[value="medium"]')

        # Check a topping (checkbox)
        await interaction.browser_check('input[name="topping"][value="cheese"]', checked=True)

        # Type in the textarea
        await interaction.browser_type(
            'textarea[name="comments"]',
            "Please deliver to the back door."
        )

        # Take another snapshot to verify form is filled
        snapshot = await accessibility.browser_snapshot()
        print("Form filled, ready to submit")

        # Get HTML to see form state
        html = await extraction.browser_get_html('form', max_length=1000)
        print("Form HTML preview:", html["html"][:300])

    finally:
        await manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
