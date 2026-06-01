"""Tools fuer parallele, isolierte Browser-Sessions (Multi-Context).

Eine "Session" ist ein eigener BrowserContext mit komplett getrennten Cookies,
localStorage, sessionStorage und Auth -- anders als Tabs (browser_new_tab), die
sich denselben Cookie-Jar teilen.

    browser_create_session, browser_list_sessions, browser_switch_session,
    browser_close_session, browser_parallel_navigate

Typische Use-Cases:
  - eingeloggt vs. ausgeloggt gleichzeitig pruefen
  - dieselbe Seite mit zwei Accounts vergleichen (A/B)
  - mehrere Suchen parallel ausfuehren
"""

from sin_browser_tools.core import manager


async def browser_create_session(name: str) -> dict:
    """Neue isolierte Session (eigener Cookie-/Storage-Jar) anlegen.

    Args:
        name: eindeutiger Name, z.B. "admin", "guest", "accountB".

    Returns:
        {"status":"ok","name":...} oder {"status":"error","error":...}.
        Fehlt ein echter Browser (persistent user_data_dir), kommt ein klarer
        Hinweis, stattdessen Tabs zu nutzen.
    """
    return await manager.sessions.create_context(name)


async def browser_list_sessions() -> dict:
    """Alle Sessions auflisten (Name, aktiv-Flag, Tab-Anzahl, aktuelle URL)."""
    return manager.sessions.list_contexts()


async def browser_switch_session(name: str) -> dict:
    """Aktive Session wechseln.

    Danach operieren ALLE anderen Tools (navigate, click, fill, snapshot, ...)
    auf dieser Session. @eN-Refs aus der vorherigen Session werden verworfen ->
    nach dem Wechsel neu browser_snapshot aufrufen.
    """
    return await manager.sessions.switch_context(name)


async def browser_close_session(name: str) -> dict:
    """Eine Session schliessen (alle ihre Tabs). Wird die aktive Session
    geschlossen, wechselt der Manager automatisch auf eine verbleibende.
    Die 'default'-Session kann erst geschlossen werden, wenn keine andere
    mehr offen ist.
    """
    return await manager.sessions.close_context(name)


async def browser_parallel_navigate(sessions: list, timeout: float = 30000) -> dict:
    """Mehrere Sessions GLEICHZEITIG zu URLs navigieren.

    Args:
        sessions: Liste von {"name": str, "url": str}. Nicht existierende
            Sessions werden automatisch angelegt.
        timeout: pro Navigation, in Millisekunden.

    Returns:
        {"status":"ok","results":[{name,status,url,title}|{name,status:'error',error}]}.
        Die vorher aktive Session bleibt aktiv.

    Beispiel:
        await browser_parallel_navigate([
            {"name": "google", "url": "https://www.google.com/search?q=playwright"},
            {"name": "bing",   "url": "https://www.bing.com/search?q=playwright"},
        ])
        # -> beide Suchen laufen parallel in isolierten Sessions
    """
    return await manager.sessions.parallel_navigate(sessions, timeout=timeout)
