# Bring Shopping Integration

Manage [Bring!](https://www.getbring.com/en/home) shopping lists through a Python service,
CLI, stdio MCP server, or self-hosted HTTPS MCP endpoint.

> `bring-api` is an unofficial client. This project pins version 1.1.2 because upstream
> changes can break authentication and list operations.

## Deploy with Docker

The Docker deployment supports 64-bit macOS, Windows, and Linux on AMD64 or ARM64. You
need Docker, a Bring account, a Tailscale account, and an MCP client.

On macOS or Linux:

```bash
git clone https://github.com/yonatanppr/bring-shopping-list-integration.git
cd bring-shopping-list-integration
./deploy/bootstrap.sh
```

On Windows:

```powershell
git clone https://github.com/yonatanppr/bring-shopping-list-integration.git
cd bring-shopping-list-integration
.\deploy\bootstrap.cmd
```

Bootstrap stores credentials in `.env`, enrolls the Tailscale container, verifies Bring
access, starts the MCP server, and prints the HTTPS capability URL. Protect that URL like a
password. The deployment publishes no host port and requires no domain or port forwarding.

Read the [deployment guide](docs/deployment.md) for client setup, updates, capability
rotation, and troubleshooting.

## Local Python setup

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
Use a dedicated Bring account with access to the target list where practical.

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

Add `--json` before the subcommand for machine-readable output. `complete` moves an item
into Bring's recently used collection. `remove` deletes it.

## Local stdio MCP server

Run the stdio server with:

```bash
bring-shopping-mcp
```

Configure an MCP client to launch that command with `BRING_EMAIL`, `BRING_PASSWORD`, and
one unambiguous default-list selector in its environment. The server exposes:

| Tool | Purpose |
| --- | --- |
| `bring_list_lists` | List accessible shopping lists. |
| `bring_get_items` | Read current purchase items. |
| `bring_add_items` | Add a bounded batch of items. |
| `bring_complete_items` | Move purchase items to recently used. |
| `bring_remove_items` | Permanently remove items when `confirm=true`. |

The server returns structured results and limits batches to 20 items. Mutation receipts
include the MCP request ID. Name-only completion and removal reject duplicate matches.

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

See [Security](SECURITY.md) before exposing the HTTPS transport and
[Contributing](CONTRIBUTING.md) before submitting changes.
