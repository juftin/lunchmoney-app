# Upstream API Compatibility Policy

Lunch Money v2 is an alpha API. This project therefore treats any upstream
change as a compatibility review, not an automatic dependency upgrade.

## Pinned inputs

`pyproject.toml` pins both the generated Python client and the OpenAPI package
that produced its reviewed contract. `docs/upstream-contract.json` records the
reviewed endpoint, schema, and enum fingerprints. `docs/upstream-coverage.json`
maps every one of the 39 generated operations to its service function, REST
operation, and MCP tool.

Run `task upstream:check` to download the exact pinned specification and verify
that it still agrees with the generated client and reviewed snapshot. CI runs
this check on every change.

## Reviewing an upgrade

1. Read Lunch Money's release notes and deprecation notices for the proposed
   OpenAPI version.
2. Update the exact generated-client and OpenAPI-package pins together, then
   regenerate the lockfile with `task lock`.
3. Run `task upstream:refresh` and review the contract diff. Endpoint, schema,
   or enum changes require corresponding service, REST, MCP, and manifest
   changes before acceptance.
4. Run `task contract` and the standard `task fix`, `task lint`, `task check`,
   and `task test` verification suite.

## Upstream integration checks

`task contract` calls Lunch Money's official static mock service at
`https://mock.lunchmoney.dev/v2`. It uses a synthetic bearer token and only
read-only operations, so it never accesses or changes financial data. Mutation
behavior remains covered by the project's synthetic unit tests. A disposable
Lunch Money test budget may be used for a manual write-path review; never use a
production budget or production access token for this purpose.

## Breaking changes

Do not merge a client/spec upgrade when the snapshot, coverage manifest, or
mock contract fails. Record the upstream version and affected operations in the
pull request, decide whether to adapt or temporarily drop support, update the
manifest deliberately, and retain a regression test for the chosen behavior.
