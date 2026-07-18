# Agent Guide

## Mission

Build a secure Bring shopping-list integration in layers: vendor adapter, application
service, MCP transport, then voice/LLM orchestration. Keep each layer independently
testable and do not claim Google Nest support without a working ingress proof of concept.

## Start Here

Read `README.md`, `docs/architecture.md`, `SECURITY.md`, and the project skill at
`.agents/skills/bring-shopping-integration/SKILL.md` before changing integration code.

## Commands

```bash
python -m pip install -e '.[dev]'
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
pre-commit run --all-files
```

## Engineering Rules

- Support Python 3.11 and newer; use async I/O at external boundaries.
- Keep vendor response types inside `service.py`; return application dataclasses.
- Extend the `BringApi` protocol only for operations the application actually uses.
- Keep MCP handlers thin. Validation, list selection, and item behavior belong in the
  service layer.
- Never silently choose among multiple lists or duplicate items.
- Preserve `bring-api==1.1.2` until an upgrade is verified against its typed models and a
  disposable live list.
- Use structured serializers and MCP schemas, not string-built JSON.

## Safety Rules

- Never read, print, commit, or place `.env` or credential values in model context.
- Unit tests must not access the network or a real Bring account.
- Live mutations require an explicit operator action and a known list UUID.
- Permanent or bulk removal must be confirmation-gated at the LLM/MCP boundary.
- Bind future MCP network transports to localhost unless authentication and TLS are part
  of the same change.

## Definition of Done

Run Ruff lint and format checks, strict mypy, pytest, and skill validation. Update the
architecture or roadmap when a boundary, dependency, MCP contract, or voice assumption
changes.
