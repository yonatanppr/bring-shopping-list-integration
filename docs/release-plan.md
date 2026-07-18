# Version 1 Release Plan

## Confirmed Scope

Version 1 is a locally deployable shopping-list integration served over MCP stdio.
It includes:

- Stable tools for listing shopping lists and reading, adding, completing, and removing
  shopping items.
- The Bring service boundary and command-line diagnostics.
- Structured tool contracts, predictable errors, and mutation receipts.
- Offline tests, opt-in live contract tests, packaging checks, release automation, and
  operator documentation.
- Security controls for credentials and destructive operations.

## Excluded From Version 1

- Google Nest voice ingress.
- Speech transcription and spoken confirmations.
- Remotely accessible MCP transports.
- General natural-language parsing outside the model host.

These are separate milestones and must not delay the local MCP release.

## Current State

The Bring service and command-line interface build successfully and pass the existing
lint, format, type, and unit-test gates. A read-only live check has verified authentication
and list discovery through `bring-api`. The dedicated `Integration Test` list exists and
is visible to the configured account.

The service, CLI, and local stdio MCP server are implemented. Offline protocol tests use
the official in-memory client transport. The live contract test has passed add, read,
complete, and remove through both the service and MCP tool layers on the dedicated list.

The suite enforces lint, format, strict typing, 85% branch coverage, dependency audit,
Python 3.11 through 3.14 compatibility, and a wheel/install smoke test in CI. An
editable-install failure was traced to the local virtual environment's macOS hidden flag:
Python 3.13 skips hidden path-configuration files. Clearing that environment flag restored
package imports. A `v*.*.*` tag reruns the release gates and attaches a wheel and source
archive to a GitHub release.

## Live Contract Tests

Live write tests must use a dedicated Bring list named `Integration Test`. The normal
default list is never a valid test target.

The test harness must:

- Require an explicit `BRING_TEST_LIST_UUID` and a separate opt-in flag.
- Verify that the test UUID differs from the configured default-list UUID.
- Create a unique item name for every run.
- Exercise add, read, complete, and remove against that item.
- Attempt cleanup in `finally`, including after partial failure.
- Run manually or on a protected schedule, never for untrusted pull requests.

`bring-api 1.1.2` cannot create shopping lists. Creating the dedicated list through the
Bring app or web interface is a one-time deployment prerequisite.

## Open Decisions

- Select and configure the local MCP host that will launch the stdio server.
- Decide whether the package should be published publicly or distributed only as release
  artifacts.
- Revisit Google Nest voice ingress only after a separate feasibility proof succeeds.
