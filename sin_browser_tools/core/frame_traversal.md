# `frame_traversal.py`

Unified frame traversal for OOPIFs (out-of-process iframes) and shadow DOM.

## `FrameInfo` Dataclass

Represents metadata about a single frame.

| Field | Type | Description |
|-------|------|-------------|
| `url` | str | Frame URL |
| `name` | str | Frame name attribute |
| `is_main` | bool | True if main frame |
| `parent_url` | str | Parent frame's URL |
| `frame_type` | str | "main", "same_process", "oopif", "error" |
| `ax_tree` | dict | Accessibility tree (if collected) |
| `shadow_roots` | list | Detected shadow roots |
| `error` | str | Error message if traversal failed |
| `html_length` | int | Length of frame's HTML |
| `frame` | Frame | Playwright Frame object (for CDP binding) |

## `UnifiedFrameTraverser`

Traverses all frames on a page, collecting accessibility trees and metadata.

### Usage

```python
traverser = UnifiedFrameTraverser(page)
frames = await traverser.traverse(
    include_ax_tree=True,
    pierce_shadow=True,
    max_depth=10
)
# frames: List[FrameInfo]
```

### OOPIF Detection

OOPIFs run in a separate process and require CDP sessions bound to their
specific frame. The traverser detects them via URL origin comparison and
collects their accessibility trees separately.

### Shadow DOM

When `pierce_shadow=True`, the traverser descends into open shadow roots
to find elements invisible to the normal DOM tree.

## Integration

Used by:
- `browser_snapshot_full_oopif` (accessibility.py)
- `browser_snapshot_in_frame` (frames.py)
- `SmartBrowserTools.deep_snapshot` (smart_tools.py)
