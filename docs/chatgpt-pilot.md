# ChatGPT Pilot

## Prerequisites

- `./deploy/bootstrap.sh` completed successfully.
- `./deploy/status.sh` reports five tools.
- ChatGPT developer mode is enabled and the account permits custom MCP write actions.

This integration never uses an OpenAI API key and does not call the OpenAI API. That means
there is no API usage billing. Subscription feature availability is different: current
[OpenAI developer-mode guidance](https://help.openai.com/en/articles/12584461)
does not guarantee full write-capable MCP apps on ChatGPT Plus. If the UI does not expose
write tools, the add/remove pilot cannot meet the no-additional-subscription requirement.

## Connect

Run `./deploy/status.sh`, then use its printed values in ChatGPT:

1. Open Settings, then Apps & Connectors, and create a custom app in developer mode.
2. Enter the complete HTTPS MCP server URL printed by the command.
3. Select **No Authentication**. The random secret embedded in the URL is the credential.
4. Save the app and confirm these five tools appear: list lists, read items, add items,
   complete items, and remove items.

Do not paste the URL into chat, screenshots, logs, or issue reports. If it is exposed, run
`./deploy/rotate-capability.sh` immediately and update the app URL.

## Reversible live check

This uses the selected personal list; a dedicated test list is not required. Choose a
unique temporary name such as `MCP Pilot 2026-07-18 1430` and ask ChatGPT to perform each
step separately:

1. “Read my current Bring shopping list. Do not change it.”
2. “Add one item named `MCP Pilot 2026-07-18 1430` with specification `temporary check`.”
3. “Read the list again and tell me the exact UUID of that temporary item.”
4. “Permanently remove only that item using its exact UUID and `confirm=true`.”
5. “Read the list once more and verify that exact UUID is gone.”

Stop if ChatGPT selects a different list, cannot return an exact item UUID, reports a
duplicate, or asks to remove by name only. Cleanup is an explicit permanent removal, not a
completion. The automated live test suite remains restricted to a dedicated
`Integration Test` list and is unrelated to this pilot.
