"""CAPTCHA / anti-bot detection.

Does NOT solve challenges. It tells the agent *honestly* "you cannot proceed
here" with a concrete provider name, instead of letting it click into a wall
and silently fail. Detection is fact; solving is out of scope.
"""

from __future__ import annotations

from sin_browser_tools.core import manager
from sin_browser_tools.core.result import ok


# Known DOM signatures of common anti-bot systems.
_SIGNATURES = {
    "recaptcha": [
        "iframe[src*='recaptcha']",
        "div.g-recaptcha",
        "#recaptcha",
    ],
    "hcaptcha": [
        "iframe[src*='hcaptcha']",
        "div.h-captcha",
    ],
    "turnstile": [
        "iframe[src*='challenges.cloudflare.com']",
        "div.cf-turnstile",
    ],
    "datadome": [
        "iframe[src*='captcha-delivery.com']",
        "#datadome",
    ],
    "cloudflare_challenge": [
        "#challenge-running",
        "#cf-challenge-running",
    ],
}

_TITLE_HINTS = (
    "just a moment",
    "attention required",
    "verify you are human",
    "are you a robot",
)


async def browser_detect_captcha() -> dict:
    """Scan the current page for known CAPTCHA / anti-bot systems.

    Returns ``ok=True`` always (detection succeeded); the meaningful field is
    ``captcha_present``. ``detections`` lists provider + matched selector so the
    finding is auditable.
    """
    page = manager.page
    detected: list[dict] = []

    for provider, selectors in _SIGNATURES.items():
        for sel in selectors:
            try:
                el = await page.query_selector(sel)
            except Exception:
                continue
            if el:
                detected.append({"provider": provider, "selector": sel})
                break

    try:
        title = (await page.title() or "").lower()
        if any(hint in title for hint in _TITLE_HINTS):
            detected.append(
                {"provider": "interstitial", "selector": "title", "title": title}
            )
    except Exception:
        pass

    advice = (
        "Agent cannot solve this automatically. Options: (1) restore a saved "
        "auth state / cookies to skip the challenge, (2) plug in a solver "
        "service, (3) report the task as blocked. Do NOT keep clicking."
        if detected
        else "No CAPTCHA detected -- safe to proceed."
    )

    return ok(
        status="scanned",
        captcha_present=bool(detected),
        detections=detected,
        advice=advice,
    )
