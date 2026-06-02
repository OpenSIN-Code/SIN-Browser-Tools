"""
PII Redaction Engine -- Entfernt sensible Daten vor LLM-Uebergabe.
Verhindert DSGVO-Leaks bei Enterprise-Kunden.

Regex-basiert ohne externe NLP-Abhaengigkeiten (kein presidio erforderlich).
"""

import re
from dataclasses import dataclass
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


def _luhn_valid(number: str) -> bool:
    """Return True if digit string passes Luhn checksum."""
    digits = [int(c) for c in number if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


@dataclass
class RedactionStats:
    """Statistiken ueber durchgefuehrte Redaktionen."""

    emails: int = 0
    phones: int = 0
    credit_cards: int = 0
    session_ids: int = 0
    ibans: int = 0
    custom: int = 0
    total: int = 0


class PIIRedactor:
    """
    Entfernt PII (Personally Identifiable Information) aus Accessibility Trees,
    DOM-Snapshots und Text-Daten, BEVOR sie an LLMs gesendet werden.
    """

    PATTERNS = {
        "email": re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b(?!\|)"
        ),
        "phone": re.compile(
            r"\b(?:\+?49|0)[\s\-]?\(?[0-9]{2,5}\)?[\s\-]?[0-9]{3,8}[\s\-]?[0-9]{0,8}\b"
        ),
        "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
        "sid": re.compile(r"\b[a-f0-9]{32,64}\b", re.IGNORECASE),
        "iban": re.compile(
            r"\b[A-Z]{2}\d{2}\s?(?:\d{4}\s?){2,7}(?:\d{0,4})?\b"
        ),
    }

    # Attribute-Keys in AX-Tree-Nodes, deren Werte auf PII geprueft werden
    SENSITIVE_ATTRIBUTES = {
        "value",
        "text",
        "description",
        "name",
        "placeholder",
        "aria-label",
        "title",
    }

    # Keys, die niemals an LLMs gehen sollten (komplett redigiert)
    BLOCKED_KEYS = {
        "password",
        "csrf",
        "xsrf",
        "token",
        "secret",
        "apikey",
        "api_key",
        "authorization",
        "cookie",
    }

    def __init__(
        self,
        custom_patterns: Optional[dict] = None,
        aggressive: bool = True,
    ):
        self.patterns = {**self.PATTERNS}
        if custom_patterns:
            self.patterns.update(custom_patterns)
        self.aggressive = aggressive

    def redact(self, data: Any, stats: Optional[RedactionStats] = None) -> Any:
        """
        Haupt-API: Redigiert beliebige Datenstrukturen rekursiv.
        """
        if stats is None:
            stats = RedactionStats()

        result = self._redact_recursive(data, stats)
        stats.total = (
            stats.emails
            + stats.phones
            + stats.credit_cards
            + stats.session_ids
            + stats.ibans
            + stats.custom
        )

        if stats.total > 0:
            logger.info(
                "PII redaction completed",
                emails=stats.emails,
                phones=stats.phones,
                credit_cards=stats.credit_cards,
                session_ids=stats.session_ids,
            )

        return result

    def _redact_recursive(self, data: Any, stats: RedactionStats) -> Any:
        if isinstance(data, dict):
            return self._redact_dict(data, stats)
        elif isinstance(data, list):
            return [self._redact_recursive(item, stats) for item in data]
        elif isinstance(data, str):
            return self._redact_string(data, stats)
        else:
            return data

    def _redact_dict(self, data: dict, stats: RedactionStats) -> dict:
        result = {}
        for key, value in data.items():
            key_lower = key.lower()

            if any(blocked in key_lower for blocked in self.BLOCKED_KEYS):
                result[key] = "[REDACTED]"
                stats.custom += 1
                continue

            if key_lower in self.SENSITIVE_ATTRIBUTES and isinstance(value, str):
                result[key] = self._redact_string(value, stats)
            else:
                result[key] = self._redact_recursive(value, stats)

        return result

    def _redact_string(self, text: str, stats: RedactionStats) -> str:
        if not text or len(text) < 4:
            return text

        email_matches = self.patterns["email"].findall(text)
        if email_matches:
            stats.emails += len(email_matches)
            text = self.patterns["email"].sub("[EMAIL_REDACTED]", text)

        cc_count = 0
        def _redact_cc(m):
            nonlocal cc_count
            if _luhn_valid(m.group(0)):
                cc_count += 1
                return "[CC_REDACTED]"
            return m.group(0)
        text = self.patterns["credit_card"].sub(_redact_cc, text)
        if cc_count:
            stats.credit_cards += cc_count

        phone_matches = self.patterns["phone"].findall(text)
        if phone_matches:
            stats.phones += len(phone_matches)
            text = self.patterns["phone"].sub("[PHONE_REDACTED]", text)

        iban_matches = self.patterns["iban"].findall(text)
        if iban_matches:
            stats.ibans += len(iban_matches)
            text = self.patterns["iban"].sub("[IBAN_REDACTED]", text)

        if self.aggressive:
            sid_matches = self.patterns["sid"].findall(text)
            if sid_matches:
                stats.session_ids += len(sid_matches)
                text = self.patterns["sid"].sub("[SID_REDACTED]", text)

        return text

    def redact_ax_tree(self, ax_tree: dict) -> dict:
        """Spezialisiertes Redigieren fuer Accessibility Trees."""
        return self.redact(ax_tree)

    def redact_snapshot(self, snapshot: dict) -> dict:
        """Redigiert einen kompletten browser_snapshot Output."""
        result = dict(snapshot)

        if "tree" in result and result["tree"]:
            result["tree"] = self.redact_ax_tree(result["tree"])

        if "url" in result:
            result["url"] = re.sub(r"[?&]sid=[^&]+", "", result["url"])

        return result
