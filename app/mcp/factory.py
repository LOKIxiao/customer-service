from pathlib import Path

from app.mcp.client import MCPToolClient


def create_mcp_client(tickets_file: Path | None = None) -> MCPToolClient:
    return MCPToolClient(tickets_file=tickets_file)
