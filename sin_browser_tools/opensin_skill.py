import json
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

@dataclass
class ToolAction:
    name: str
    description: str
    category: str
    params: Dict[str, Any]
    enabled: bool = True
    tags: list = None

class SINBrowserSkill:
    TOOL_DEFINITIONS = [
        ToolAction("browser/snapshot", "Get accessibility tree with Ref-IDs", "accessibility", {}),
        ToolAction("browser/navigate", "Navigate to URL", "navigation", {"url": {"type": "string", "required": True}}),
        ToolAction("browser/back", "Go back in history", "navigation", {}),
        ToolAction("browser/scroll", "Scroll page", "navigation", {"direction": {"type": "string", "enum": ["up", "down"]}, "amount": {"type": "integer"}}),
        ToolAction("browser/press", "Press keyboard key", "navigation", {"key": {"type": "string", "required": True}}),
        ToolAction("browser/click", "Click element", "interaction", {"target": {"type": "string", "required": True}}),
        ToolAction("browser/type", "Type text", "interaction", {"target": {"type": "string", "required": True}, "text": {"type": "string", "required": True}}),
        ToolAction("browser/fill", "Fill input", "interaction", {"target": {"type": "string", "required": True}, "value": {"type": "string", "required": True}}),
        ToolAction("browser/upload", "Upload file", "interaction", {"target": {"type": "string", "required": True}, "file_path": {"type": "string", "required": True}}),
        ToolAction("browser/screenshot", "Take screenshot", "vision", {}),
        ToolAction("browser/images", "List images", "vision", {}),
        ToolAction("browser/text", "Extract text", "vision", {}),
        ToolAction("browser/dialog", "Handle JS dialog", "dialog", {"action": {"type": "string", "enum": ["accept", "dismiss"]}}),
        ToolAction("browser/wait-dialog", "Wait for dialog", "dialog", {}),
        ToolAction("browser/console", "Execute JavaScript", "extraction", {"expression": {"type": "string", "required": True}}),
        ToolAction("browser/cdp", "Send CDP command", "extraction", {"method": {"type": "string", "required": True}}),
    ]
    
    def __init__(self):
        self.actions = {action.name: action for action in self.TOOL_DEFINITIONS}
    
    def to_opensin_registry(self) -> Dict[str, Any]:
        return {
            "skill": "sin-browser-tools",
            "version": "0.1.0",
            "actions": {action.name: asdict(action) for action in self.TOOL_DEFINITIONS}
        }

skill = SINBrowserSkill()
def init_opensin_integration():
    return skill
