# Bring Shopping Integration

Python integration layer for managing [Bring!](https://www.getbring.com/en/home)
shopping lists. Version 1 provides a tested service, CLI, and local stdio MCP server
over the unofficial [`bring-api`](https://github.com/miaucl/bring-api) package.

> `bring-api` is reverse engineered and is not affiliated with Bring! Labs AG.
> Upstream changes can break authentication or list operations. The dependency is
> pinned until a newer release is deliberately verified.

## Setup

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
pre-commit install
```

Set `BRING_EMAIL` and `BRING_PASSWORD` in `.env`. A Bring account created through
Google, Apple, or Facebook sign-in needs a Bring password before API login works.
Use a dedicated Bring account shared onto the target list where practical.

Verify access without changing a list:

```bash
bring-shopping doctor
bring-shopping lists
```

If more than one list is returned, put its UUID in `BRING_LIST_UUID`. Then exercise
the item operations explicitly:

```bash
bring-shopping items
bring-shopping add "Milk" --spec "2 liters"
bring-shopping complete "Milk" --item-uuid ITEM_UUID
bring-shopping remove "Milk" --item-uuid ITEM_UUID
```

Add `--json` before the subcommand for machine-readable output. `complete` moves an
item into Bring's recently used collection; `remove` permanently removes it.

## MCP Server

Run the stdio server with:

```bash
bring-shopping-mcp
```

Configure a local MCP host to launch that command with `BRING_EMAIL`, `BRING_PASSWORD`,
and one unambiguous default-list selector in its environment. The server exposes:

| Tool | Purpose |
| --- | --- |
| `bring_list_lists` | List accessible shopping lists. |
| `bring_get_items` | Read current purchase items. |
| `bring_add_items` | Add a bounded batch of items. |
| `bring_complete_items` | Move purchase items to recently used. |
| `bring_remove_items` | Permanently remove items when `confirm=true`. |

All results are structured. Mutation receipts include the MCP request ID. Adds receive a
stable UUID, name-only completion and removal reject duplicates, and batches are limited
to 20 items. The first release intentionally supports stdio only.

## Development

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest
python -m pip_audit --skip-editable
pre-commit run --all-files
```

Unit tests never connect to Bring. Live verification requires a dedicated list named
`Integration Test`, its UUID, and an explicit opt-in:

```bash
BRING_RUN_LIVE_TESTS=1 \
BRING_TEST_LIST_UUID=TEST_LIST_UUID \
python -m pytest -m live --no-cov
```

The harness refuses the configured default list, uses unique disposable items, and runs
cleanup after failures. Never run it against a normal shopping list.

On macOS, Python 3.13 skips hidden `.pth` files. If an editable install under `.venv`
cannot import `bring_shopping`, clear an inherited filesystem flag with
`chflags -R nohidden .venv` and reinstall the project.

See [architecture](docs/architecture.md), [roadmap](docs/roadmap.md),
[release plan](docs/release-plan.md),
[Google Nest and personal Bring setup](docs/setup-google-nest.md), and
[security guidance](SECURITY.md) before adding remote transports or voice-facing functionality.
