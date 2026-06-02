"""Structured extraction tools -- return tables and lists as structured data
instead of raw text the agent has to parse itself.

Parsing free-form innerText is exactly where agents hallucinate. These tools do
the DOM walking in the page and hand back ``list[dict]`` the agent can use
directly.
"""

from __future__ import annotations

from typing import Optional

from sin_browser_tools.core import manager
from sin_browser_tools.core.result import ok, err


_TABLE_JS = """
(args) => {
  const { sel, idx } = args;
  const tables = [...document.querySelectorAll(sel)];
  const t = tables[idx];
  if (!t) return { __error: 'table not found' };
  const headerCells = [...t.querySelectorAll('thead th, thead td')];
  let headers = headerCells.map(c => c.innerText.trim());
  const bodyRows = [...t.querySelectorAll('tbody tr')];
  const rows = bodyRows.length ? bodyRows : [...t.querySelectorAll('tr')];
  if (!headers.length && rows.length) {
    headers = [...rows[0].children].map(c => c.innerText.trim());
  }
  const start = headers.length && !bodyRows.length ? 1 : 0;
  const out = [];
  for (let i = start; i < rows.length; i++) {
    const cells = [...rows[i].children].map(c => c.innerText.trim());
    const obj = {};
    cells.forEach((v, j) => { obj[headers[j] || ('col' + j)] = v; });
    out.push(obj);
  }
  return { headers, rows: out };
}
"""

_LIST_JS = """
(args) => {
  const { sel, fields } = args;
  const items = [...document.querySelectorAll(sel)];
  return items.map(it => {
    if (!fields) return { text: it.innerText.trim() };
    const obj = {};
    for (const [k, q] of Object.entries(fields)) {
      const el = it.querySelector(q);
      obj[k] = el
        ? (el.innerText || el.getAttribute('content') ||
           el.getAttribute('href') || '').trim()
        : null;
    }
    return obj;
  });
}
"""


async def browser_extract_table(
    table_selector: str = "table",
    index: int = 0,
) -> dict:
    """Extract one HTML table as ``list[dict]`` (header -> cell value).

    ``table_selector`` selects the table(s); ``index`` picks which match. Header
    detection falls back to the first row if there is no ``<thead>``.
    """
    page = manager.page
    result = await page.evaluate(
        _TABLE_JS, {"sel": table_selector, "idx": index}
    )
    if isinstance(result, dict) and result.get("__error"):
        return err(
            result["__error"],
            status="not_found",
            selector=table_selector,
            index=index,
        )
    return ok(
        status="extracted",
        headers=result.get("headers", []),
        rows=result.get("rows", []),
        row_count=len(result.get("rows", [])),
    )


async def browser_extract_list(
    item_selector: str,
    fields: Optional[dict] = None,
) -> dict:
    """Extract repeated elements as ``list[dict]``.

    ``item_selector`` matches each repeated item. ``fields`` maps an output key
    to a CSS selector relative to the item, e.g.
    ``{"title": "h3", "price": ".price", "link": "a"}``. For link/meta elements
    the value falls back to ``href`` / ``content``. Without ``fields`` each
    item's trimmed ``innerText`` is returned.
    """
    page = manager.page
    items = await page.evaluate(
        _LIST_JS, {"sel": item_selector, "fields": fields}
    )
    return ok(status="extracted", items=items, count=len(items))
