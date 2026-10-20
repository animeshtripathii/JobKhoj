# agent/test_mcp_tools.py
#
# Fixed: uses sys.executable instead of the bare string "python" to launch
# the server subprocess. This guarantees the SAME Python interpreter
# (our activated venv) is used to launch the server, regardless of what
# "python" might resolve to in a freshly spawned subprocess's environment.

import asyncio
import os
import sys
from langchain_mcp_adapters.client import MultiServerMCPClient


async def main():
    client = MultiServerMCPClient({
        "resume_matcher": {
            "command": sys.executable,
            "args": ["-m", "mcp_servers.resume_matcher.server"],
            "transport": "stdio",
        },
        "application_tracker": {
            "command": sys.executable,
            "args": ["-m", "mcp_servers.application_tracker.server"],
            "transport": "stdio",
        },
        "interview_prep": {
            "command": sys.executable,
            "args": ["-m", "mcp_servers.interview_prep.server"],
            "transport": "stdio",
        },
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", os.path.abspath("data")],
            "transport": "stdio",
        },
        "fetch": {
            "command": sys.executable,
            "args": ["-m", "mcp_server_fetch"],
            "transport": "stdio",
        },
    })

    tools = await client.get_tools()
    print(f"\nFound {len(tools)} tool(s):\n")
    for tool in tools:
        print(f"- {tool.name}: {tool.description[:80]}")


if __name__ == "__main__":
    asyncio.run(main())