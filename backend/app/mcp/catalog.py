"""MCP Catalog and Auto-Detection Registry for HarnessForge.

Discovers local MCP servers from host environments (mcp.json, settings, etc.)
and provides a curated catalog of standard presets (code-graph, sqlite, yahoofinance, stitch, postgres, etc.).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import ROOT_DIR
from app.schemas.blueprint import MCPServerSpec

# Built-in Standard Presets for common agentic workflows
MCP_PRESETS: Dict[str, MCPServerSpec] = {
    "sqlite": MCPServerSpec(
        id="sqlite",
        description="SQLite Database Explorer & Query Engine. Allows running SQL queries, reading schemas, and analyzing structured data.",
        transport="stdio",
        command="uvx",
        args=["mcp-server-sqlite", "--db-path", "database.db"],
        env={},
    ),
    "yahoofinance": MCPServerSpec(
        id="yahoofinance",
        description="Yahoo Finance Market & News Ingestion. Fetches historical stock prices, market metrics, corporate actions, and financial news.",
        transport="stdio",
        command="python",
        args=["-m", "yfinance_mcp_server"],
        env={},
    ),
    "code-graph": MCPServerSpec(
        id="code-graph",
        description="Graph-based Code Intelligence & AST Search. Provides call graphs, semantic search, symbol references, and architecture impact analysis.",
        transport="stdio",
        command="cgc",
        args=["mcp", "start"],
        env={"DEFAULT_DATABASE": "falkordb", "INDEX_SOURCE": "true"},
    ),
    "stitch": MCPServerSpec(
        id="stitch",
        description="UI Screen Design, Layout Variants, and Design System Token Generator.",
        transport="stdio",
        command="stitch-mcp",
        args=[],
        env={},
    ),
    "postgres": MCPServerSpec(
        id="postgres",
        description="PostgreSQL Database Inspector. Connects to PostgreSQL databases for schema verification, queries, and migrations.",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/mydb"],
        env={},
    ),
    "github": MCPServerSpec(
        id="github",
        description="GitHub Integration. Inspect pull requests, issues, commits, branches, and repository contents.",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-github"],
        env={"GITHUB_PERSONAL_ACCESS_TOKEN": ""},
    ),
    "playwright": MCPServerSpec(
        id="playwright",
        description="Browser Automation & End-to-End Testing. Navigates pages, interacts with DOM elements, captures screenshots, and validates UI behavior.",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-playwright"],
        env={},
    ),
    "filesystem": MCPServerSpec(
        id="filesystem",
        description="Secure Local Filesystem Access. Read, search, list, and manipulate files in designated directory paths.",
        transport="stdio",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", "."],
        env={},
    ),
}


def get_mcp_presets() -> List[MCPServerSpec]:
    """Return all curated built-in MCP server presets."""
    return list(MCP_PRESETS.values())


def detect_host_mcp_servers(workspace_dir: Optional[Path] = None) -> List[MCPServerSpec]:
    """Auto-detect configured MCP servers from host environment and config files."""
    detected: Dict[str, MCPServerSpec] = {}
    base_dir = workspace_dir or ROOT_DIR

    candidate_files = [
        base_dir / "mcp.json",
        base_dir / ".agent" / "mcp.json",
        base_dir / ".agents" / "mcp.json",
        base_dir / "opencode.json",
        Path.home() / ".codegraphcontext" / "mcp.json",
    ]

    for cfg_path in candidate_files:
        if not cfg_path.exists():
            continue
        try:
            raw = cfg_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            # Standard mcpServers structure
            mcp_servers = data.get("mcpServers") or data.get("mcp_servers") or {}
            for name, spec in mcp_servers.items():
                if name in detected:
                    continue
                cmd = spec.get("command")
                args = spec.get("args", [])
                env = spec.get("env", {})
                url = spec.get("url")
                transport = "http" if url else "stdio"
                detected[name] = MCPServerSpec(
                    id=name,
                    description=spec.get("description", f"Host-detected MCP server: {name}"),
                    transport=transport,
                    command=cmd,
                    args=args,
                    url=url,
                    env=env,
                )
        except Exception:
            continue

    return list(detected.values())


def get_all_available_mcp_servers(workspace_dir: Optional[Path] = None) -> List[MCPServerSpec]:
    """Combine host-detected MCP servers with built-in presets (host overrides presets)."""
    detected = detect_host_mcp_servers(workspace_dir)
    merged: Dict[str, MCPServerSpec] = {preset.id: preset for preset in get_mcp_presets()}
    for srv in detected:
        merged[srv.id] = srv
    return list(merged.values())


def resolve_mcp_spec(
    mcp_id: str,
    custom_override: Optional[Dict[str, Any]] = None,
    workspace_dir: Optional[Path] = None,
) -> MCPServerSpec:
    """Resolve an MCP spec by ID using presets, detected servers, or a custom override."""
    if custom_override:
        return MCPServerSpec(
            id=mcp_id,
            description=custom_override.get("description", f"Custom MCP: {mcp_id}"),
            transport=custom_override.get("transport", "stdio"),
            command=custom_override.get("command"),
            args=custom_override.get("args", []),
            url=custom_override.get("url"),
            env=custom_override.get("env", {}),
        )

    all_servers = {srv.id: srv for srv in get_all_available_mcp_servers(workspace_dir)}
    if mcp_id in all_servers:
        return all_servers[mcp_id]

    # Fallback default stub
    return MCPServerSpec(
        id=mcp_id,
        description=f"Auto-generated MCP spec for {mcp_id}",
        transport="stdio",
        command=mcp_id,
        args=[],
        env={},
    )
