---
name: Bug Report
about: Report a bug or unexpected behavior
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description
A clear and concise description of what the bug is.

## Steps to Reproduce
1. Call `browser_...`
2. With parameters: `...`
3. See error

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened. Include error messages if any.

## Minimal Reproducible Example
```python
import asyncio
from sin_browser_tools.core import manager
from sin_browser_tools.tools import navigation

async def main():
    await manager.start_local()
    # Your code that reproduces the bug
    await manager.cleanup()

asyncio.run(main())
```

## Environment
- OS: [e.g., Ubuntu 22.04, macOS 14, Windows 11]
- Python version: [e.g., 3.11.4]
- SIN-Browser-Tools version: [e.g., 2.1.0 or commit hash]
- Playwright version: [e.g., 1.40.0]

## Additional Context
- Screenshots if applicable
- Browser console errors
- Relevant logs from `.sin_traces/` if tracing was enabled
