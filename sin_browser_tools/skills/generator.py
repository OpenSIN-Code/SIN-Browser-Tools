"""Generate/validate OpenCode skills from proven runs."""

import argparse
import sys
from pathlib import Path
from typing import Optional


def generate_skill(name: str, description: str) -> None:
    """Scaffold a new .opencode/skills/{name}/ directory."""
    skills_dir = Path(".opencode/skills")
    skills_dir.mkdir(parents=True, exist_ok=True)

    skill_dir = skills_dir / name
    skill_dir.mkdir(exist_ok=True)

    title = name.replace("-", " ").title()
    skill_md = f"""---
name: {name}
description: |-
  {description}
---

# {title}

Following the LOOK -> DECIDE -> ACT -> VERIFY loop.

## Parameters
(Describe inputs here)

## Steps
(List ordered browser_* tool calls)

## Success check
(How do we know it worked?)

## If stuck
See `sin-browser-automation` skill's error-recovery.md.
"""
    (skill_dir / "SKILL.md").write_text(skill_md)

    ref_dir = skill_dir / "reference"
    ref_dir.mkdir(exist_ok=True)
    (ref_dir / ".gitkeep").touch()

    print(f"✓ Created {skill_dir}")
    print(f"  Edit SKILL.md to fill in parameters, steps, success check.")


def validate_skill(name: str) -> bool:
    """Check SKILL.md frontmatter, name consistency, tool existence."""
    from sin_browser_tools.tools import catalog

    skill_dir = Path(".opencode/skills") / name
    skill_md = skill_dir / "SKILL.md"

    if not skill_md.exists():
        print(f"✗ {skill_md} not found")
        return False

    content = skill_md.read_text()
    if not content.startswith("---"):
        print(f"✗ {skill_md} missing frontmatter")
        return False

    lines = content.split("\n")
    frontmatter_name = None
    for line in lines[1:]:
        if line.startswith("---"):
            break
        if line.startswith("name:"):
            frontmatter_name = line.split(":", 1)[1].strip()

    if frontmatter_name != name:
        print(f"✗ frontmatter name '{frontmatter_name}' != folder '{name}'")
        return False

    tools = set(catalog.discover())
    for line in lines:
        if "browser_" in line:
            tokens = line.replace("(", " ").replace(")", " ").replace("`", " ").split()
            for tok in tokens:
                if tok.startswith("browser_") and tok not in tools:
                    print(f"✗ tool '{tok}' not in catalog")
                    return False

    print(f"✓ {name} is valid")
    return True


def main() -> None:
    p = argparse.ArgumentParser(description="Skill generator & validator")
    p.add_argument("--name", help="skill name (lowercase-hyphenated)")
    p.add_argument("--description", help="skill description")
    p.add_argument("--validate", help="validate skill by name")
    p.add_argument("--list", action="store_true", help="list all skills")

    args = p.parse_args()

    if args.validate:
        sys.exit(0 if validate_skill(args.validate) else 1)
    elif args.list:
        skills_dir = Path(".opencode/skills")
        if skills_dir.exists():
            for d in sorted(skills_dir.iterdir()):
                if d.is_dir():
                    print(f"  {d.name}")
    elif args.name:
        generate_skill(args.name, args.description or "")
    else:
        p.print_help()


if __name__ == "__main__":
    main()
