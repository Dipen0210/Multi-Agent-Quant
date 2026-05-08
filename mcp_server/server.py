"""
QuantSentiment MCP Server

Exposes the multi-agent analysis system as MCP tools so Claude Desktop
(or any MCP client) can call them directly in conversation.

Usage:
    python -m mcp_server.server          # stdio transport (Claude Desktop)
    python mcp_server/server.py          # same

Add to Claude Desktop config (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "quantsentiment": {
          "command": "python",
          "args": ["-m", "mcp_server.server"],
          "cwd": "/path/to/QuantSentiment",
          "env": { "API_BASE_URL": "http://localhost:8000" }
        }
      }
    }
"""
import inspect
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types
import mcp_server.tools as qt


app = Server("quantsentiment")

_TOOLS = [qt.analyze_ticker, qt.get_portfolio, qt.health_check]


def _build_schema(fn) -> dict:
    sig = inspect.signature(fn)
    props = {}
    required = []
    for name, param in sig.parameters.items():
        annotation = param.annotation
        if annotation is inspect.Parameter.empty:
            ptype = "string"
        elif annotation is int:
            ptype = "integer"
        else:
            ptype = "string"

        props[name] = {"type": ptype}

        doc = inspect.getdoc(fn) or ""
        for line in doc.splitlines():
            line = line.strip()
            if line.startswith(f"{name}:"):
                props[name]["description"] = line[len(name) + 1:].strip()

        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            props[name]["default"] = param.default

    schema = {"type": "object", "properties": props}
    if required:
        schema["required"] = required
    return schema


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=fn.__name__,
            description=(inspect.getdoc(fn) or "").splitlines()[0],
            inputSchema=_build_schema(fn),
        )
        for fn in _TOOLS
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    fn_map = {fn.__name__: fn for fn in _TOOLS}
    if name not in fn_map:
        raise ValueError(f"Unknown tool: {name}")
    result = fn_map[name](**arguments)
    return [types.TextContent(type="text", text=result)]


async def _run():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main():
    import asyncio
    asyncio.run(_run())


if __name__ == "__main__":
    main()
