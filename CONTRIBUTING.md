# Contributing

## Workflow

1. Create and activate a Python 3.11+ virtual environment.
2. Install the project with `python -m pip install -e '.[dev]'`.
3. Install hooks with `pre-commit install`.
4. Keep changes within the service, transport, or vendor-adapter boundary.
5. Run `pre-commit run --all-files` before opening a change.

## Tests

Normal tests must be deterministic and must not use real Bring credentials or network
access. Model Bring responses with an in-memory implementation of the `BringApi`
protocol. Live tests require `BRING_RUN_LIVE_TESTS=1`, an explicit
`BRING_TEST_LIST_UUID`, and the dedicated `Integration Test` list. They must never run
for an untrusted pull request.

## Dependency Updates

`bring-api` is intentionally pinned. Before changing it:

1. Read the upstream changelog and response types.
2. Run all static and unit checks.
3. Run `bring-shopping doctor` against a dedicated account.
4. Verify add, read, complete, and remove against a non-production test list.
5. Record any contract change in `docs/architecture.md`.
