"""MCP client - connects to MCP servers and discovers tools/resources."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


class MCPServerConnection:
    """A connection to a single MCP server."""

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name = name
        self.config = config
        self.session: ClientSession | None = None
        self.tools: list[dict[str, Any]] = []
        self.resources: list[dict[str, Any]] = []
        self._transport: Any = None
        self._read: Any = None
        self._write: Any = None
        self._cm: Any = None  # context manager

    @property
    def server_type(self) -> str:
        """Determine server type from config."""
        if "command" in self.config:
            return "stdio"
        elif "url" in self.config:
            return "sse"
        return "unknown"

    async def connect(self) -> bool:
        """Connect to the MCP server and discover tools/resources.

        Returns:
            True if connection was successful.
        """
        try:
            if self.server_type == "stdio":
                return await self._connect_stdio()
            elif self.server_type == "sse":
                return await self._connect_sse()
            else:
                logger.warning("Unknown MCP server type for %s", self.name)
                return False
        except Exception as e:
            logger.error("Failed to connect to MCP server %s: %s", self.name, e)
            return False

    async def _connect_stdio(self) -> bool:
        """Connect via stdio transport."""
        command = self.config["command"]
        args = self.config.get("args", [])
        env = {**os.environ, **self.config.get("env", {})}

        server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env,
        )

        self._cm = stdio_client(server_params)
        self._read, self._write = await self._cm.__aenter__()
        self.session = ClientSession(self._read, self._write)
        await self.session.__aenter__()
        await self.session.initialize()

        # Discover tools
        tools_result = await self.session.list_tools()
        self.tools = [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema if hasattr(t, "inputSchema") else {},
            }
            for t in tools_result.tools
        ]

        # Discover resources
        try:
            resources_result = await self.session.list_resources()
            self.resources = [
                {
                    "uri": r.uri,
                    "name": r.name or "",
                    "description": r.description or "",
                }
                for r in resources_result.resources
            ]
        except Exception:
            self.resources = []

        logger.info(
            "Connected to MCP server %s: %d tools, %d resources",
            self.name, len(self.tools), len(self.resources),
        )
        return True

    async def _connect_sse(self) -> bool:
        """Connect via SSE transport."""
        url = self.config["url"]
        headers = self.config.get("headers", {})

        self._cm = sse_client(url=url, headers=headers)
        self._read, self._write = await self._cm.__aenter__()
        self.session = ClientSession(self._read, self._write)
        await self.session.__aenter__()
        await self.session.initialize()

        # Discover tools
        tools_result = await self.session.list_tools()
        self.tools = [
            {
                "name": t.name,
                "description": t.description or "",
                "input_schema": t.inputSchema if hasattr(t, "inputSchema") else {},
            }
            for t in tools_result.tools
        ]

        logger.info(
            "Connected to MCP server %s (SSE): %d tools",
            self.name, len(self.tools),
        )
        return True

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call.
            arguments: Tool arguments.

        Returns:
            Tool result as string.
        """
        if self.session is None:
            return f"Error: Not connected to MCP server {self.name}"

        try:
            result = await self.session.call_tool(tool_name, arguments)
            # Extract text from content blocks
            parts = []
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
                elif hasattr(block, "data"):
                    parts.append(f"[binary data: {len(block.data)} bytes]")
                else:
                    parts.append(str(block))
            return "\n".join(parts) if parts else "Done (no output)."
        except Exception as e:
            return f"MCP tool error ({self.name}/{tool_name}): {e}"

    async def read_resource(self, uri: str) -> str:
        """Read a resource from the MCP server.

        Args:
            uri: Resource URI.

        Returns:
            Resource content as string.
        """
        if self.session is None:
            return f"Error: Not connected to MCP server {self.name}"

        try:
            result = await self.session.read_resource(uri)
            parts = []
            for block in result.contents:
                if hasattr(block, "text"):
                    parts.append(block.text)
                else:
                    parts.append(str(block))
            return "\n".join(parts)
        except Exception as e:
            return f"MCP resource error ({self.name}/{uri}): {e}"

    async def disconnect(self) -> None:
        """Disconnect from the MCP server."""
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
                self.session = None
            if self._cm:
                await self._cm.__aexit__(None, None, None)
                self._cm = None
        except Exception as e:
            logger.debug("Error disconnecting from %s: %s", self.name, e)


class MCPManager:
    """Manages multiple MCP server connections."""

    def __init__(self) -> None:
        self.connections: dict[str, MCPServerConnection] = {}

    async def connect_all(self, servers_config: dict[str, dict[str, Any]]) -> int:
        """Connect to all configured MCP servers.

        Args:
            servers_config: Dict mapping server name to server config.

        Returns:
            Number of successfully connected servers.
        """
        connected = 0
        for name, config in servers_config.items():
            conn = MCPServerConnection(name, config)
            if await conn.connect():
                self.connections[name] = conn
                connected += 1
            else:
                logger.warning("Failed to connect to MCP server: %s", name)
        return connected

    def get_all_tools(self) -> list[dict[str, Any]]:
        """Get all tools from all connected servers.

        Returns:
            List of tool definitions with server name added.
        """
        all_tools = []
        for server_name, conn in self.connections.items():
            for tool in conn.tools:
                all_tools.append({
                    **tool,
                    "server": server_name,
                    "full_name": f"mcp__{server_name}__{tool['name']}",
                })
        return all_tools

    async def call_tool(self, full_name: str, arguments: dict[str, Any]) -> str:
        """Call a tool by its full name (mcp__server__tool).

        Args:
            full_name: Full tool name including server prefix.
            arguments: Tool arguments.

        Returns:
            Tool result as string.
        """
        parts = full_name.split("__", 2)
        if len(parts) != 3 or parts[0] != "mcp":
            return f"Error: Invalid MCP tool name: {full_name}"

        server_name = parts[1]
        tool_name = parts[2]

        conn = self.connections.get(server_name)
        if conn is None:
            return f"Error: MCP server not found: {server_name}"

        return await conn.call_tool(tool_name, arguments)

    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers."""
        for conn in self.connections.values():
            await conn.disconnect()
        self.connections.clear()

    @property
    def tool_count(self) -> int:
        """Total number of tools across all servers."""
        return sum(len(c.tools) for c in self.connections.values())

    @property
    def server_count(self) -> int:
        """Number of connected servers."""
        return len(self.connections)
