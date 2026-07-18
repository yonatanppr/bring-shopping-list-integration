# Setup With Bring and Google Nest

This guide configures the project for a personal Bring shopping list and explains the
current Google Nest limitation. Complete the Bring and MCP sections first; they provide a
working shopping-list integration independently of the voice endpoint.

## What You Need

- A Bring account with an email address and password.
- A personal Bring list, or a dedicated integration account shared onto that list.
- An always-on computer or server with Python 3.11 or newer.
- An MCP-capable model host if you want the repository's MCP tools.
- For free-form voice commands, Home Assistant plus an Assist-capable microphone and
  speaker.

Use a dedicated Bring account where practical. Share the personal list with that account
from the Bring app. This limits the lists available to the integration and makes password
rotation less disruptive. Accounts created with Google, Apple, or Facebook sign-in must
first set a Bring password. Home Assistant documents this requirement in its
[Home Assistant integration prerequisites](https://www.home-assistant.io/integrations/bring/#prerequisites).

## 1. Install the Project

Clone the repository on the computer that will run the integration, then install it in a
virtual environment:

```bash
git clone https://github.com/yonatanppr/bring-shopping-list-integration.git
cd bring-shopping-list-integration
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install .
cp .env.example .env
```

Keep this computer on whenever the voice or MCP integration needs to be available.

## 2. Configure Bring

Open `.env` and set the account credentials:

```dotenv
BRING_EMAIL=integration-account@example.com
BRING_PASSWORD=replace-with-the-bring-password
BRING_REQUEST_TIMEOUT_SECONDS=20
```

Do not commit `.env`. It is ignored by Git, but it still contains a reusable password.

Confirm that authentication works and list the account's accessible lists:

```bash
set -a
source .env
set +a
bring-shopping doctor
bring-shopping lists
```

Copy the UUID of the personal list into `.env`:

```dotenv
BRING_LIST_UUID=replace-with-the-personal-list-uuid
```

Prefer the UUID over `BRING_LIST_NAME`; it remains unambiguous if a list is renamed. Load
the updated environment and perform a reversible smoke test:

```bash
set -a
source .env
set +a
bring-shopping items
bring-shopping add "Setup Test Item" --spec "remove after verification"
```

Check the Bring app on a phone. After the item appears, get its UUID and remove it:

```bash
bring-shopping items
bring-shopping remove "Setup Test Item" --item-uuid ITEM_UUID
```

## 3. Connect an MCP Host

The MCP server uses local stdio transport. Configure the MCP host on the same machine to
start the executable and pass the Bring settings as environment variables. A typical
server entry has this shape:

```json
{
  "mcpServers": {
    "bring-shopping": {
      "command": "/absolute/path/to/bring-shopping-list-integration/.venv/bin/bring-shopping-mcp",
      "env": {
        "BRING_EMAIL": "integration-account@example.com",
        "BRING_PASSWORD": "replace-with-the-bring-password",
        "BRING_LIST_UUID": "replace-with-the-personal-list-uuid",
        "BRING_REQUEST_TIMEOUT_SECONDS": "20"
      }
    }
  }
}
```

Use the exact configuration format required by the selected host. Restart it, verify that
`bring_list_lists` and `bring_get_items` are available, then ask it to add one temporary
item. Confirm the result in Bring before relying on voice input. Do not expose this stdio
server as an unauthenticated network service.

## 4. Choose the Voice Path

### Free-form items: use Home Assistant Assist

The supported route for a phrase such as "add two liters of milk to Bring" is:

```text
Assist microphone -> Home Assistant Assist -> Bring integration -> personal Bring list
```

Home Assistant's official Bring integration exposes Bring lists as shopping-list entities
and explicitly supports adding items with Assist. Install it from **Settings > Devices &
services > Add Integration > Bring!** and provide the dedicated Bring account. Confirm that
the personal list appears as the intended shopping-list entity. Then configure an Assist
voice pipeline and an Assist-capable endpoint by following the
[Home Assistant voice setup](https://www.home-assistant.io/voice_control/).

Test the exact sentence supported by the selected language, for example:

```text
Add milk to the shopping list.
```

Verify that the item appears in the intended Bring list. Test quantities, multiple items,
corrections, and similar list names before household use. The Home Assistant path uses its
native Bring integration; it does not require this repository's MCP server.

### Google Nest speaker: current limitation

A Google Nest speaker cannot currently act as a general microphone for this project's MCP
server. Google retired custom Conversational Actions on June 13, 2023, removing the
developer path that previously handled arbitrary conversational input
([Google sunset notice](https://developers.google.com/assistant/ca-sunset)). Google Home
scripted automations provide an `assistant.event.OkGoogle` starter with a configured query,
but the schema documents comparisons against that query rather than wildcard extraction
of an arbitrary product name
([Google event schema](https://developers.home.google.com/automations/schema/reference/entity/assistant/ok_google_event)).

This means a Nest routine can recognize fixed phrases such as "shopping mode," but it
cannot take the unknown part of "add *item* to Bring" and forward that item to this app.
Keep the Nest for its normal Google Home functions and place an Assist-capable voice
endpoint nearby for free-form Bring commands. Do not expose the MCP server to the internet
in an attempt to bypass this platform restriction.

## 5. Operational Checklist

- The dedicated account can access only the required Bring lists.
- `.env` is present only on the runtime machine and is not committed or logged.
- `BRING_LIST_UUID` identifies the personal list.
- `bring-shopping doctor`, `lists`, and `items` succeed.
- A temporary CLI item appears in Bring and can be removed by UUID.
- The MCP host can read and add to the selected list.
- Permanent removal remains a confirmed action; MCP removal requires `confirm=true`.
- The always-on host restarts the selected model host or Home Assistant after reboot.
- Voice tests cover ambiguous and multi-item requests before household use.

For deployment boundaries and credential handling, also read
[Architecture](architecture.md) and [Security](../SECURITY.md).
