# 🔌 Advanced MCP Considerations & Integration Blueprint

## 📋 Overview

This document outlines advanced **Model Context Protocol (MCP)** considerations, packaging strategies, security patterns, and protocol primitives for **Lunch Money MCP**. It serves as an authoritative guide for extending the server beyond basic tools into a full-featured MCP ecosystem component.

---

## 🏗️ 1. Transports & Client Packaging ("Bundles")

```mermaid
graph TD
    subgraph Client Environments
        ClaudeDesktop[Claude Desktop App]
        AGY_IDE[Antigravity IDE / CLI]
        Cursor[Cursor IDE]
        WebClient[Web / Remote MCP Client]
    end

    subgraph Transports
        STDIO[stdio Transport / Process Pipe]
        SSE[SSE Transport / Server-Sent Events]
    end

    subgraph Executable Bundles
        UVX[uvx lunchmoney-mcp]
        Docker[Docker Container]
    end

    ClaudeDesktop -->|stdio| UVX
    AGY_IDE -->|stdio| UVX
    Cursor -->|stdio| UVX
    WebClient -->|HTTP / SSE| SSE
    Docker --> SSE
```

### 1.1 Executable Entrypoint & PyPI `uvx` Bundling

Expose a clean CLI entrypoint in `pyproject.toml` so users and LLM clients can launch the server instantly via `uvx lunchmoney-mcp` or `pipx run lunchmoney-mcp` without manually cloning the repository:

```toml
# pyproject.toml
[project.scripts]
lunchmoney-mcp = "lunchmoney_mcp.mcp.server:main"
```

### 1.2 Multi-Transport Support (`stdio` & `sse`)

FastMCP natively supports both process piping (`stdio`) for local desktop apps and HTTP Server-Sent Events (`sse`) for remote microservices:

```python
# src/lunchmoney_mcp/mcp/server.py
def main():
    import sys
    transport = "sse" if "--sse" in sys.argv else "stdio"
    mcp.run(transport=transport)
```

### 1.3 Client Configuration Snippets

#### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "lunchmoney": {
      "command": "uvx",
      "args": ["lunchmoney-mcp"],
      "env": {
        "LUNCHMONEY_ACCESS_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

#### Antigravity MCP Config (`.gemini/config/mcp.json`)

```json
{
  "mcpServers": {
    "lunchmoney": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "/path/to/lunchmoney-mcp",
        "lunchmoney-mcp"
      ],
      "env": {
        "LUNCHMONEY_ACCESS_TOKEN": "your_api_token_here"
      }
    }
  }
}
```

---

## 🔐 2. Authentication & Authorization (API Key vs. OAuth 2.0)

Set `LUNCHMONEY_API_KEY` to require an `X-API-Key` header on every REST API
request. Leave it unset for local development; MCP stdio and SSE transports
continue to use the Lunch Money access token configured for the server.

| Auth Model                 | Topology                  | Target Deployment                          | Implementation Details                                                                   |
| :------------------------- | :------------------------ | :----------------------------------------- | :--------------------------------------------------------------------------------------- |
| **Static Token (Current)** | Single-Tenant / Local     | Desktop Apps (Claude, Antigravity, Cursor) | Injected via `LUNCHMONEY_ACCESS_TOKEN` environment variable.                             |
| **Multi-Tenant OAuth 2.0** | Multi-User / Cloud Hosted | Web-Hosted MCP Servers / Remote SSE        | Lunch Money OAuth 2.0 PKCE flow. Per-session token resolution stored in context headers. |

---

## 📦 3. MCP Primitives: Resources & Prompts

Beyond function-calling **Tools**, MCP defines **Resources** (read-only context URIs) and **Prompts** (pre-built prompt templates).

### 3.1 MCP Resources (`lunchmoney://...`)

| Resource URI                       | Description                                           | Mime Type          |
| :--------------------------------- | :---------------------------------------------------- | :----------------- |
| `lunchmoney://summary`             | Instant account net worth & account balance breakdown | `text/markdown`    |
| `lunchmoney://categories`          | Complete category hierarchy and budget settings       | `application/json` |
| `lunchmoney://transactions/recent` | Stream of recent 30-day transactions                  | `application/json` |

### 3.2 MCP Prompts (Built-in Assistant Workflows)

- `budget_health_check`: Analyze monthly budget performance and highlight over-budget categories.
- `uncategorized_transactions_audit`: Find uncategorized transactions and recommend category assignments.
