"""Network wait tools -- block until a specific request/response happens.

Before this module the only waiters were DOM/text/load based. An agent that
clicks "Save" and needs to know the API call actually returned 200 had no way
to *wait for and inspect that exact response* -- it had to guess with sleeps.
These tools wait on the real network event and return its concrete data.

``url_substring`` matches if the given string is contained in the request URL.
``method`` (optional) further narrows to GET/POST/etc.
"""

from __future__ import annotations

from sin_browser_tools.core import manager


def _matcher(url_substring: str, method: str | None):
    method_u = method.upper() if method else None

    def _match(req_or_resp) -> bool:
        try:
            request = getattr(req_or_resp, "request", req_or_resp)
            if url_substring not in request.url:
                return False
            if method_u and request.method.upper() != method_u:
                return False
            return True
        except Exception:
            return False

    return _match


async def browser_wait_for_response(
    url_substring: str,
    method: str | None = None,
    timeout_ms: int = 30000,
):
    """Wait until a response whose URL contains ``url_substring`` arrives.

    Returns status, URL, HTTP status code, the response headers and -- when the
    body is JSON or text -- a truncated preview, so the agent can *verify* the
    backend actually answered instead of assuming it did.
    """
    page = manager.page
    try:
        response = await page.wait_for_response(
            _matcher(url_substring, method), timeout=timeout_ms
        )
    except Exception as e:
        return {
            "status": "timeout",
            "error": f"No matching response within {timeout_ms}ms: {e}",
            "url_substring": url_substring,
            "method": method,
        }

    body_preview = None
    content_type = ""
    try:
        headers = await response.all_headers()
        content_type = headers.get("content-type", "")
        if any(t in content_type for t in ("json", "text", "xml", "javascript")):
            raw = await response.text()
            body_preview = raw[:2000]
    except Exception:
        headers = {}

    return {
        "status": "found",
        "url": response.url,
        "http_status": response.status,
        "ok_http": response.ok,
        "content_type": content_type,
        "headers": headers,
        "body_preview": body_preview,
    }


async def browser_wait_for_request(
    url_substring: str,
    method: str | None = None,
    timeout_ms: int = 30000,
):
    """Wait until a request whose URL contains ``url_substring`` is sent.

    Useful to confirm the page actually fired an API call (e.g. analytics, save,
    autocomplete) after an interaction. Returns the request method, URL and
    POST body when present.
    """
    page = manager.page
    try:
        request = await page.wait_for_request(
            _matcher(url_substring, method), timeout=timeout_ms
        )
    except Exception as e:
        return {
            "status": "timeout",
            "error": f"No matching request within {timeout_ms}ms: {e}",
            "url_substring": url_substring,
            "method": method,
        }

    post_data = None
    try:
        post_data = request.post_data
    except Exception:
        pass

    return {
        "status": "found",
        "url": request.url,
        "method": request.method,
        "post_data": post_data,
        "resource_type": request.resource_type,
    }
