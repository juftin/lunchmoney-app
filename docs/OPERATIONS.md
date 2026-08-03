# Production Operations Runbook

This runbook covers the production Docker Compose topology: one REST/MCP web
service, PostgreSQL, Redis, and optionally one scheduler. It intentionally
keeps financial data and credentials out of logs, command history, and CI
output.

## Deploy safely

1. Terminate TLS at an ingress or reverse proxy and forward only to the web
   service's loopback binding (`127.0.0.1:8000`). Do not publish PostgreSQL or
   Redis ports. Restrict `/metrics` to the operations network or an authenticated
   monitoring client.
2. Run the web and scheduler services with least privilege. The supplied image
   runs as an unprivileged user, drops Linux capabilities, disallows privilege
   escalation, and has a read-only root filesystem. Do not weaken these settings
   merely to make an application write to its image filesystem.
3. Inject values from a secret manager or the deployment environment; never bake
   them into an image, commit them, or pass them on a command line. Before
   starting Compose, set `LUNCHMONEY_ACCESS_TOKEN`, `LUNCHMONEY_MCP_API_KEY`,
   `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `LUNCHMONEY_DATABASE_URL`.
   The database URL must use the same database credentials and hostname
   `postgres`; percent-encode reserved characters in its username and password.
4. Start the API and its dependencies, then confirm the checks below. Start the
   `scheduler` profile only when exactly one scheduler process is intended.

```bash
docker compose up --build --detach --wait
curl --fail --header "X-API-Key: $LUNCHMONEY_MCP_API_KEY" http://127.0.0.1:8000/health
curl --fail --header "X-API-Key: $LUNCHMONEY_MCP_API_KEY" http://127.0.0.1:8000/ready
docker compose --profile scheduler up --detach scheduler
```

`/health` confirms that the process is alive. `/ready` additionally confirms
that dependencies required to serve traffic are ready. These endpoints
intentionally bypass API-key authentication so an orchestrator can detect a
failed service; keep them on the loopback deployment binding or limit them at
the reverse proxy. `/metrics` requires `LUNCHMONEY_MCP_API_KEY` and must remain
available only to the operations network or an authenticated monitoring client.

## Audit release dependencies

Run the following before publishing a release or after changing a dependency:

```bash
task security
```

This audits the locked production Python dependency set with `uv audit` and
fails when it finds a known vulnerability. It does not inspect the operating
system, container configuration, or secrets; CI continues to use Trivy for
those release-image and repository checks.

## Network policy

The server starts with localhost and `127.0.0.1` as its only accepted `Host`
headers, and with CORS and proxy-header trust disabled. Configure the public
deployment explicitly at the reverse-proxy boundary:

```bash
export LUNCHMONEY_ALLOWED_HOSTS="mcp.example.com"
export LUNCHMONEY_TRUSTED_PROXY_IPS="10.0.0.10"
export LUNCHMONEY_CORS_ALLOWED_ORIGINS="https://console.example.com"
```

Set `LUNCHMONEY_TRUSTED_PROXY_IPS` only to the literal IP addresses of proxies
that overwrite forwarded headers. Never use a wildcard or an untrusted client
address. Leave `LUNCHMONEY_CORS_ALLOWED_ORIGINS` empty unless a browser client
is required; when it is, list complete HTTPS origins rather than a wildcard.

The defaults below apply in each web worker. Tune them for the deployed reverse
proxy and expected workload, while keeping an edge rate limit for a global,
multi-worker limit.

| Setting                                |   Default | Purpose                           |
| -------------------------------------- | --------: | --------------------------------- |
| `LUNCHMONEY_MAX_REQUEST_BODY_BYTES`    | 1,048,576 | Maximum HTTP request body size.   |
| `LUNCHMONEY_REQUEST_TIMEOUT_SECONDS`   |        30 | Maximum HTTP request duration.    |
| `LUNCHMONEY_MAX_CONCURRENT_REQUESTS`   |       100 | Per-worker in-flight request cap. |
| `LUNCHMONEY_RATE_LIMIT_REQUESTS`       |       120 | Per-client request allowance.     |
| `LUNCHMONEY_RATE_LIMIT_WINDOW_SECONDS` |        60 | Rate-limit window in seconds.     |

## Secret rotation

Rotate the API key, Lunch Money access token, and database/Redis credentials on
a schedule and immediately after suspected exposure. Create replacement secrets
first, update the deployment secret store, then recreate the web service and the
single scheduler. Verify `/ready`, a minimally privileged authenticated request,
and the scheduler's next run before revoking the old credential. Use a rolling
web deployment if the orchestrator supports it; do not run a second scheduler
during rotation.

## PostgreSQL backup and restore

Take encrypted, off-host logical backups at least daily. Retain daily backups
for 35 days, monthly backups for 12 months, and one tested annual archive, or
follow the organization’s stricter retention policy. Record the database schema
revision with each backup. At least quarterly, restore a backup into an isolated
environment and verify `/ready` before considering it recoverable.

Create a custom-format backup without placing its contents in a container:

```bash
backup_file="lunchmoney-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose exec -T postgres pg_dump \
  --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" \
  --format=custom --no-owner --no-privileges > "$backup_file"
```

Test a restore against an isolated PostgreSQL database first. To restore the
production database, first stop the web and scheduler services, ensure the
backup is the intended one, and have an approved maintenance window. The command
below replaces existing objects in the target database and is deliberately
destructive:

```bash
docker compose stop app scheduler
docker compose exec -T postgres pg_restore \
  --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" \
  --clean --if-exists --no-owner --single-transaction < "$backup_file"
docker compose up --detach app
curl --fail --header "X-API-Key: $LUNCHMONEY_MCP_API_KEY" http://127.0.0.1:8000/ready
```

Keep the original backup immutable until the restored system is validated. Do
not copy production financial data into development or CI environments.

## Incident checklist

| Signal                        | Immediate action                                                                                              | Before closing                                                                                   |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `/health` fails               | Keep traffic away, inspect container status and redacted logs, then restart or roll back the web service.     | `/health` and `/ready` remain successful after the observation window.                           |
| `/ready` fails                | Check PostgreSQL and Redis health, migration status, disk space, and network policy. Do not bypass readiness. | Dependency health and a read-only authenticated request succeed.                                 |
| Suspected credential exposure | Revoke and rotate the affected secret; audit access paths and deployment history.                             | New credentials work, old credentials are rejected, and no secret value entered logs or tickets. |
| Data loss or corruption       | Stop writes and the scheduler; preserve evidence; restore only to an isolated target first.                   | Restore test, reconciliation, and owner approval are recorded.                                   |
| Upstream rate limit/failure   | Pause unnecessary syncs and inspect only redacted request metadata and retry behavior.                        | Sync succeeds at a controlled rate without duplicate scheduler instances.                        |

Collect timestamps, deployment revision, container state, and redacted error
identifiers during an incident. Never include access tokens, API keys, database
URLs with passwords, transaction data, or financial payloads in tickets or logs.
