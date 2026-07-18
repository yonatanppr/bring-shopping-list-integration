---
name: bring-shopping-integration
description: Build, change, test, or diagnose this repository's Bring shopping-list adapter and local MCP server. Use for bring-api authentication, list or item selection, shopping mutations, structured MCP tools, packaging, or guarded live Bring contract tests.
---

# Bring Shopping Integration

Keep the vendor adapter, application service, MCP transport, and voice ingress as separate
layers. Read `../../../AGENTS.md`, `../../../docs/architecture.md`, and
`../../../SECURITY.md` before changing runtime behavior.

## Workflow

1. Identify whether the change belongs to vendor connection, service behavior, MCP
   transport, or voice orchestration.
2. Read [references/bring-api.md](references/bring-api.md) before changing vendor calls or
   response mapping.
3. Put validation, deterministic list selection, and mutation behavior in
   `BringShoppingService`; keep transports thin.
4. Extend the `BringApi` protocol only when the application uses a new vendor operation.
5. Add offline tests using an in-memory protocol implementation. Never use credentials or
   network access in unit tests.
6. Add protocol tests with the official in-memory MCP client for tool changes.
7. Run Ruff lint and format checks, strict mypy, pytest, and the dependency audit.
8. Treat live verification as an explicit operator action against the dedicated test list.

## Guardrails

- Never inspect, print, commit, or pass `.env` values into prompts.
- Never select the first list when multiple lists exist.
- Prefer list and item UUIDs for mutations; report ambiguity instead of guessing.
- Preserve the user's item wording and use `specification` for quantities or qualifiers.
- Require `confirm=true` for permanent removal at the MCP boundary.
- Keep tool batches and read results bounded, and return structured receipts.
- Keep `bring-api` pinned until its typed response contract and live behavior are verified.
- Do not treat MCP as a Google Nest audio ingress. Keep the feasibility gate in
  `docs/roadmap.md` current.

## Verification

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
python -m pip_audit --skip-editable
```

Only after offline checks pass, use `bring-shopping doctor` for a read-only live check.
Live mutations require `BRING_RUN_LIVE_TESTS=1`, an explicit `BRING_TEST_LIST_UUID`, and
the dedicated list named `Integration Test`.
