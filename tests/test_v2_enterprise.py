"""
Integration Tests fuer SIN-Browser-Tools v2.0.
Verifiziert die 5 Core-Fixes aus der GMX-Fehleranalyse.
"""

import asyncio
import pytest

from sin_browser_tools.core.manager import BrowserManager, _RegistryStub
from sin_browser_tools.core.pii_redaction import PIIRedactor
from sin_browser_tools.core.session_vault import SessionVault
from sin_browser_tools.core.frame_traversal import UnifiedFrameTraverser
from sin_browser_tools.tools.smart_tools import SmartBrowserTools
from sin_browser_tools.tools.network_intercept import intercept_gmx_emails


@pytest.mark.asyncio
async def test_pii_redaction():
    """Verifiziert PII-Redaction in Snapshots."""
    redactor = PIIRedactor()
    test_data = {
        "value": "Bitte kontaktieren Sie max.mustermann@example.com oder +49 30 12345",
        "description": "SID: 496970b9954896064bc2a9b3a45a8a38fa754011859f9",
    }
    redacted = redactor.redact(test_data)

    assert "EMAIL_REDACTED" in redacted["value"]
    assert "PHONE_REDACTED" in redacted["value"]
    assert "SID_REDACTED" in redacted["description"]
    assert "max.mustermann" not in str(redacted)


@pytest.mark.asyncio
async def test_pii_redact_snapshot_removes_sid_from_url():
    """SID wird aus der URL im Snapshot entfernt."""
    redactor = PIIRedactor()
    snap = {"url": "https://navigator.gmx.net/mail?sid=abc123def456abc123def456abc123def456", "tree": {}}
    result = redactor.redact_snapshot(snap)
    assert "sid=" not in result["url"]


@pytest.mark.asyncio
async def test_session_vault_save_restore(tmp_path):
    """Session-Vault speichert und stellt Cookies wieder her."""
    vault = SessionVault(str(tmp_path))

    async with BrowserManager(headless=True).session() as mgr:
        await mgr.page.goto("https://example.com")
        record = await vault.save_session(mgr.context, "example.com")

        assert record.domain == "example.com"
        assert (tmp_path / "example_com.json").exists()

        # Restore auf frischem Context
        async with BrowserManager(headless=True).session() as mgr2:
            restored = await vault.restore_session(mgr2.context, "example.com")
            assert restored is True


@pytest.mark.asyncio
async def test_session_vault_expired(tmp_path):
    """Abgelaufene Sessions werden erkannt und geloescht."""
    import json
    import time

    vault = SessionVault(str(tmp_path))
    # Manuell eine expired Session anlegen
    expired_record = {
        "domain": "expired.com",
        "cookies": [],
        "origins": [],
        "active_sids": {},
        "last_url": "",
        "created_at": time.time() - 7200,
        "last_used": time.time() - 7200,  # 2 Stunden alt
        "ttl_seconds": 3600,
    }
    (tmp_path / "expired_com.json").write_text(json.dumps(expired_record))

    async with BrowserManager(headless=True).session() as mgr:
        restored = await vault.restore_session(mgr.context, "expired.com")

    assert restored is False
    assert not (tmp_path / "expired_com.json").exists()


@pytest.mark.asyncio
async def test_unified_frame_traverser_counts_main_frame():
    """UnifiedFrameTraverser liefert mindestens den Main-Frame."""
    async with BrowserManager(headless=True).session() as mgr:
        await mgr.page.goto("https://example.com")
        traverser = UnifiedFrameTraverser(pierce_shadow=True)
        frames = await traverser.traverse(mgr.page)

        assert len(frames) >= 1
        main_frames = [f for f in frames if f.is_main]
        assert len(main_frames) == 1
        assert main_frames[0].ax_tree is not None


@pytest.mark.asyncio
async def test_unified_frame_traverser_shadow_dom():
    """Shadow-DOM-Extraktion schlaegt nicht ab bei Seiten ohne Shadow Roots."""
    async with BrowserManager(headless=True).session() as mgr:
        await mgr.page.set_content("""
            <html><body>
                <div id="host"></div>
                <script>
                    const host = document.getElementById('host');
                    const shadow = host.attachShadow({ mode: 'open' });
                    shadow.innerHTML = '<p>Shadow content</p>';
                </script>
            </body></html>
        """)
        traverser = UnifiedFrameTraverser(pierce_shadow=True)
        frames = await traverser.traverse(mgr.page)

        main = frames[0]
        assert main.shadow_roots is not None
        # Mindestens ein Shadow Root gefunden
        assert len(main.shadow_roots) >= 1
        assert main.shadow_roots[0]["mode"] == "open"
        assert main.shadow_roots[0]["accessible"] is True


@pytest.mark.asyncio
async def test_smart_tools_deep_snapshot():
    """deep_snapshot liefert frame_count und aggregated_tree."""
    async with BrowserManager(headless=True).session() as mgr:
        await mgr.page.goto("https://example.com")
        tools = SmartBrowserTools(mgr.page, mgr.context)
        snap = await tools.deep_snapshot(pierce_shadow=True, redact_pii=True)

        assert "frame_count" in snap
        assert snap["frame_count"] >= 1
        assert "aggregated_tree" in snap
        assert snap["aggregated_tree"]["role"] == "RootWebArea"


@pytest.mark.asyncio
async def test_smart_tools_smart_navigate():
    """smart_navigate gibt status und final_url zurueck."""
    async with BrowserManager(headless=True).session() as mgr:
        tools = SmartBrowserTools(mgr.page, mgr.context)
        result = await tools.smart_navigate(
            "https://example.com", close_popups=False, wait_for_stability=False
        )

        assert "status" in result
        assert result["status"] == 200
        assert "example.com" in result["final_url"]


@pytest.mark.asyncio
async def test_intercept_gmx_emails_no_crash():
    """intercept_gmx_emails gibt eine leere Liste zurueck (ohne Login), crasht aber nicht."""
    async with BrowserManager(headless=True).session() as mgr:
        await mgr.page.goto("about:blank")
        emails = await intercept_gmx_emails(mgr.page, timeout_ms=1000)
        assert isinstance(emails, list)


@pytest.mark.asyncio
async def test_browser_manager_context_manager_cleans_up_on_exception():
    """BrowserManager.__aexit__ wird auch bei Exception ausgefuehrt."""
    crashed = False
    try:
        async with BrowserManager(headless=True) as mgr:
            await mgr.page.goto("about:blank")
            raise RuntimeError("intentional crash")
    except RuntimeError:
        crashed = True

    assert crashed
    assert mgr._browser is None
    assert mgr._playwright is None


# ---------------------------------------------------------------------------
# Issue #4: robust text-based ref lookup (no fragile snapshot-string regex)
# ---------------------------------------------------------------------------

def _seed_registry():
    reg = _RegistryStub()
    reg.register({"role": "button", "name": "Accept all", "backendDOMNodeId": 1})
    reg.register({"role": "link", "name": "Your statement is ready", "backendDOMNodeId": 2})
    reg.register({"role": "button", "name": "Accept", "backendDOMNodeId": 3})
    reg.register({"role": "textbox", "name": "", "backendDOMNodeId": 4})  # unlabeled
    return reg


def test_find_by_text_substring_case_insensitive():
    reg = _seed_registry()
    matches = reg.find_by_text("STATEMENT")
    assert len(matches) == 1
    assert matches[0]["name"] == "Your statement is ready"


def test_find_by_text_ranks_exact_then_shortest():
    reg = _seed_registry()
    # "accept" is a substring of both "Accept all" and "Accept"; the exact
    # match ("Accept") must rank first.
    matches = reg.find_by_text("accept")
    assert [m["name"] for m in matches] == ["Accept", "Accept all"]


def test_find_by_text_role_filter_and_exact():
    reg = _seed_registry()
    assert reg.find_by_text("Accept all", role="link") == []
    exact = reg.find_by_text("accept", exact=True)
    assert len(exact) == 1 and exact[0]["name"] == "Accept"


def test_find_by_text_ignores_unlabeled_and_missing():
    reg = _seed_registry()
    assert reg.find_by_text("") == []
    assert reg.find_by_text("nonexistent") == []
