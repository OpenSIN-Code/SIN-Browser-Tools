"""Frame-scoped tools: list frames, eval in a frame, and a shadow-piercing
snapshot scoped to a single frame.

Why this module exists (Issue #11):
    Sites like GMX render their mail list inside a *same-process* iframe
    (``webmailer.gmx.net``) whose rows are custom elements (``list-mail-item``)
    nested several levels deep in **open shadow DOM**. The accessibility-tree
    snapshot (``browser_snapshot`` / ``browser_snapshot_full_oopif``) cannot see
    those rows: custom elements expose no ARIA role, so ``getFullAXTree`` returns
    almost nothing and ``document.querySelectorAll('list-mail-item')`` finds 0
    items (it does not pierce shadow roots).

    These tools provide the two escape hatches the issue asks for:
      1. ``browser_eval_in_frame``    -> run arbitrary JS in a named/URL-matched
         frame (the generic ``frame.evaluate`` the workaround used).
      2. ``browser_snapshot_in_frame`` -> walk the DOM of a single frame while
         **piercing open shadow roots** (and, optionally, nested same-origin
         child iframes), returning the matched elements' text/tag so an agent can
         actually read shadow-DOM content like email subjects.
"""

import re

from sin_browser_tools.core import manager

# ---------------------------------------------------------------------------
# Shadow-piercing DOM walker, injected into the target frame.
#
# Standard querySelectorAll does NOT cross shadow boundaries, so we recurse
# manually: at every root we match `selector` (or collect text-bearing leaf-ish
# elements when no selector is given), then descend into each element's OPEN
# shadowRoot. Closed shadow roots are inaccessible by design and are reported via
# `closedShadowHosts` so the caller knows content may be hidden.
# ---------------------------------------------------------------------------
_WALK_JS = r"""
(args) => {
  const { selector, pierceShadow, pierceIframes, minLen, maxLen, maxItems, maxDepth } = args;
  const items = [];
  let closedShadowHosts = 0;
  let openShadowRoots = 0;
  let truncated = false;

  const pushEl = (el, depth) => {
    if (items.length >= maxItems) { truncated = true; return; }
    let raw = el.innerText || el.textContent || '';
    // Custom elements (e.g. <list-mail-item>) render their content INSIDE their
    // own shadow root, so the host's light-DOM text is empty. Fall back to the
    // open shadow root's text so subjects/labels are actually returned.
    if (!raw.trim() && pierceShadow && el.shadowRoot && el.shadowRoot.mode === 'open') {
      raw = el.shadowRoot.textContent || '';
    }
    const text = raw.replace(/\s+/g, ' ').trim();
    if (!selector) {
      // Heuristic "readable content" mode: only keep elements whose own text is
      // within bounds, mirroring the issue's working workaround.
      if (text.length < minLen || text.length > maxLen) return;
    }
    items.push({
      tag: el.tagName ? el.tagName.toLowerCase() : '(unknown)',
      id: el.id || null,
      classes: el.classList ? Array.from(el.classList).slice(0, 6) : [],
      text: text.slice(0, maxLen),
      shadow_depth: depth,
    });
  };

  const walk = (root, depth) => {
    if (!root || depth > maxDepth || items.length >= maxItems) return;
    // Iterate EVERY element at this root so shadow descent is independent of
    // selector matching: e.g. <list-mail-item> lives inside the shadowRoot of
    // <mail-list-container>, which itself does NOT match selector. If we only
    // descended into matched elements we'd never reach the rows.
    let all;
    try {
      all = root.querySelectorAll('*');
    } catch (e) {
      return;
    }
    let matchSet = null;
    if (selector) {
      try {
        matchSet = new Set(root.querySelectorAll(selector));
      } catch (e) {
        return; // invalid selector
      }
    }
    all.forEach((el) => {
      if (selector) {
        if (matchSet.has(el)) pushEl(el, depth);
      } else if (el.childElementCount === 0) {
        // "all readable" mode: only leaf-ish nodes so we don't emit a container
        // AND its contents.
        pushEl(el, depth);
      }
      if (pierceShadow && el.shadowRoot) {
        if (el.shadowRoot.mode === 'open') {
          openShadowRoots++;
          walk(el.shadowRoot, depth + 1);
        } else {
          closedShadowHosts++;
        }
      }
    });
  };

  if (document.body) walk(document.body, 0);

  // Optionally descend into same-origin child iframes within this frame.
  let nestedIframeNote = null;
  if (pierceIframes) {
    const iframes = Array.from(document.querySelectorAll('iframe'));
    let blocked = 0;
    for (const ifr of iframes) {
      try {
        const doc = ifr.contentDocument;
        if (doc && doc.body) walk(doc.body, 0);
        else blocked++;
      } catch (e) {
        blocked++; // cross-origin: not reachable from JS, use frame_url targeting
      }
    }
    if (blocked > 0) {
      nestedIframeNote =
        blocked + ' nested iframe(s) were cross-origin and not reachable from ' +
        'this frame; target them directly via frame_url.';
    }
  }

  return {
    items,
    count: items.length,
    truncated,
    open_shadow_roots: openShadowRoots,
    closed_shadow_hosts: closedShadowHosts,
    nested_iframe_note: nestedIframeNote,
  };
}
"""


def _frame_descriptor(frame) -> dict:
    """Compact, JSON-safe description of a Playwright frame."""
    return {
        "name": frame.name or "",
        "url": frame.url or "",
        "is_main": frame.parent_frame is None,
        "parent_url": frame.parent_frame.url if frame.parent_frame else None,
    }


def _resolve_frame(frame_name: str = None, frame_url: str = None):
    """Find a frame by exact name or by URL substring.

    Returns ``(frame, error)``. Exactly one of name/url should be given; if
    neither is given the main frame is returned (so callers get a sane default).
    """
    page = manager.page
    if frame_name:
        for f in page.frames:
            if (f.name or "") == frame_name:
                return f, None
        return None, f"No frame with name={frame_name!r}. Call browser_list_frames to see available frames."
    if frame_url:
        needle = frame_url.lower()
        # Prefer the most-specific (longest URL) match for determinism.
        matches = [f for f in page.frames if needle in (f.url or "").lower()]
        if not matches:
            return None, f"No frame whose URL contains {frame_url!r}. Call browser_list_frames to see available frames."
        matches.sort(key=lambda f: len(f.url or ""), reverse=True)
        return matches[0], None
    return page.main_frame, None


async def browser_list_frames() -> dict:
    """List every frame (iframe) on the page with its name, URL and parent.

    Use this to discover frames before calling ``browser_eval_in_frame`` or
    ``browser_snapshot_in_frame``. On webmail apps like GMX/web.de the message
    list lives in a child frame (e.g. name ``mail`` / URL ``webmailer.gmx.net``)
    rather than the main document, so target that frame's name or URL.
    """
    page = manager.page
    frames = [_frame_descriptor(f) for f in page.frames]
    return {"count": len(frames), "frames": frames}


async def browser_eval_in_frame(
    expression: str, frame_name: str = None, frame_url: str = None
) -> dict:
    """Evaluate a JavaScript expression inside a specific frame (not the main page).

    Provide ``frame_name`` (exact iframe name) OR ``frame_url`` (substring of the
    frame URL, e.g. ``"webmailer.gmx.net"``). With neither, the main frame is
    used. This is the escape hatch for shadow-DOM walking inside same-process
    iframes that the accessibility snapshot cannot reach.

    The expression runs as a frame-context function body/expression, exactly like
    Playwright's ``frame.evaluate`` (e.g. ``"document.title"`` or a full
    ``"() => {...}"`` arrow function).
    """
    frame, error = _resolve_frame(frame_name, frame_url)
    if error:
        return {"error": error}
    try:
        result = await frame.evaluate(expression)
        return {
            "frame": _frame_descriptor(frame),
            "type": type(result).__name__,
            "result": result,
        }
    except Exception as e:
        return {"error": str(e), "frame": _frame_descriptor(frame)}


async def browser_snapshot_in_frame(
    frame_name: str = None,
    frame_url: str = None,
    selector: str = None,
    pierce_shadow: bool = True,
    pierce_iframes: bool = False,
    min_text_len: int = 3,
    max_text_len: int = 300,
    max_items: int = 500,
) -> dict:
    """Shadow-DOM-piercing snapshot scoped to ONE frame (Issue #11).

    Reads content the accessibility snapshot misses: custom elements nested in
    open shadow DOM inside a same-process iframe (e.g. GMX ``list-mail-item``
    email rows). Walks the target frame's DOM, descends into every OPEN
    ``shadowRoot``, and returns the matched elements' tag/id/classes/text.

    Targeting:
      - ``frame_name`` -- exact iframe name (e.g. ``"mail"``).
      - ``frame_url``  -- substring of the frame URL (e.g. ``"webmailer.gmx.net"``).
      - neither        -- the main frame.
      Discover frames first with ``browser_list_frames``.

    Selection:
      - ``selector`` -- CSS selector matched at every shadow level (e.g.
        ``"list-mail-item"``). When omitted, every leaf element whose own text is
        between ``min_text_len`` and ``max_text_len`` chars is returned (good for
        a first read of unknown shadow content).
      - ``pierce_shadow`` -- recurse into open shadow roots (default True).
      - ``pierce_iframes`` -- also descend into same-origin child iframes of the
        target frame (default False; cross-origin children must be targeted
        directly via ``frame_url``).

    Closed shadow roots are inaccessible by design; their host count is reported
    in ``closed_shadow_hosts`` so you know content may remain hidden.
    """
    frame, error = _resolve_frame(frame_name, frame_url)
    if error:
        return {"error": error}

    args = {
        "selector": selector,
        "pierceShadow": pierce_shadow,
        "pierceIframes": pierce_iframes,
        "minLen": min_text_len,
        "maxLen": max_text_len,
        "maxItems": max_items,
        "maxDepth": 12,
    }
    try:
        data = await frame.evaluate(_WALK_JS, args)
    except Exception as e:
        return {"error": str(e), "frame": _frame_descriptor(frame)}

    result = {
        "frame": _frame_descriptor(frame),
        "selector": selector,
        "count": data.get("count", 0),
        "items": data.get("items", []),
        "open_shadow_roots": data.get("open_shadow_roots", 0),
        "closed_shadow_hosts": data.get("closed_shadow_hosts", 0),
        "truncated": data.get("truncated", False),
        "method": "frame_dom_walk_pierce" if pierce_shadow else "frame_dom_walk",
    }

    hints = []
    if data.get("count", 0) == 0:
        hints.append(
            "No elements matched in this frame. Verify the frame target with "
            "browser_list_frames, and remember closed shadow roots are not "
            "readable."
        )
    if data.get("closed_shadow_hosts"):
        hints.append(
            f"{data['closed_shadow_hosts']} closed shadow root(s) were skipped "
            "(content inside them cannot be read from JS)."
        )
    if data.get("nested_iframe_note"):
        hints.append(data["nested_iframe_note"])
    if data.get("truncated"):
        hints.append(
            f"Result truncated at max_items={max_items}; raise max_items or pass "
            "a more specific selector."
        )
    if hints:
        result["hint"] = " ".join(hints)
        result["hints"] = hints
    return result


# ---------------------------------------------------------------------------
# browser_click_in_frame — click a (shadow-DOM) element inside ONE frame
# (Issue #12: GMX/web.de mail rows are <list-mail-item> custom elements nested
# in OPEN shadow DOM inside a same-process "mail" iframe; browser_click /
# browser_click_by_text operate on the main page's snapshot registry and never
# reach them).
# ---------------------------------------------------------------------------

async def browser_click_in_frame(
    selector: str,
    frame_name: str = None,
    frame_url: str = None,
    index: int = 0,
    text: str = None,
    timeout_ms: int = 5000,
) -> dict:
    """Click an element inside a specific frame, piercing OPEN shadow DOM (Issue #12).

    This is the click counterpart to ``browser_snapshot_in_frame``. It targets
    the GMX/web.de case where message rows are custom elements
    (e.g. ``list-mail-item``) nested in open shadow DOM inside a same-process
    ``mail`` iframe, which the main-page click tools cannot reach.

    Playwright's CSS locator engine pierces OPEN shadow roots automatically and
    routes the click into the correct (possibly cross-origin) frame, so this is
    far more reliable than ``element.click()`` via ``evaluate`` (which silently
    fails on many shadow-DOM elements).

    Targeting:
      - ``selector`` -- CSS selector for the element(s) to click
        (e.g. ``"list-mail-item"``). Required.
      - ``frame_name`` -- exact iframe name (e.g. ``"mail"``).
      - ``frame_url``  -- substring of the frame URL (e.g. ``"webmailer.gmx.net"``).
      - neither name nor url -- the main frame.
      Discover frames first with ``browser_list_frames``.

    Selection among matches:
      - ``text`` -- if given, only elements whose (rendered, shadow-inclusive)
        text contains this substring are considered. Use it as a sender/subject
        filter, e.g. ``text="Invoice"``.
      - ``index`` -- which of the (optionally text-filtered) matches to click,
        0-based (default 0 = first).

    Returns ``{"status": "clicked", "frame": {...}, "selector", "index",
    "match_count", "clicked_text"}`` on success, or ``{"error": ...}`` with a
    hint (e.g. when nothing matched or the index is out of range).
    """
    frame, error = _resolve_frame(frame_name, frame_url)
    if error:
        return {"error": error}

    try:
        locator = frame.locator(selector)
        if text:
            locator = locator.filter(has_text=text)

        match_count = await locator.count()
        if match_count == 0:
            return {
                "error": (
                    f"No element matched selector {selector!r}"
                    + (f" with text containing {text!r}" if text else "")
                    + " in this frame."
                ),
                "frame": _frame_descriptor(frame),
                "hint": (
                    "Verify the frame with browser_list_frames and the selector "
                    "with browser_snapshot_in_frame. Remember: closed shadow "
                    "roots are not reachable."
                ),
            }
        if index < 0 or index >= match_count:
            return {
                "error": (
                    f"index {index} is out of range; {match_count} element(s) "
                    f"matched {selector!r}"
                    + (f" with text {text!r}" if text else "")
                    + "."
                ),
                "frame": _frame_descriptor(frame),
                "match_count": match_count,
            }

        target = locator.nth(index)
        try:
            await target.scroll_into_view_if_needed(timeout=timeout_ms)
        except Exception:
            pass  # best-effort; click still hit-tests + auto-scrolls

        # Capture the row's text before clicking, for an observable result the
        # agent can confirm against. Custom elements render their content inside
        # a shadow root, so inner_text() on the host is empty -- read the open
        # shadow root too (this is the GMX <list-mail-item> case).
        try:
            clicked_text = await target.evaluate(
                """(el) => {
                    let t = (el.innerText || el.textContent || '');
                    if (!t.trim() && el.shadowRoot) {
                        t = el.shadowRoot.textContent || '';
                    }
                    return t.replace(/\\s+/g, ' ').trim().slice(0, 120);
                }"""
            )
        except Exception:
            clicked_text = None

        await target.click(timeout=timeout_ms)
        return {
            "status": "clicked",
            "frame": _frame_descriptor(frame),
            "selector": selector,
            "index": index,
            "match_count": match_count,
            "clicked_text": clicked_text,
            "method": "frame_locator_pierce",
        }
    except Exception as e:
        return {"error": str(e), "frame": _frame_descriptor(frame)}


# ---------------------------------------------------------------------------
# browser_scan_frames — scan ALL frames for text content (Issue #15)
# ---------------------------------------------------------------------------

async def browser_scan_frames(
    pattern: str = None,
    regex: str = None,
    include_empty: bool = False,
    max_text_len: int = 5000,
) -> dict:
    """Scan ALL frames on the current page for text content.

    This is the tool for pages (like GMX webmailer) where content lives in an
    unnamed, URL-less `about:blank` iframe that cannot be targeted by name or URL.
    Instead of guessing which frame to target, this tool iterates every frame,
    extracts its text, and optionally filters by pattern/regex.

    Args:
        pattern: Substring to search for (case-insensitive). If provided, only
                 frames whose text contains this substring are returned.
        regex: Regex pattern to search for. If provided, only frames whose text
               matches this regex are returned. Takes precedence over pattern.
        include_empty: If True, include frames with no/empty text in results.
        max_text_len: Truncate each frame's text to this length (default 5000).

    Returns:
        dict with:
          - total_frames: Number of frames on the page
          - matching_frames: Number of frames that matched (or all if no filter)
          - frames: List of matching frame info dicts, each with:
              - index: Frame index in page.frames
              - name: Frame name (may be empty)
              - url: Frame URL (may be 'about:blank' or empty)
              - text: Extracted text (truncated to max_text_len)
              - text_length: Full text length before truncation
              - matches: List of match strings (if pattern/regex provided)
          - hint: Guidance if no frames matched

    Use case (GMX email body):
        After clicking an email, the body loads in an unnamed iframe. Use:
          browser_scan_frames(pattern="verify") to find OTP verification URLs
          browser_scan_frames(regex=r"\\d{6}") to find 6-digit OTP codes
    """
    page = manager.page
    frames = page.frames
    results = []
    compiled_regex = None

    if regex:
        try:
            compiled_regex = re.compile(regex, re.IGNORECASE | re.MULTILINE)
        except re.error as e:
            return {"error": f"Invalid regex: {e}"}

    for idx, frame in enumerate(frames):
        try:
            # Try multiple extraction methods for robustness
            text = await frame.evaluate(
                "() => document.body ? document.body.innerText || document.body.textContent || '' : ''"
            )
        except Exception:
            # Frame may be cross-origin or detached
            text = ""

        text_length = len(text)
        if not include_empty and not text.strip():
            continue

        matches = []
        if compiled_regex:
            matches = compiled_regex.findall(text)
            if not matches:
                continue
        elif pattern:
            if pattern.lower() not in text.lower():
                continue
            # Find all occurrences for context
            lower_text = text.lower()
            lower_pattern = pattern.lower()
            pos = 0
            while True:
                pos = lower_text.find(lower_pattern, pos)
                if pos == -1:
                    break
                # Extract match with context (50 chars before/after)
                start = max(0, pos - 50)
                end = min(len(text), pos + len(pattern) + 50)
                matches.append(text[start:end])
                pos += 1

        frame_info = {
            "index": idx,
            "name": frame.name or "",
            "url": frame.url or "",
            "text": text[:max_text_len] + ("..." if text_length > max_text_len else ""),
            "text_length": text_length,
        }
        if matches:
            frame_info["matches"] = matches[:20]  # Limit matches
            frame_info["match_count"] = len(matches) if len(matches) <= 20 else "20+ (showing first 20)"
        results.append(frame_info)

    result = {
        "total_frames": len(frames),
        "matching_frames": len(results),
        "frames": results,
    }

    if not results:
        hints = []
        if pattern or regex:
            hints.append(
                f"No frames contained {'regex ' + repr(regex) if regex else 'pattern ' + repr(pattern)}. "
                "Try browser_scan_frames() without a filter to see all frame contents, "
                "or wait for the content to load with browser_wait."
            )
        else:
            hints.append(
                "All frames were empty. The page may still be loading — try "
                "browser_wait, then browser_scan_frames again."
            )
        result["hint"] = " ".join(hints)
        result["hints"] = hints

    return result
