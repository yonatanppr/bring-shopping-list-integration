# Roadmap

## Phase 1: Bring API Integration

- [x] Pin and wrap `bring-api`.
- [x] Load credentials and default list selection from the environment.
- [x] Support list, read, add, complete, and remove operations.
- [x] Provide an executable CLI and offline unit tests.
- [x] Run `bring-shopping doctor` with real credentials.
- [x] Verify add, read, complete, and remove on a disposable test list.

## Phase 2: MCP Server

- [x] Add the official Python MCP SDK as a bounded runtime dependency.
- [x] Define structured tool input/output models and predictable errors.
- [x] Implement stdio transport over `BringShoppingService`.
- [x] Add protocol tests using an in-memory `BringApi` implementation.
- [x] Add mutation receipts, request correlation, and bounded retry behavior.
- [ ] Register the server in the chosen LLM host and run end-to-end tool calls.

## Phase 3: Voice and LLM Orchestration

- [ ] Select the always-on host for speech-to-text, the LLM, and MCP client.
- [ ] Define multilingual item parsing, confirmation, and correction behavior.
- [ ] Add trace IDs and redacted operational metrics.
- [ ] Exercise noisy, ambiguous, multi-item, and duplicate-item utterances.

## Google Nest Feasibility Gate

Bring states that Google stopped third-party Notes & Lists integrations in June 2023,
so Bring can no longer be selected directly as the Google Assistant shopping list:
[Bring support notice](https://www.getbring.com/blog-posts/google-assistant-no-more-support-for-third-party-list-apps).
Google also retired custom Conversational Actions:
[Google sunset notice](https://developers.google.com/assistant/ca-sunset).

Google Home scripted automations currently document exact query matching with
`assistant.event.OkGoogle`; they do not document wildcard capture of an arbitrary item
inside a phrase:
[OkGoogle event schema](https://developers.home.google.com/automations/schema/reference/entity/assistant/ok_google_event).
Therefore a direct Nest command such as "add arbitrary-item to Bring" is not a supported
integration path that this MCP server alone can unlock.

Before promising Nest support, run a separate proof of concept against the user's actual
Google Home environment. The supported fallback is Home Assistant's Bring integration
with Home Assistant Assist on an Assist-capable microphone endpoint:
[Home Assistant Bring integration](https://www.home-assistant.io/integrations/bring).
That can meet the voice outcome, but a Google Nest speaker may not be usable as the audio
endpoint.
