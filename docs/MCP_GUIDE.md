# MCP Guide

Lunch Money MCP lets an MCP-enabled assistant answer questions about your
Lunch Money account. For most people, the local setup below is all that is
needed.

## Use it with your desktop app or IDE

Your MCP client starts the server when needed. Add this configuration to its
MCP server settings, replace the access token, then restart the client:

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

This uses the recommended local connection. It does not open a network port,
and each request goes directly to Lunch Money without retaining data when it
finishes.

If you run the project from a checkout instead, replace `uvx` and its arguments
with the command your client uses to run:

```bash
lunchmoney-app mcp
```

## Connect a remote client

Run a Streamable HTTP server when the MCP client cannot start a local process:

```bash
export LUNCHMONEY_ACCESS_TOKEN="your-lunch-money-token"
lunchmoney-app mcp --streamable-http --host 0.0.0.0 --port 8000
```

Connect the client to `http://your-server:8000/mcp`. For a public deployment,
put the service behind HTTPS and follow the [operations runbook](OPERATIONS.md).

Streamable HTTP is the recommended remote connection. `--sse` and `--http`
remain available only for clients that require those older connection types.

## Choose how data is handled

The local setup is private by default: requests go to Lunch Money and nothing
is retained afterward. A remote server keeps data available for later requests
by default. You can choose a different behavior with either command:

| Option        | What it does                                          |
| :------------ | :---------------------------------------------------- |
| `--stateless` | Keeps a live Lunch Money data cache while running     |
| `--ephemeral` | Sends each request to Lunch Money and retains nothing |

For example, use a remote server without retaining data:

```bash
lunchmoney-app mcp --streamable-http --ephemeral
```

## Secure a remote server

Your Lunch Money access token stays on the server; MCP clients do not receive
it. Do not expose a remote server directly to the internet without HTTPS and
client authentication.

If your MCP client supports OAuth, configure your OIDC provider before starting
the server:

```bash
export LUNCHMONEY_APP_OAUTH_CONFIG_URL="https://id.example.com/.well-known/openid-configuration"
export LUNCHMONEY_APP_OAUTH_CLIENT_ID="lunchmoney-app"
export LUNCHMONEY_APP_OAUTH_BASE_URL="https://mcp.example.com"

lunchmoney-app mcp --streamable-http --host 0.0.0.0 --port 8000
```

Set `LUNCHMONEY_APP_OAUTH_CLIENT_SECRET` too when your identity provider
requires it. Register `https://mcp.example.com/auth/callback` with the provider.

For a complete deployment checklist, backups, and security guidance, see the
[operations runbook](OPERATIONS.md).

## Review unreviewed transactions

Use the `unreviewed_transactions_review` prompt to retrieve unreviewed,
non-pending transactions with `review_transactions`. It defaults to the prior
45 days and returns, in one response, complete transaction and Plaid metadata,
each transaction's linked category and account, the full category list, and all
accounts. After you confirm the exact values, it applies the needed category,
notes, and payee updates through `bulk_update_transactions`, and marks each
confirmed transaction as reviewed.

The same workspace is available as the `review_transactions` MCP tool and
`GET /api/transactions/review`. Supply `start_date`/`end_date` or a manual/Plaid
account ID to narrow the default review window.
