"""Tests fuer parallele, isolierte Browser-Sessions (Multi-Context).

Verifiziert die Kernzusage des Features: jeder benannte Context ist ein eigener
Cookie-/Storage-Jar (Isolation), plus Lifecycle (create/list/switch/close) und
parallele Navigation.
"""

import pytest

from sin_browser_tools.core.manager import BrowserManager, manager
from sin_browser_tools.tools import sessions as S

# Eigene Origin, damit localStorage funktioniert (set_content/data: verbieten es).
ORIGIN = "http://session.test/"
_BODY = "<!doctype html><title>SessionFixture</title><h1>session</h1>"


@pytest.fixture
async def live_manager():
    mgr = BrowserManager(headless=True, stealth=False)
    await mgr.start_local()
    manager._set_instance(mgr)

    async def _serve(route):
        await route.fulfill(status=200, content_type="text/html", body=_BODY)

    # Auf Context-Ebene routen, damit JEDE Session (Context) dieselbe Fixture
    # offline ausliefert.
    await mgr.context.route(ORIGIN, _serve)
    await mgr.page.goto(ORIGIN, wait_until="domcontentloaded")
    try:
        yield mgr
    finally:
        await mgr.cleanup()


async def _route_all(mgr):
    """Routing-Helfer: route() pro neuem Context erneut setzen."""
    async def _serve(route):
        await route.fulfill(status=200, content_type="text/html", body=_BODY)
    return _serve


async def test_default_session_autoregistered(live_manager):
    res = await S.browser_list_sessions()
    assert res["status"] == "ok"
    assert res["active"] == "default"
    assert [c["name"] for c in res["contexts"]] == ["default"]


async def test_create_and_isolation(live_manager):
    mgr = live_manager

    assert (await S.browser_create_session("admin"))["status"] == "ok"
    assert (await S.browser_create_session("guest"))["status"] == "ok"

    # Routing fuer die neuen Contexts setzen.
    serve = await _route_all(mgr)
    for name in ("admin", "guest"):
        await manager.sessions._contexts[name].route(ORIGIN, serve)

    res = await S.browser_parallel_navigate(
        [{"name": "admin", "url": ORIGIN}, {"name": "guest", "url": ORIGIN}]
    )
    assert res["status"] == "ok"
    assert all(r["status"] == 200 for r in res["results"])

    # Isolation: localStorage in admin darf in guest NICHT sichtbar sein.
    await S.browser_switch_session("admin")
    await mgr.page.evaluate("localStorage.setItem('k','admin-value')")
    assert await mgr.page.evaluate("localStorage.getItem('k')") == "admin-value"

    await S.browser_switch_session("guest")
    assert await mgr.page.evaluate("localStorage.getItem('k')") is None


async def test_duplicate_name_rejected(live_manager):
    assert (await S.browser_create_session("dup"))["status"] == "ok"
    dup = await S.browser_create_session("dup")
    assert dup["status"] == "error"
    assert "already exists" in dup["error"]


async def test_close_switches_active(live_manager):
    await S.browser_create_session("temp")
    await S.browser_switch_session("temp")
    assert (await S.browser_list_sessions())["active"] == "temp"

    closed = await S.browser_close_session("temp")
    assert closed["status"] == "ok"
    # Aktive Session wechselte automatisch weg von der geschlossenen.
    assert (await S.browser_list_sessions())["active"] != "temp"


async def test_cannot_close_default_while_others_exist(live_manager):
    await S.browser_create_session("other")
    res = await S.browser_close_session("default")
    assert res["status"] == "error"


async def test_switch_unknown_session(live_manager):
    res = await S.browser_switch_session("does-not-exist")
    assert res["status"] == "error"
    assert "available" in res
