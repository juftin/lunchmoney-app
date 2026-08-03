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
        HTTP[HTTP / Streamable HTTP]
    end

    subgraph Executable Bundles
        UVX[uvx lunchmoney-mcp]
        Docker[Docker Container]
    end

    ClaudeDesktop -->|stdio| UVX
    AGY_IDE -->|stdio| UVX
    Cursor -->|stdio| UVX
    WebClient -->|SSE| SSE
    WebClient -->|HTTP / Streamable HTTP| HTTP
    Docker --> HTTP
```

### 1.1 Executable Entrypoint & PyPI `uvx` Bundling

Expose a clean CLI entrypoint in `pyproject.toml` so users and LLM clients can launch the server instantly via `uvx lunchmoney-mcp mcp` or `pipx run lunchmoney-mcp mcp` without manually cloning the repository:

```toml
# pyproject.toml
[project.scripts]
lunchmoney-mcp = "lunchmoney_mcp.cli:main"
```

### 1.2 Multi-Transport Support

The executable supports FastMCP's four transports. `stdio` is the default for
local desktop clients; use the HTTP flags for remote server deployments:

```bash
lunchmoney-mcp mcp                    # stdio
lunchmoney-mcp mcp --stdio            # stdio (explicit)
lunchmoney-mcp mcp --sse              # Server-Sent Events
lunchmoney-mcp mcp --http             # HTTP
lunchmoney-mcp mcp --streamable-http  # Streamable HTTP
```

For HTTP transports, the default bind address is `127.0.0.1:8000`. The MCP
endpoints are `http://127.0.0.1:8000/mcp` for HTTP and Streamable HTTP, and
`http://127.0.0.1:8000/sse` for SSE. Override the bind address as needed:

```bash
lunchmoney-mcp mcp --streamable-http --host 0.0.0.0 --port 9000
```

`--host` and `--port` are invalid with `--stdio`. The four transport flags are
mutually exclusive.

### 1.3 Shell completion and command discovery

`mcp` is one of the top-level `lunchmoney-mcp` commands. Generate completion
for the installed executable and source it in the current shell:

```bash
# Bash
source <(lunchmoney-mcp --print-completion bash)

# Zsh
source <(lunchmoney-mcp --print-completion zsh)
```

Install Bash completion for future shells with:

```bash
mkdir -p "${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions"
lunchmoney-mcp --print-completion bash \
  > "${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions/lunchmoney-mcp"
```

For Zsh, configure `fpath=(~/.zfunc $fpath)` and
`autoload -Uz compinit && compinit` in `~/.zshrc`, then install the generated
function:

```bash
mkdir -p ~/.zfunc
lunchmoney-mcp --print-completion zsh > ~/.zfunc/_lunchmoney-mcp
```

The default remains `lunchmoney-mcp mcp` over stdio. Do not add an HTTP flag
just to run a local desktop client: stdio communicates over the parent process'
standard input and output, and avoids opening a listening socket.

Use `lunchmoney-mcp <subcommand> --help` for the authoritative option list.

### 1.4 Client Configuration Snippets

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

## 🔐 2. Authentication & Authorization

Set `LUNCHMONEY_MCP_API_KEY` to require an `X-API-Key` header on every REST API
request. Leave it unset for local development. This differs from
`LUNCHMONEY_ACCESS_TOKEN`, which is the server's credential for Lunch Money's
upstream API; every MCP transport uses that upstream credential.

| Credential or guard                 | Scope                          | Target deployment                             | Implementation details                                                                                                                                                             |
| :---------------------------------- | :----------------------------- | :-------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Upstream Lunch Money credential** | Server-to-Lunch-Money          | Every deployment                              | `LUNCHMONEY_ACCESS_TOKEN` is required by the server to call Lunch Money. It is not passed by MCP or REST clients.                                                                  |
| **REST API key**                    | Client-to-project REST API     | Optional, local or hosted REST API            | `LUNCHMONEY_MCP_API_KEY` requires the matching `X-API-Key` header on REST requests. It does not guard MCP endpoints.                                                               |
| **Remote MCP OIDC OAuth**           | Client-to-project MCP endpoint | Optional, hosted HTTP/SSE/Streamable HTTP MCP | FastMCP's OAuth proxy delegates client authentication to a configured OIDC identity provider. The server continues to use its single configured Lunch Money access token upstream. |

### 2.1 Remote MCP OAuth

HTTP, SSE, and Streamable HTTP MCP endpoints can use an upstream OIDC identity
provider through FastMCP's OAuth proxy. Configure all required values before
starting an HTTP transport:

```bash
export LUNCHMONEY_MCP_OAUTH_CONFIG_URL="https://id.example.com/.well-known/openid-configuration"
export LUNCHMONEY_MCP_OAUTH_CLIENT_ID="lunchmoney-mcp"
export LUNCHMONEY_MCP_OAUTH_CLIENT_SECRET="your-identity-provider-secret" # optional for public clients
export LUNCHMONEY_MCP_OAUTH_BASE_URL="https://mcp.example.com"
export LUNCHMONEY_MCP_OAUTH_AUDIENCE="https://mcp.example.com" # optional

lunchmoney-mcp mcp --streamable-http --host 0.0.0.0 --port 8000
```

`LUNCHMONEY_MCP_OAUTH_BASE_URL` must be the public HTTPS origin, without the
`/mcp` path. Register `${LUNCHMONEY_MCP_OAUTH_BASE_URL}/auth/callback` as the
callback URL with the identity provider. FastMCP publishes OAuth metadata and
handles dynamic client registration and PKCE for compatible MCP clients.

OAuth is disabled when all required OAuth variables are unset, preserving local
stdio use. Supplying only some of `LUNCHMONEY_MCP_OAUTH_CONFIG_URL`,
`LUNCHMONEY_MCP_OAUTH_CLIENT_ID`, and `LUNCHMONEY_MCP_OAUTH_BASE_URL` prevents
startup so a remote endpoint cannot be accidentally left partially configured.

---

## 📦 3. MCP Primitives: Resources & Prompts

Beyond function-calling **Tools**, MCP defines **Resources** (read-only context URIs) and **Prompts** (pre-built prompt templates).

### 3.1 MCP Resources (`lunchmoney://...`)

| Resource URI              | Description                              | Mime Type          |
| :------------------------ | :--------------------------------------- | :----------------- |
| `lunchmoney://summary`    | Current-month budget summary with totals | `text/markdown`    |
| `lunchmoney://categories` | Complete synchronized category hierarchy | `application/json` |

### 3.2 MCP Prompts (Built-in Assistant Workflows)

- `budget_health_check`: Analyze monthly budget performance and highlight over-budget categories.
- `uncategorized_transactions_audit`: Find uncategorized transactions and recommend category assignments.
