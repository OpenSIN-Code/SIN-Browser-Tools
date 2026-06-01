"""Shared pytest fixtures for the tool smoke tests.

The smoke tests in ``test_tool_smoke.py`` exercise every ``browser_*`` tool
against a single, self-contained fixture page (no network, no external sites)
so that a regression in any tool's wiring is caught deterministically and
offline.
"""

from html import escape

import pytest

from sin_browser_tools.core.manager import BrowserManager, manager

# A tiny 1x1 transparent PNG so browser_get_images has a real <img> to report
# without any network dependency.
_PNG_1PX = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# Mirrors the GMX structure from Issue #11: a named ("mail") same-process iframe
# whose email rows are custom elements (<list-mail-item>) nested in OPEN shadow
# DOM. The accessibility tree is blind to these (custom elements have no role),
# and document.querySelectorAll('list-mail-item') on the frame returns 0 because
# it does not pierce shadow roots -- exactly the bug the new frame tools fix.
MAIL_FRAME_HTML = """<!doctype html><html><body>
<mail-list-container></mail-list-container>
<script>
customElements.define('list-mail-item', class extends HTMLElement {
  constructor(){ super(); const r=this.attachShadow({mode:'open'});
    r.innerHTML = '<div class="subject">'+this.getAttribute('subject')+'</div>'; }
});
customElements.define('mail-list-container', class extends HTMLElement {
  constructor(){ super(); const r=this.attachShadow({mode:'open'});
    const subs=['Invoice 2026-01','Welcome aboard','Your receipt'];
    r.innerHTML = subs.map(function(s){
      return '<list-mail-item subject="'+s+'"></list-mail-item>'; }).join(''); }
});
</script>
</body></html>"""


# Self-contained fixture page. Covers the element types every interaction /
# extraction / vision tool needs: heading, button (with click side effect),
# link, text input, textarea, native <select>, checkbox, an image, a
# same-origin iframe (for frame traversal / snapshot), plus a button that opens
# a native JS dialog (for the dialog tools).
FIXTURE_HTML = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>Smoke Fixture</title></head>
<body>
  <h1>Smoke Test Page</h1>
  <p id="lead">Hello smoke world.</p>
  <button id="btn" aria-label="Click Me">Click Me</button>
  <button id="dlg-btn" onclick="window.alert('hi from dialog')">Open Dialog</button>
  <a id="lnk" href="https://example.com/next">Go Next</a>
  <input id="inp" type="text" aria-label="Full Name" />
  <textarea id="ta" aria-label="Notes"></textarea>
  <select id="sel" aria-label="Choice">
    <option value="a">Alpha</option>
    <option value="b">Beta</option>
  </select>
  <label><input id="chk" type="checkbox" aria-label="Agree" /> Agree</label>
  <img id="logo" src="{png}" alt="logo" width="1" height="1" />
  <iframe id="frame" srcdoc="<button>inner button</button>"></iframe>
  <iframe id="mail" name="mail" srcdoc="{mail_srcdoc}"></iframe>
  <div id="result"></div>
  <script>
    document.getElementById('btn').addEventListener('click', () => {{
      document.getElementById('result').innerText = 'clicked';
    }});
  </script>
</body>
</html>""".format(png=_PNG_1PX, mail_srcdoc=escape(MAIL_FRAME_HTML, quote=True))


# Fake origin the fixture is served from. Using a real ``http://`` origin (via
# request routing, so it stays fully offline) instead of ``set_content`` is what
# lets localStorage/sessionStorage work: those APIs raise SecurityError on the
# opaque origin that ``set_content`` runs under.
FIXTURE_URL = "http://smoke.test/"


@pytest.fixture
async def live_manager():
    """Start a headless browser, register it as the global singleton, and load
    the fixture page from a routed (offline) http origin. Yields the live
    ``BrowserManager`` and tears everything down afterwards so each test starts
    from a clean browser.
    """
    mgr = BrowserManager(headless=True, stealth=False)
    await mgr.start_local()
    manager._set_instance(mgr)

    async def _serve_fixture(route):
        await route.fulfill(
            status=200,
            content_type="text/html",
            body=FIXTURE_HTML,
        )

    await mgr.page.route(FIXTURE_URL, _serve_fixture)
    await mgr.page.goto(FIXTURE_URL, wait_until="domcontentloaded")

    # The "mail" srcdoc iframe (GMX-like shadow-DOM fixture) loads its child
    # frame and upgrades its custom elements asynchronously -- domcontentloaded
    # on the top document does not wait for it, and the child Frame object (and
    # its .name) may not be exposed yet. srcdoc is same-origin, so we poll from
    # the PARENT document into the iframe's contentDocument until the shadow rows
    # exist. This makes the frame-tool tests deterministic.
    try:
        await mgr.page.wait_for_function(
            "() => { const ifr = document.getElementById('mail');"
            " const doc = ifr && ifr.contentDocument;"
            " const c = doc && doc.querySelector('mail-list-container');"
            " return !!(c && c.shadowRoot && c.shadowRoot.childElementCount >= 3); }",
            timeout=5000,
        )
    except Exception:
        pass

    try:
        yield mgr
    finally:
        try:
            manager.registry.clear()
        except Exception:
            pass
        await mgr.cleanup()
