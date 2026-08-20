<h1 align="center">lunchmoney-mcp</h1>

<p align="center">
    Lunch Money Application
</p>

<p align="center">
  <a href="https://github.com/juftin/lunchmoney-mcp"><img src="https://img.shields.io/github/v/release/juftin/lunchmoney-mcp?color=blue&label=lunchmoney-mcp&logo=github" alt="GitHub"></a>
  <a href="https://github.com/juftin/lunchmoney-mcp/blob/main/LICENSE"><img src="https://img.shields.io/github/license/juftin/lunchmoney-mcp?color=blue&label=License" alt="GitHub License"></a>
  <a href="https://github.com/juftin/lunchmoney-mcp/actions/workflows/ci.yaml?query=branch%3Amain"><img src="https://github.com/juftin/lunchmoney-mcp/actions/workflows/ci.yaml/badge.svg?branch=main" alt="CI Status"></a>
  <a href="https://juftin.github.io/lunchmoney-mcp/"><img src="https://img.shields.io/static/v1?message=docs&color=526CFE&logo=Material+for+MkDocs&logoColor=FFFFFF&label=" alt="docs"></a>
</p>

## Quickstart

Use Lunch Money from your favorite MCP-enabled assistant in a few minutes.

1. Create or copy your Lunch Money access token.
2. Add the configuration below to your MCP client's server settings.
3. Replace `your-lunch-money-token`, restart the client, and start chatting.

Your MCP client starts and manages Lunch Money MCP for you; do not run a
separate server command.

```json
{
    "mcpServers": {
        "lunchmoney": {
            "command": "uvx",
            "args": ["lunchmoney-mcp", "mcp"],
            "env": {
                "LUNCHMONEY_ACCESS_TOKEN": "your-lunch-money-token"
            }
        }
    }
}
```

Try asking:

- “How much did I spend on dining this month?”
- “Show my largest recent transactions.”
- “Which transactions still need a category?”

## Learn more

- [MCP guide](docs/MCP_GUIDE.md): client configuration, remote connections, and OAuth.
- [CLI guide](docs/CLI.md): commands, data handling, scheduling, and shell completion.
- [Operations runbook](docs/OPERATIONS.md): self-hosting, Docker Compose, security, and backups.
