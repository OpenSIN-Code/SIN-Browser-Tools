"""OpenSIN skill registry.

This used to be a hand-maintained list of tools, which drifted out of sync with
the real implementation (wrong/invalid names, missing tools). It is now derived
directly from the central :mod:`sin_browser_tools.tools.catalog`, so the skill
registry can never disagree with the tools the MCP server actually exposes.
"""

from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List

from .tools import catalog


@dataclass
class ToolAction:
    name: str
    description: str
    category: str
    params: Dict[str, Any]
    enabled: bool = True
    tags: List[str] = field(default_factory=list)


# Map a tool name to its category for nicer grouping in the registry output.
_CATEGORY_BY_PREFIX = {
    "navigate": "navigation",
    "back": "navigation",
    "forward": "navigation",
    "reload": "navigation",
    "scroll": "navigation",
    "press": "navigation",
    "get_url": "navigation",
    "set_viewport": "navigation",
    "wait": "navigation",
    "list_tabs": "navigation",
    "new_tab": "navigation",
    "switch_tab": "navigation",
    "close_tab": "navigation",
    "click": "interaction",
    "double_click": "interaction",
    "right_click": "interaction",
    "hover": "interaction",
    "drag": "interaction",
    "select_option": "interaction",
    "check": "interaction",
    "type": "interaction",
    "fill": "interaction",
    "upload_file": "interaction",
    "snapshot": "accessibility",
    "vision": "vision",
    "screenshot": "vision",
    "pdf": "vision",
    "get_images": "vision",
    "get_text": "vision",
    "dialog": "dialog",
    "wait_for_dialog": "dialog",
    "console": "extraction",
    "cdp": "extraction",
    "get_cookies": "extraction",
    "set_cookie": "extraction",
    "clear_cookies": "extraction",
    "get_html": "extraction",
    "get_links": "extraction",
    "get_attribute": "extraction",
    "storage": "extraction",
    "list_tools": "meta",
}


def _category_for(tool_name: str) -> str:
    action = tool_name[len("browser_"):] if tool_name.startswith("browser_") else tool_name
    for prefix, cat in _CATEGORY_BY_PREFIX.items():
        if action == prefix or action.startswith(prefix):
            return cat
    return "misc"


class SINBrowserSkill:
    def __init__(self):
        self.actions: Dict[str, ToolAction] = {}
        for spec in catalog.specs():
            name = spec["name"]
            params = {
                pname: {
                    "type": pinfo.get("type", "string"),
                    "required": pname in spec["required"],
                }
                for pname, pinfo in spec["parameters"].items()
            }
            self.actions[name] = ToolAction(
                name=name,
                description=spec["description"],
                category=_category_for(name),
                params=params,
            )

    def to_opensin_registry(self) -> Dict[str, Any]:
        return {
            "skill": "sin-browser-tools",
            "version": "0.1.0",
            "count": len(self.actions),
            "actions": {name: asdict(action) for name, action in self.actions.items()},
        }


skill = SINBrowserSkill()


def init_opensin_integration():
    return skill
