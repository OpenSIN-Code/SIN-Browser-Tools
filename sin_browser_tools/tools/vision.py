import base64
from sin_browser_tools.core import manager

async def browser_vision(full_page: bool = False) -> dict:
    img_bytes = await manager.page.screenshot(full_page=full_page)
    return {"format": "png", "base64": base64.b64encode(img_bytes).decode('utf-8'), "url": manager.page.url}

async def browser_screenshot(full_page: bool = False) -> dict:
    return await browser_vision(full_page=full_page)

async def browser_get_images() -> dict:
    images = await manager.page.evaluate("""
        () => Array.from(document.querySelectorAll('img')).map(img => ({
            src: img.src, alt: img.alt || '', width: img.naturalWidth, height: img.naturalHeight
        })).filter(img => img.src)
    """)
    return {"count": len(images), "images": images}

async def browser_get_text(selector: str = "body") -> dict:
    text = await manager.page.inner_text(selector)
    return {"text": text[:8000], "length": len(text)}


async def browser_screenshot_element(selector: str) -> dict:
    """Screenshot a single element (by CSS selector) as a Base64 PNG.

    Far cheaper on model context than a full-page screenshot when the agent only
    needs to look at one component.
    """
    el = await manager.page.query_selector(selector)
    if el is None:
        return {"error": f"No element matches selector: {selector}"}
    img_bytes = await el.screenshot()
    return {
        "format": "png",
        "base64": base64.b64encode(img_bytes).decode("utf-8"),
        "selector": selector,
    }


async def browser_pdf(landscape: bool = False, print_background: bool = True) -> dict:
    """Render the current page to a PDF and return it Base64-encoded.

    Chromium only supports PDF generation in headless mode; this surfaces a
    clear error instead of throwing an opaque Playwright exception otherwise.
    """
    try:
        pdf_bytes = await manager.page.pdf(
            landscape=landscape, print_background=print_background
        )
    except Exception as e:
        return {"error": f"PDF generation failed (headless Chromium only): {e}"}
    return {
        "format": "pdf",
        "base64": base64.b64encode(pdf_bytes).decode("utf-8"),
        "bytes": len(pdf_bytes),
        "url": manager.page.url,
    }
