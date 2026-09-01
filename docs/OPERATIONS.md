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
   starting Compose, set `LUNCHMONEY_ACCESS_TOKEN`, `LUNCHMONEY_APP_API_KEY`,
   `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `LUNCHMONEY_DATABASE_URL`.
   The database URL must use the same database credentials and hostname
   `postgres`; percent-encode reserved characters in its username and password.
4. Start the API and its dependencies, then confirm the checks below. Start the
   `scheduler` profile only when exactly one scheduler process is intended.

```bash
docker compose up --build --detach --wait
curl --fail --header "X-API-Key: $LUNCHMONEY_APP_API_KEY" http://127.0.0.1:8000/health
curl --fail --header "X-API-Key: $LUNCHMONEY_APP_API_KEY" http://127.0.0.1:8000/ready
docker compose --profile scheduler up --detach scheduler
```

`/health` confirms that the process is alive. `/ready` additionally confirms
that dependencies required to serve traffic are ready. These endpoints
intentionally bypass API-key authentication so an orchestrator can detect a
failed service; keep them on the loopback deployment binding or limit them at
the reverse proxy. `/metrics` requires `LUNCHMONEY_APP_API_KEY` and must remain
available only to the operations network or an authenticated monitoring client.

## Compose deployment modes

Use one of these alternatives for a deployment. Set the required Compose
variables before every command; the default combined mode is the recommended
production topology. The `app` service exposes the REST API and streamable HTTP
MCP endpoint together at `/mcp`.

| Mode                | Command                                                                                                                                     | Result                                                                                                               |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| Combined (default)  | `docker compose up --build --detach --wait`                                                                                                 | REST API and streamable HTTP MCP in one web process.                                                                 |
| API-only            | `docker compose up --detach postgres redis` then `docker compose run --rm --service-ports app gunicorn lunchmoney_app.app.main:fastapi_app` | REST API only, with the same database and lock dependencies.                                                         |
| MCP-only            | `docker compose run --rm --service-ports app lunchmoney-app mcp --streamable-http --host 0.0.0.0 --port 8000`                               | Standalone Streamable HTTP MCP server at `/mcp`; it uses the configured persistent database and starts no scheduler. |
| Dedicated scheduler | `docker compose --profile scheduler up --build --detach scheduler`                                                                          | Adds the opt-in `schedule` process to the combined web deployment.                                                   |

The API-only and MCP-only commands are foreground processes; run them under the
process supervisor appropriate for the deployment if they are not being used
for a temporary diagnostic. Do not run the API-only and combined app commands
at the same time because both publish the configured port. The scheduler is
not a high-availability service: run exactly one `scheduler` container, even
when the web application has multiple workers or replicas.

For local, non-container MCP clients, `lunchmoney-app mcp` defaults to stdio.
Use a standalone HTTP MCP process only when the MCP client is remote.

## Configuration precedence and diagnostics

For runtime settings that a command exposes as flags, configuration resolves in
this order: **CLI flags > process environment > `.env` > built-in defaults**.
Credentials and connection URLs are intentionally excluded from CLI flags; set
them in the process environment or `.env` instead. Compose's project `.env`
file is used for variable interpolation, and the values injected into a
container become process-environment values for this precedence rule.

Run `lunchmoney-app doctor` before a new deployment or after a configuration
change. It checks local configuration and dependencies only—it never calls the
Lunch Money API—and redacts secret values in its output. A non-zero exit status
means the process should not be considered ready for its requested command.

Use `lunchmoney-app version` to report the installed package version. The
release process is automated; do not manually change the version in a deployed
environment to represent an upgrade.

## Audit release dependencies

Run the following before publishing a release or after changing a dependency:

```bash
task security
```

This audits the locked production Python dependency set with `uv audit` and
fails when it finds a known vulnerability. It does not inspect the operating
system, container configuration, or secrets; CI continues to use Trivy for
those release-image and repository checks.

## Releases and upgrades

Releases are created from the configured release branches by semantic-release.
Its prepare step updates the package and every versioned agent-bundle manifest
in one commit, builds the Python distributions and MCPB, and renders
release-specific MCP Registry metadata. Its GitHub plugin attaches every
artifact to the GitHub release, then its publish hook publishes the immutable
MCPB metadata to the official MCP Registry. The pre-existing `publish.yaml`
workflow publishes the Python distributions to PyPI independently. Treat GitHub
release notes as the authoritative compatibility and migration record.

Before enabling the first release, configure PyPI Trusted Publishing for the
`juftin/lunchmoney-app` repository, workflow `publish.yaml`, and the protected
`pypi` environment. Semantic Release's MCP Registry publish hook uses GitHub
OIDC and needs no stored registry credential.

Upgrade a Compose deployment in a maintenance window:

1. Read the target release notes and confirm its supported Python, database, and
   configuration requirements.
2. Take and verify an off-host PostgreSQL backup as described below. Keep the
   previous image or source revision available for rollback.
3. Update the checked-out release or image reference, then recreate the web
   service: `docker compose up --build --detach --wait`.
4. If scheduling is enabled, recreate the single scheduler too:
   `docker compose --profile scheduler up --build --detach scheduler`.
   Do not start a second scheduler while the old one is still running.
5. Run `lunchmoney-app doctor` in the deployment environment and verify
   `/ready`, an authenticated read-only request, and the next scheduled run.

Application startup serializes Alembic migrations with the shared migration
lock. A failed readiness check after an upgrade is a reason to stop traffic and
inspect the migration and dependency state—not to bypass the readiness check.

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
curl --fail --header "X-API-Key: $LUNCHMONEY_APP_API_KEY" http://127.0.0.1:8000/ready
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
