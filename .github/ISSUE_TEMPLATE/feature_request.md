---
name: Feature Request
about: Suggest a new tool or enhancement
title: '[FEATURE] '
labels: enhancement
assignees: ''
---

## Problem / Use Case
Describe the problem you're trying to solve or the use case this feature would address.

Example: "When automating GMX webmail, the email body loads in an unnamed iframe that I cannot target..."

## Proposed Solution
Describe the tool or enhancement you'd like to see.

Example: "A `browser_scan_frames(pattern)` tool that searches all frames for text content..."

## API Design (if applicable)
```python
# How you envision calling this tool
result = await browser_new_tool(
    required_param="value",
    optional_param=True,
)
# Expected return structure
{
    "status": "success",
    "data": [...],
}
```

## Alternatives Considered
What workarounds or alternative approaches have you tried?

## Additional Context
- Links to similar features in other tools
- Screenshots or diagrams if helpful
- Related issues
