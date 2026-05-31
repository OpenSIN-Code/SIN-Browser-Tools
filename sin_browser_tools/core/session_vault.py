"""
Session State Vault -- Persistiert und injiziert Sessions.
Loest das GMX-SID-Problem durch zentrales Session-Management mit
automatischer SID-Extraktion und TTL-basiertem Expiry.
"""

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

from playwright.async_api import BrowserContext, Page
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class SessionRecord:
    """Persistierte Session-Daten fuer eine Domain."""

    domain: str
    cookies: list
    origins: list
    active_sids: dict
    last_url: str
    created_at: float
    last_used: float
    ttl_seconds: int = 3600  # 1 Stunde default

    def is_expired(self) -> bool:
        return (time.time() - self.last_used) > self.ttl_seconds


class SessionVault:
    """
    Persistenter Session-Speicher mit Auto-SID-Detection.
    Speichert Cookies, LocalStorage und aktive SIDs pro Domain.
    """

    def __init__(self, storage_path: str = "./.sin_vault"):
        self.storage = Path(storage_path)
        self.storage.mkdir(parents=True, exist_ok=True)

    def _vault_file(self, domain: str) -> Path:
        safe_domain = domain.replace(".", "_").replace("/", "_")
        return self.storage / f"{safe_domain}.json"

    async def save_session(
        self, context: BrowserContext, domain: str, current_url: str = ""
    ) -> SessionRecord:
        """Speichert den kompletten Session-State."""
        state = await context.storage_state()

        active_sids: dict = {}
        for page in context.pages:
            sid = self._extract_sid_from_url(page.url)
            if sid:
                active_sids[page.url] = sid

        record = SessionRecord(
            domain=domain,
            cookies=state.get("cookies", []),
            origins=state.get("origins", []),
            active_sids=active_sids,
            last_url=current_url or (context.pages[0].url if context.pages else ""),
            created_at=time.time(),
            last_used=time.time(),
        )

        with open(self._vault_file(domain), "w", encoding="utf-8") as f:
            json.dump(asdict(record), f, indent=2)

        logger.info(
            "Session saved",
            domain=domain,
            cookies=len(record.cookies),
            sids=len(record.active_sids),
        )
        return record

    async def restore_session(self, context: BrowserContext, domain: str) -> bool:
        """
        Stellt eine Session aus dem Vault wieder her.
        Gibt False zurueck wenn keine oder abgelaufene Session vorhanden ist.
        """
        vault_file = self._vault_file(domain)
        if not vault_file.exists():
            logger.debug("No vault file found", domain=domain)
            return False

        try:
            with open(vault_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            record = SessionRecord(**data)
        except Exception as e:
            logger.warning("Vault file corrupted", domain=domain, error=str(e))
            return False

        if record.is_expired():
            logger.info("Session expired", domain=domain)
            vault_file.unlink(missing_ok=True)
            return False

        try:
            if record.cookies:
                await context.add_cookies(record.cookies)
        except Exception as e:
            logger.warning("Cookie injection failed", error=str(e))

        # LocalStorage via Page-Evaluate injizieren
        if context.pages and record.origins:
            page = context.pages[0]
            for origin_entry in record.origins:
                origin = origin_entry.get("origin")
                local_storage = origin_entry.get("localStorage", [])
                if origin and local_storage:
                    try:
                        await page.goto(origin, wait_until="domcontentloaded", timeout=5000)
                        for item in local_storage:
                            await page.evaluate(
                                f"localStorage.setItem({json.dumps(item['name'])}, "
                                f"{json.dumps(item['value'])})"
                            )
                    except Exception as e:
                        logger.debug(
                            "LocalStorage injection failed", origin=origin, error=str(e)
                        )

        logger.info("Session restored", domain=domain)
        return True

    async def detect_sid_redirect(
        self, page: Page, timeout_ms: int = 10000
    ) -> Optional[str]:
        """
        Erkennt GMX-style SID-Redirects (logoutlounge -> neue SID).
        Gibt die neue SID zurueck wenn gefunden, sonst None.
        """
        current_url = page.url
        sid_indicators = ["logoutlounge", "session=expired", "login?reason="]

        if not any(indicator in current_url for indicator in sid_indicators):
            return None

        logger.info("Session expired detected, waiting for redirect", url=current_url)
        try:
            await page.wait_for_url("**/*sid=**", timeout=timeout_ms)
            new_sid = self._extract_sid_from_url(page.url)
            if new_sid:
                logger.info("New SID acquired", sid=new_sid[:20] + "...")
                return new_sid
        except Exception as e:
            logger.warning("SID redirect timeout", error=str(e))

        return None

    @staticmethod
    def _extract_sid_from_url(url: str) -> Optional[str]:
        """Extrahiert SID-Parameter aus URL."""
        try:
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            for key in ["sid", "session_id", "sessionid", "token", "auth_token"]:
                if key in params:
                    return params[key][0]
        except Exception:
            pass
        return None

    async def list_sessions(self) -> list[SessionRecord]:
        """Listet alle gespeicherten Sessions."""
        records = []
        for vault_file in self.storage.glob("*.json"):
            try:
                with open(vault_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                records.append(SessionRecord(**data))
            except Exception:
                continue
        return records

    async def clear_expired(self) -> int:
        """Loescht alle abgelaufenen Sessions. Gibt Anzahl zurueck."""
        cleared = 0
        for vault_file in self.storage.glob("*.json"):
            try:
                with open(vault_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                record = SessionRecord(**data)
                if record.is_expired():
                    vault_file.unlink()
                    cleared += 1
            except Exception:
                continue
        return cleared
