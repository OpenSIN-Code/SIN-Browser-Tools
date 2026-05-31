import asyncio
import sys
import json
from .core import manager
from .opensin_skill import skill

class SINBrowserCLI:
    def __init__(self):
        self.commands = {
            "skills": self.cmd_skills,
            "help": self.cmd_help,
        }
    
    async def cmd_skills(self, args):
        registry = skill.to_opensin_registry()
        print(json.dumps(registry, indent=2))
    
    async def cmd_help(self, args):
        print("SIN-Browser-Tools CLI")
        print("Available commands: skills, help")
    
    async def main(self, argv: list):
        if len(argv) < 2:
            await self.cmd_help([])
            return 1
        
        command = argv[1]
        if command not in self.commands:
            print(f"Unknown command: {command}")
            return 1
        
        return await self.commands[command]([])

async def main():
    cli = SINBrowserCLI()
    exit_code = await cli.main(sys.argv)
    sys.exit(exit_code)

if __name__ == "__main__":
    asyncio.run(main())
