# Bring Shopping Integration

Python integration layer for managing [Bring!](https://www.getbring.com/en/home)
shopping lists. It provides a tested service, CLI, local stdio MCP server, and a
self-hosted HTTPS deployment for remote MCP clients such as ChatGPT.

> `bring-api` is reverse engineered and is not affiliated with Bring! Labs AG.
> Upstream changes can break authentication or list operations. The dependency is
> pinned until a newer release is deliberately verified.

## Self-host with HTTPS

The supported deployment runs on 64-bit macOS, Windows, and Linux—including Ubuntu and
Raspberry Pi OS. It needs Docker Desktop or Docker Engine, a Bring account, a free personal
Tailscale account, and a ChatGPT account that can create custom MCP apps. It needs no
domain, public IP, port forwarding, OpenAI API key, or OpenAI API billing. Tailscale Funnel
is available on all plans, but the free Personal plan is for personal, non-commercial use;
check the [Tailscale plan terms](https://tailscale.com/pricing) for your use case. Docker
Desktop is also free for personal use; larger organizations must check the
[Docker Desktop terms](https://docs.docker.com/subscription/desktop-license/).

On macOS or Linux:

```bash
git clone https://github.com/yonatanppr/bring-shopping-list-integration.git
cd bring-shopping-list-integration
./deploy/bootstrap.sh
```

On Windows, open Command Prompt or PowerShell:

```powershell
git clone https://github.com/yonatanppr/bring-shopping-list-integration.git
cd bring-shopping-list-integration
.\deploy\bootstrap.cmd
```

The guided bootstrap can install Docker after confirmation. It then:

1. stores secrets in a protected `.env` (`0600` on Unix; current-user ACL on Windows);
2. opens a one-time Tailscale browser enrollment;
3. authenticates to Bring read-only and asks you to confirm an exact list UUID;
4. starts the loopback-only MCP container and validates MCP initialization;
5. enables Tailscale Funnel and prints the capability URL to enter in ChatGPT.

No inbound firewall rule or host port is required. Only the unguessable URL ending in
`/<64-hex-character-secret>/mcp` reaches MCP; every other public path returns 404. Treat
the complete URL like a password. See the [deployment guide](docs/deployment.md) and
[ChatGPT pilot](docs/chatgpt-pilot.md).

> ChatGPT plan availability is separate from API billing. The server never calls the
> OpenAI API, but OpenAI's current [developer-mode documentation](https://help.openai.com/en/articles/12584461)
> does not guarantee write-capable custom MCP apps on Plus. Confirm that your ChatGPT UI
> exposes the five tools and permits write actions before relying on the pilot.

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

## Local stdio MCP server

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
to 20 items. The stdio and HTTPS transports expose the same tool contract.

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

See [deployment](docs/deployment.md),
[ChatGPT pilot](docs/chatgpt-pilot.md),
[Google Nest and personal Bring setup](docs/setup-google-nest.md), and
[security guidance](SECURITY.md) before adding remote transports or voice-facing functionality.
