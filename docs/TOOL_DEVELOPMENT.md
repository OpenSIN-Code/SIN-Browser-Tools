# Tool Development Best Practices

This guide covers how to develop, document, and evolve tools in SIN-Browser-Tools.
The goal is **predictable interfaces** that agents and tests can reliably depend on.

---

## 1. Return Contract Design

Every tool returns a **dict** (never throws). This allows agents to handle success and
error uniformly without try/catch boilerplate.

### Rule 1: Always include a status key

Every return path must carry a **`status`** key that classifies the outcome.

**Common status values:**
- **Success states:** `found`, `ok`, `ready`, `set`, `cleared`, `dismissed`
- **Timeout/retry states:** `timeout`, `pending`
- **Error states:** `error`, `no_dialog_pending`, `no_match`

```python
# ✅ Good: status on success
return {"status": "found", "element": ..., "matchCount": 1}

# ✅ Good: status on timeout
return {"status": "timeout", "error": "Text did not appear within 5000ms"}

# ✅ Good: status on error
return {"status": "error", "error": "Frame not found"}

# ❌ Bad: inconsistent, agents can't reliably branch
return {"found": True}  # success
return {"error": "..."}  # timeout — no status key
```

### Rule 2: Evolve contracts additively

When adding new fields to a return dict, **keep existing keys** and add new ones.
Never rename or remove an existing key.

**Why:** Agents and tests check `result["status"]`. Renaming it breaks every caller.

```python
# ❌ Bad: renamed status -> found (Issue #28 regression)
# Old: {"status": "found", "text": "..."}
# New: {"found": True, "text": "..."}  # Breaks all old callers checking ["status"]

# ✅ Good: additive (what we fixed in #28)
# Old: {"status": "found", "text": "..."}
# New: {"status": "found", "found": True, "text": "..."}  # Both keys present
```

### Rule 3: Document the contract

Every tool's **tool doc** (e.g., `sin_browser_tools/tools/dialog.md`) must include
a **Returns** section that lists the return dict keys for each outcome path.

```markdown
### `browser_click(selector, button="left", force=False)`
Click an element on the page (button: "left", "right", "middle").

**Returns:**
- Success: `{"status": "ok", "element": {tag, id, ...}}`
- Error (missing selector): `{"status": "error", "error": "No element matches ..."}`
```

**See also:** [`sin_browser_tools/tools/frames.md`](../sin_browser_tools/tools/frames.md)
for the reference documentation pattern.

---

## 2. Documenting a New Tool

### Checklist

1. **Create the tool file** in `sin_browser_tools/tools/{name}.py`
2. **Export from `__init__.py`** so agents can import it
3. **Create the doc file** `sin_browser_tools/tools/{name}.md`
   - Short description at the top
   - Argument reference for each function (what it does, example call)
   - **Returns section** showing the dict keys for success/error/timeout
   - Example workflow (optional, if the tool is complex)
4. **Add tests** in `tests/test_tool_smoke.py`
   - Happy path (success case)
   - Error case (missing selector, timeout, etc.)
   - Return contract test (assert `status` key is present — see Issue #28)
5. **Update README.md** tool count

### Returns Section Template

```markdown
### `your_function(arg1, arg2)`

Short description.

**Arguments:**
- `arg1` (str): What it is
- `arg2` (int, optional): What it is, default 5000

**Returns:**

Success:
\`\`\`json
{"status": "found", "element": {"tag": "...", "id": "...", "text": "..."}}
\`\`\`

Timeout (if applicable):
\`\`\`json
{"status": "timeout", "error": "Text 'x' did not appear within 5000ms"}
\`\`\`

Error:
\`\`\`json
{"status": "error", "error": "Frame not found: 'main'"}
\`\`\`

**Example:**
\`\`\`python
result = await your_function("some text")
if result["status"] == "found":
    # Process result["element"]
elif result["status"] == "timeout":
    # Handle timeout
else:
    # Handle error
\`\`\`
```

---

## 3. Return Contract Stability (Issue #28 Lesson)

**Never rename or remove an existing key in a released tool's return dict.**

Renaming breaks every agent and test that reads the old key. The fix is to return
**both** the old and new keys (additive contract).

### If you must make a breaking change

1. Open an issue
2. Discuss the impact with the team
3. Bump the version (e.g., from v1.2.0 → v2.0.0)
4. Document the migration in `CHANGELOG.md` under a **`### Changed`** heading
5. Update all tool docs and examples

### Return Contract Test Pattern

Always test **both** the success and failure paths to catch regressions.

```python
async def test_your_function_returns_status_key(live_manager):
    """Regression guard: ensure status key is always present."""
    # Success case
    found = await your_function("target text")
    assert found["status"] == "found"
    assert "element" in found

    # Timeout case
    missing = await your_function("never appears", timeout=500)
    assert missing["status"] == "timeout"
    assert "error" in missing
```

See: [`tests/test_tool_smoke.py::test_wait_for_text_returns_both_status_and_found`](../../tests/test_tool_smoke.py)

---

## 4. Testing Checklist

### For every tool or function

- **Happy path test**: Does the success case work?
- **Error path test**: Does it handle missing inputs gracefully?
- **Return contract test**: Is the `status` key always present?
- **Integration test**: Does it work end-to-end with a real browser?

### Run tests locally before pushing

```bash
python -m pytest tests/test_tool_smoke.py -v
```

---

## 5. Backwards Compatibility Policy

SIN-Browser-Tools follows [Semantic Versioning](https://semver.org/).

- **Patch (v1.2.3):** Bug fixes, doc updates, internal refactors
- **Minor (v1.3.0):** New tools, new args to existing tools (optional), additive return keys
- **Major (v2.0.0):** Return dict restructures, breaking arg removals, renamed tools

**Adding a new optional argument?** It's a minor version bump (backwards compatible).

**Renaming an existing return key?** It's a major version bump (breaking change).

---

## 6. Code Style & Patterns

### Error handling

```python
# ✅ Always return a dict, never raise
async def your_function(selector):
    try:
        result = await page.query_selector(selector)
    except Exception as e:
        return {"status": "error", "error": str(e)}
    
    if not result:
        return {"status": "error", "error": f"No element matches: {selector}"}
    
    return {"status": "ok", "element": {...}}
```

### Type hints

```python
from typing import Any, Dict, Optional

async def your_function(
    text: str,
    timeout: int = 5000,
    frame_name: Optional[str] = None,
) -> Dict[str, Any]:
    """..."""
```

### Docstring format

```python
async def your_function(arg1: str, arg2: int = 5000) -> Dict[str, Any]:
    """
    Short one-liner.
    
    Longer description if needed.
    
    Arguments:
        arg1 (str): What it is
        arg2 (int, optional): What it is, default 5000
    
    Returns:
        On success: {"status": "ok", "result": ...}
        On timeout: {"status": "timeout", "error": "..."}
        On error: {"status": "error", "error": "..."}
    
    Example:
        result = await your_function("text")
        if result["status"] == "ok":
            # Use result["result"]
    """
```

---

## 7. Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| Throwing exceptions instead of returning error dicts | Wrap try/catch, return `{"status": "error", ...}` |
| Forgetting `status` key on error paths | Always include `status` on every return path |
| Renaming an existing key (e.g., `status` → `found`) | Add the new key, keep the old one (additive) |
| Not documenting the return dict in the tool's .md file | Add a **Returns** section with examples for each path |
| Only testing the happy path | Test success, error, and timeout paths |
| Breaking change without updating CHANGELOG | Document in `CHANGELOG.md` under `### Changed` (Major version bump) |

---

## References

- [Return Contract Stability](../CONTRIBUTING.md#return-contract-stability) (CONTRIBUTING.md)
- [Issue #28: browser_wait_for_text regression](https://github.com/OpenSIN-Code/SIN-Browser-Tools/issues/28)
- [frames.md: Reference tool docs](../sin_browser_tools/tools/frames.md)
- [test_tool_smoke.py: Regression guard patterns](../../tests/test_tool_smoke.py)
