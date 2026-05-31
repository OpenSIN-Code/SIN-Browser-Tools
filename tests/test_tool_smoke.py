"""End-to-end smoke tests for every ``browser_*`` MCP tool.

Goal: catch wiring/regression bugs (like the snapshot AX-tree crash in Issue #7,
the exact-text click no-op, and the tab-close AttributeError) automatically.

Each test drives a real headless Chromium against the self-contained fixture
page from ``conftest.py`` -- no network, no external sites. The tests are
intentionally shallow ("does the tool run and return a sane shape?") rather than
deep behavioural tests, so they stay fast and stable while still exercising the
full surface area that agents call.
"""

import inspect

import pytest

from sin_browser_tools.tools import (
    accessibility,
    catalog,
    dialog,
    extraction,
    interaction,
    navigation,
    vision,
)


# ---------------------------------------------------------------------------
# Catalog / schema integrity (no browser needed)
# ---------------------------------------------------------------------------

def test_catalog_discovers_tools():
    """Every advertised tool is an async function named ``browser_*``."""
    tools = catalog.discover()
    assert len(tools) >= 40, f"expected the full tool surface, got {len(tools)}"
    for name, fn in tools.items():
        assert name.startswith("browser_"), name
        assert inspect.iscoroutinefunction(fn), f"{name} must be async"


def test_catalog_tool_names_are_mcp_schema_safe():
    """MCP / Anthropic require tool names to match ^[a-zA-Z0-9_-]{1,64}$."""
    import re

    pattern = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
    for name in catalog.discover():
        assert pattern.match(name), f"{name!r} is not a valid MCP tool name"


def test_catalog_every_tool_has_valid_input_schema():
    """``input_schema`` must produce a well-formed JSON schema for each tool."""
    for name, fn in catalog.discover().items():
        schema = catalog.input_schema(fn)
        assert schema["type"] == "object", name
        assert isinstance(schema["properties"], dict), name
        assert isinstance(schema["required"], list), name
        # Every required param must actually appear in properties.
        for req in schema["required"]:
            assert req in schema["properties"], f"{name}: {req} missing from properties"


async def test_browser_list_tools_self_describes(live_manager):
    result = await catalog.browser_list_tools()
    assert result["count"] >= 40
    names = {t["name"] for t in result["tools"]}
    assert "browser_navigate" in names
    assert "browser_snapshot" in names
    # filter narrows the list
    filtered = await catalog.browser_list_tools(filter="click")
    assert filtered["count"] >= 1
    assert all("click" in t["name"] or "click" in t["description"].lower()
               for t in filtered["tools"])


# ---------------------------------------------------------------------------
# Accessibility / snapshot (regression guard for Issue #6 + #7)
# ---------------------------------------------------------------------------

async def test_browser_snapshot_runs(live_manager):
    res = await accessibility.browser_snapshot()
    assert "tree" in res
    assert res["ref_count"] >= 1  # at least the button is interactive
    assert "Click Me" in res["tree"]


async def test_browser_snapshot_full_oopif_runs(live_manager):
    """Regression guard for Issue #7: must not crash on FrameInfo.frame."""
    res = await accessibility.browser_snapshot_full_oopif()
    assert "tree" in res
    assert res["method"] == "cdp_multitarget_pierce"
    assert res["ref_count"] >= 1


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

async def test_navigation_basics(live_manager):
    url = await navigation.browser_get_url()
    assert "url" in url and "title" in url

    scrolled = await navigation.browser_scroll(direction="down", amount=100)
    assert scrolled["status"] == "scrolled"

    pressed = await navigation.browser_press("Escape")
    assert pressed["status"] == "pressed"

    vp = await navigation.browser_set_viewport(width=800, height=600)
    assert vp == {"status": "resized", "width": 800, "height": 600}


async def test_navigation_goto_back_forward_reload(live_manager):
    a = await navigation.browser_navigate("data:text/html,<h1>Page A</h1>")
    assert "url" in a
    await navigation.browser_navigate("data:text/html,<h1>Page B</h1>")
    back = await navigation.browser_back()
    assert back["status"] == "navigated_back"
    fwd = await navigation.browser_forward()
    assert fwd["status"] == "navigated_forward"
    reloaded = await navigation.browser_reload()
    assert reloaded["status"] == "reloaded"


async def test_navigation_waits(live_manager):
    ready = await navigation.browser_wait_for("#btn", state="visible", timeout=5000)
    assert ready["status"] == "ready"

    found = await navigation.browser_wait_for_text("Smoke Test Page", timeout=5000)
    assert found["status"] == "found"

    loaded = await navigation.browser_wait_for_load(state="load", timeout=5000)
    assert loaded["status"] == "loaded"

    # Missing selector should time out gracefully, not raise.
    timed_out = await navigation.browser_wait_for("#nope", timeout=300)
    assert timed_out["status"] == "timeout"


async def test_tab_lifecycle(live_manager):
    """Regression guard for the tab-close AttributeError on the read-only
    ``page`` property."""
    tabs = await navigation.browser_list_tabs()
    assert tabs["count"] == 1

    opened = await navigation.browser_new_tab("data:text/html,<h1>Tab2</h1>")
    assert opened["status"] == "opened"
    assert (await navigation.browser_list_tabs())["count"] == 2

    switched = await navigation.browser_switch_tab(0)
    assert switched["status"] == "switched"

    closed = await navigation.browser_close_tab(1)
    assert closed["status"] == "closed"
    assert closed["remaining"] == 1

    with pytest.raises(ValueError):
        await navigation.browser_switch_tab(99)


# ---------------------------------------------------------------------------
# Interaction
# ---------------------------------------------------------------------------

async def test_click_via_selector_triggers_side_effect(live_manager):
    res = await interaction.browser_click("#btn")
    assert res["status"] == "clicked"
    result_text = await live_manager.page.inner_text("#result")
    assert result_text == "clicked"


async def test_find_and_click_by_text_via_registry(live_manager):
    await accessibility.browser_snapshot()  # populate the registry
    found = await interaction.browser_find_by_text("Click Me")
    assert found["count"] >= 1
    assert found["matches"][0]["ref"].startswith("@e")

    clicked = await interaction.browser_click_by_text("Click Me")
    assert clicked["source"] == "registry"
    assert (await live_manager.page.inner_text("#result")) == "clicked"


async def test_click_by_text_exact_is_not_a_no_op(live_manager):
    """Regression guard: exact=True previously passed has_text=True (a bool),
    making the locator filter a no-op. With a clean registry this must fall back
    to a live locator and match the exact text."""
    interaction.manager.registry.clear()
    res = await interaction.browser_click_by_text("Click Me", exact=True)
    assert res["source"] == "live_locator"
    assert res["status"] == "clicked"


async def test_click_by_text_no_match_raises(live_manager):
    interaction.manager.registry.clear()
    with pytest.raises(ValueError):
        await interaction.browser_click_by_text("Definitely Not On Page")


async def test_type_fill_check_select(live_manager):
    typed = await interaction.browser_type("#inp", "Ada Lovelace")
    assert typed["status"] == "typed"
    assert await live_manager.page.input_value("#inp") == "Ada Lovelace"

    filled = await interaction.browser_fill("#ta", "some notes")
    assert filled["status"] == "typed"
    assert await live_manager.page.input_value("#ta") == "some notes"

    checked = await interaction.browser_check("#chk", checked=True)
    assert checked["status"] == "checked"
    assert await live_manager.page.is_checked("#chk")

    selected = await interaction.browser_select_option("#sel", value="b")
    assert selected["status"] == "selected"
    assert await live_manager.page.input_value("#sel") == "b"


async def test_hover_double_right_click(live_manager):
    assert (await interaction.browser_hover("#btn"))["status"] == "hovered"
    assert (await interaction.browser_double_click("#btn"))["status"] == "double_clicked"
    assert (await interaction.browser_right_click("#btn"))["status"] == "right_clicked"


async def test_stale_ref_raises_helpful_error(live_manager):
    with pytest.raises(ValueError, match="not found"):
        await interaction.browser_click("@e999")


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

async def test_console_and_cdp(live_manager):
    res = await extraction.browser_console("1 + 1")
    assert res["result"] == "2"

    cdp = await extraction.browser_cdp("Browser.getVersion")
    assert "result" in cdp and "error" not in cdp


async def test_cookies_roundtrip(live_manager):
    # Use the already-loaded fixture origin so the test stays offline.
    url = live_manager.page.url
    set_res = await extraction.browser_set_cookie("smoke", "yes", url=url)
    assert set_res["status"] == "set"
    cookies = await extraction.browser_get_cookies(url)
    assert any(c["name"] == "smoke" for c in cookies["cookies"])
    cleared = await extraction.browser_clear_cookies()
    assert cleared["status"] == "cleared"


async def test_html_links_attribute_storage(live_manager):
    html = await extraction.browser_get_html()
    assert "Smoke Test Page" in html["html"]
    assert html["truncated"] is False

    links = await extraction.browser_get_links()
    assert links["count"] >= 1
    assert any("example.com" in lk["href"] for lk in links["links"])

    attr = await extraction.browser_get_attribute("#lnk", "href")
    assert attr["value"].startswith("https://example.com")

    await extraction.browser_storage(action="set", key="k", value="v")
    got = await extraction.browser_storage(action="get", key="k")
    assert got["value"] == "v"
    dump = await extraction.browser_storage(action="get")
    assert dump["items"]["k"] == "v"
    await extraction.browser_storage(action="remove", key="k")
    await extraction.browser_storage(action="clear")


async def test_get_attribute_missing_selector(live_manager):
    res = await extraction.browser_get_attribute("#does-not-exist", "href")
    assert "error" in res


# ---------------------------------------------------------------------------
# Vision
# ---------------------------------------------------------------------------

async def test_screenshot_and_text(live_manager):
    shot = await vision.browser_screenshot()
    assert shot["format"] == "png" and len(shot["base64"]) > 0

    el_shot = await vision.browser_screenshot_element("#btn")
    assert el_shot["format"] == "png"

    text = await vision.browser_get_text("body")
    assert "Smoke Test Page" in text["text"]

    images = await vision.browser_get_images()
    assert images["count"] >= 1

    pdf = await vision.browser_pdf()
    # headless Chromium supports PDF; expect bytes, not an error
    assert pdf.get("format") == "pdf" and pdf["bytes"] > 0


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

async def test_dialog_wait_then_accept(live_manager):
    import asyncio

    # Clicking #dlg-btn fires window.alert(). Kick the click off without
    # awaiting (the alert blocks until handled), then wait + accept it.
    asyncio.ensure_future(live_manager.page.click("#dlg-btn"))
    detected = await dialog.browser_wait_for_dialog(timeout=5.0)
    assert detected["status"] == "dialog_detected"
    assert detected["type"] == "alert"

    accepted = await dialog.browser_dialog("accept")
    assert accepted["status"] == "accepted"


async def test_dialog_invalid_action(live_manager):
    res = await dialog.browser_dialog("frobnicate")
    assert res["status"] == "error"
