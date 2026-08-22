# CLI Guide

## Commands

The command-line interface provides `mcp`, `serve`, `schedule`, `sync`,
`doctor`, and `version`. Use command help to see the options applicable to one
runtime:

```bash
lunchmoney-mcp --help
lunchmoney-mcp mcp --help
```

`doctor` validates local configuration and prerequisites without calling Lunch
Money. `sync` performs one foreground synchronization, and `version` prints the
installed package version.

## Configuration

For safe, CLI-exposed runtime settings, precedence is **CLI flags > process
environment > `.env` > built-in defaults**. Secrets and connection URLs are
environment/`.env`-only and cannot be passed as command-line flags.

Use a `.env` file for local development and a secret manager or deployment
environment in production. Docker Compose also reads its project `.env` file to
interpolate the Compose file; values injected into a container are process
environment values and take precedence over an application `.env` file.

## Data handling

Every operational command (`mcp`, `serve`, `schedule`, and `sync`) accepts the
same data-handling flags. Stdio MCP uses the privacy-focused default: each
request goes to Lunch Money and nothing is retained when it finishes.

| Flag          | What it does                                                         |
| :------------ | :------------------------------------------------------------------- |
| No flag       | Keeps data available for later requests, except for stdio MCP        |
| `--stateless` | Keeps a live Lunch Money data cache between requests                 |
| `--ephemeral` | Sends each request to Lunch Money and keeps nothing when it finishes |

Use `--stateless` when a running server should reuse its live data between
requests without retaining it after shutdown. Use `--ephemeral` when every
request should go straight to Lunch Money:

```bash
lunchmoney-mcp mcp --streamable-http --stateless
lunchmoney-mcp mcp --streamable-http --ephemeral
```

## Shell completion

Generate a completion script for the installed executable, then source it in
the current shell:

```bash
# Bash
source <(lunchmoney-mcp --print-completion bash)

# Zsh
source <(lunchmoney-mcp --print-completion zsh)
```

To install Bash completion for future shells, write the generated script to the
standard user completion directory:

```bash
mkdir -p "${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions"
lunchmoney-mcp --print-completion bash \
  > "${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions/lunchmoney-mcp"
```

For Zsh, add `fpath=(~/.zfunc $fpath)` and `autoload -Uz compinit && compinit`
to `~/.zshrc`, then install the generated function:

```bash
mkdir -p ~/.zfunc
lunchmoney-mcp --print-completion zsh > ~/.zfunc/_lunchmoney-mcp
```

## Scheduled synchronization

Scheduled synchronization is a dedicated, opt-in process. It refreshes metadata
on every run and incrementally refreshes transactions; its first run uses the
configured 30-day rolling transaction window until a watermark exists.

```bash
lunchmoney-mcp schedule \
  --schedule-cron "0 * * * *" \
  --schedule-timezone "America/Denver" \
  --schedule-days 30
```

Run exactly one scheduler process. The scheduler is isolated from Gunicorn web
workers and reports its most recent outcome at `GET /api/sync/status` and
through the `get_sync_status` MCP tool. To include it with Docker Compose, run:

```bash
docker compose --profile scheduler up --build
```

For local, single-process FastAPI development, enable the optional scheduler in
the `serve` command:

```bash
task dev -- --embed-scheduler --schedule-cron "0 * * * *"
```

Embedded scheduling works only with `LUNCHMONEY_ENVIRONMENT=development` and
one direct Uvicorn/FastAPI worker. Use the dedicated scheduler process for
Gunicorn or multi-worker deployments.
