# CLI Guide

## Commands

The Click command-line interface provides `mcp`, `serve`, `schedule`, `sync`,
`doctor`, `version`, `config`, and `db`. Use command help to see every option
applicable to one runtime, including its Pydantic default and environment
variable alternative:

```bash
lunchmoney-app --help
lunchmoney-app mcp --help
```

`doctor` validates local configuration and prerequisites without calling Lunch
Money. `sync` performs one foreground synchronization, and `version` prints the
installed package version.

Use `db info` to print safe database configuration JSON, `db migrate` to apply
pending migrations, and `db delete --yes` to drop every Lunch Money application
table in a configured PostgreSQL database or delete a configured SQLite file.
Database URLs are still configured only through `LUNCHMONEY_DATABASE_URL` or
`.env`; `db info` redacts any password.

Use the configuration commands to discover every runtime and environment-only
setting, inspect safely redacted resolved values, or validate configuration
without starting a service:

```bash
lunchmoney-app config list
lunchmoney-app config show
lunchmoney-app config validate
```

## Configuration

Click passes only explicitly supplied flags to Pydantic Settings. Pydantic then
resolves safe runtime settings in this order: **CLI flags, process environment,
`.env`, then built-in defaults**. It supplies the validated settings object to
the application. Secrets and connection URLs are environment/`.env`-only,
appear by name in `config list`, and cannot be passed as command-line flags.
`config show` always redacts their values.

Use a `.env` file for local development and a secret manager or deployment
environment in production. Docker Compose also reads its project `.env` file to
interpolate the Compose file; values injected into a container are process
environment values and take precedence over an application `.env` file.

## Data handling

The application has exactly two persistence modes. HTTP runtimes default to
`stateful`; stdio MCP defaults to `ephemeral` when no mode is selected.

| Flag                           | What it does                                                                                                                  |
| :----------------------------- | :---------------------------------------------------------------------------------------------------------------------------- |
| `--persistence-mode stateful`  | Reads synchronized data from SQLite or PostgreSQL and enables sync, scheduling, and the dashboard                             |
| `--persistence-mode ephemeral` | Reads Lunch Money live for each operation and creates no database, migrations, locks, or cross-operation financial-data cache |

Select database-free operation explicitly for a remote MCP server:

```bash
lunchmoney-app mcp --streamable-http --persistence-mode ephemeral
```

Database and scheduler settings are configuration errors in ephemeral mode.
The `schedule` and `sync` commands are stateful-only.

## Shell completion

Generate Click's native completion script for the installed executable, then
source it in the current shell. Bash, Zsh, and Fish are supported:

```bash
# Bash
source <(lunchmoney-app --print-completion bash)

# Zsh
source <(lunchmoney-app --print-completion zsh)
```

To install Bash completion for future shells, write the generated script to the
standard user completion directory:

```bash
mkdir -p "${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions"
lunchmoney-app --print-completion bash \
  > "${XDG_DATA_HOME:-$HOME/.local/share}/bash-completion/completions/lunchmoney-app"
```

For Zsh, add `fpath=(~/.zfunc $fpath)` and `autoload -Uz compinit && compinit`
to `~/.zshrc`, then install the generated function:

```bash
mkdir -p ~/.zfunc
lunchmoney-app --print-completion zsh > ~/.zfunc/_lunchmoney-app
```

## Scheduled synchronization

Scheduled synchronization is a dedicated, opt-in process. It refreshes metadata
on every run and incrementally refreshes transactions; its first run uses the
configured 30-day rolling transaction window until a watermark exists.

```bash
lunchmoney-app schedule \
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
