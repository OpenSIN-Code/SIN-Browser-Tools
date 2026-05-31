# `cli.py`

A minimal command-line interface, mainly for inspecting the OpenSIN skill
registry.

## Commands

| Command | Description |
| --- | --- |
| `skills` | Print the full OpenSIN registry JSON (`skill.to_opensin_registry()`). |
| `help` | List available commands. |

## Usage
```bash
python -m sin_browser_tools.cli skills   # dump the tool/skill registry as JSON
python -m sin_browser_tools.cli help
```

## Behavior
- `SINBrowserCLI.main(argv)` dispatches on `argv[1]`; unknown commands print an
  error and return exit code `1`.
- `main()` wraps it in `asyncio.run` and propagates the exit code via
  `sys.exit`.

## Notes
- This CLI is for **introspection**, not for driving the browser — actual
  browser actions are exposed through the MCP server (`mcp_server.py`).
- The `skills` output is derived from `catalog`, so it always matches the live
  tool set.
