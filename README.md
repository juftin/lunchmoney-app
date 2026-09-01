<h1 align="center">lunchmoney-app</h1>

<p align="center">
    MCP-first access to your Lunch Money data
</p>

<p align="center">
  <a href="https://github.com/juftin/lunchmoney-app"><img src="https://img.shields.io/github/v/release/juftin/lunchmoney-app?color=blue&label=lunchmoney-app&logo=github" alt="GitHub"></a>
  <a href="https://github.com/juftin/lunchmoney-app/blob/main/LICENSE"><img src="https://img.shields.io/github/license/juftin/lunchmoney-app?color=blue&label=License" alt="GitHub License"></a>
  <a href="https://github.com/juftin/lunchmoney-app/actions/workflows/ci.yaml?query=branch%3Amain"><img src="https://github.com/juftin/lunchmoney-app/actions/workflows/ci.yaml/badge.svg?branch=main" alt="CI Status"></a>
  <a href="https://juftin.github.io/lunchmoney-app/"><img src="https://img.shields.io/static/v1?message=docs&color=526CFE&logo=Material+for+MkDocs&logoColor=FFFFFF&label=" alt="docs"></a>
</p>

`lunchmoney-app` is first and foremost an [MCP](https://modelcontextprotocol.io/)
server for using your Lunch Money data from an MCP-enabled assistant. It also runs
as a standalone application with a RESTful API and database backend that keeps
itself in sync with all of your Lunch Money data.

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
            "args": ["lunchmoney-app", "mcp"],
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

<details>
<summary>Install in Claude Code, Codex, Gemini CLI, or Claude Desktop</summary>

Claude Code, Codex, and Gemini CLI use the published package through `uvx`; install
[uv](https://docs.astral.sh/uv/getting-started/installation/) first. Claude Desktop
manages the MCPB runtime itself. Provide your Lunch Money access token through
`LUNCHMONEY_ACCESS_TOKEN` unless the client prompts for it.

| Client         | Install                                                                                                      |
| :------------- | :----------------------------------------------------------------------------------------------------------- |
| Claude Code    | `claude plugin marketplace add juftin/lunchmoney-app && claude plugin install lunchmoney-mcp@lunchmoney-app` |
| Codex          | `codex plugin marketplace add juftin/lunchmoney-app && codex plugin add lunchmoney-mcp@lunchmoney-app`       |
| Gemini CLI     | `gemini extensions install https://github.com/juftin/lunchmoney-app`                                         |
| Claude Desktop | Download `lunchmoney-app.mcpb` from a release and open it.                                                   |

For direct standard-MCP setup and framework-specific token configuration, see
the [MCP guide](docs/MCP_GUIDE.md).

</details>

<!-- mcp-name: io.github.juftin/lunchmoney-app -->

## Learn more

- [MCP guide](docs/MCP_GUIDE.md): client configuration, remote connections, and OAuth.
- [CLI guide](docs/CLI.md): commands, data handling, scheduling, and shell completion.
- [Operations runbook](docs/OPERATIONS.md): self-hosting, Docker Compose, security, and backups.
