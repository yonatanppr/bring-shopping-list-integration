# Architecture

## Target Flow

```text
voice ingress -> speech transcript -> LLM host -> MCP client
    -> Bring MCP server -> BringShoppingService -> bring-api -> Bring cloud
```

The repository implements the Bring adapter, application service, CLI, and local stdio
MCP transport. Voice capture and model orchestration must not be embedded into them.

## Boundaries

### Application Models

`ShoppingList` and `ShoppingItem` are stable dataclasses returned to transports. They
prevent vendor camel-case fields and serialization details from becoming MCP contracts.

### Service

`BringShoppingService` owns validation and deterministic list selection. It accepts a
small `BringApi` protocol, which keeps unit tests offline and gives future adapters one
contract. It never selects the first list when multiple lists exist.

### Vendor Connection

`connect_bring` owns one `aiohttp.ClientSession`, authenticates once, and closes the
session on exit. Only this composition boundary constructs the upstream `Bring` client.

### CLI

The CLI is an acceptance surface for the service. It is not an MCP implementation.
Its JSON output is useful for diagnostics but is not a versioned protocol.

## MCP Contract

The MCP server should be a thin transport over the service and initially expose:

| Tool | Behavior |
| --- | --- |
| `bring_list_lists` | Read available list names and UUIDs. |
| `bring_get_items` | Read current purchase items and stable item UUIDs. |
| `bring_add_items` | Add up to 20 validated item/specification pairs. |
| `bring_complete_items` | Complete items, preferring item UUIDs. |
| `bring_remove_items` | Permanently remove items with confirmation metadata. |

Tool results are structured and bounded and do not expose credentials or vendor
authentication responses. Mutation receipts include the protocol request ID. Permanent
removal requires `confirm=true`. The server uses stdio; a network transport would require
authentication, transport encryption, rate limits, and separate deployment review.

The server uses one authenticated service session for its process lifetime. The MCP SDK
is constrained to the stable 1.x line until version 2 is stable and its migration is
tested.

## Failure And Retry Policy

The application does not add retries around mutations. `bring-api` performs one internal
retry for HTTP 502, 503, or 504 responses. Add calls use a stable UUID for that retry, and
complete and remove calls prefer the existing item UUID. Each HTTP request has the
configured timeout; a retried operation can take longer because the upstream delay occurs
between requests.

A failed batch may be partially applied. The tool error reports how many items were
confirmed before the failure and instructs the caller to read the list before retrying.
Authentication and upstream errors are sanitized at the MCP boundary.

## LLM Policy

- Use an explicitly configured list unless the user names another accessible list.
- Do not guess between duplicate list names or duplicate items.
- Preserve the user's item wording; put quantities and qualifiers in `specification`.
- Make a single tool call for a parsed multi-item utterance when batch support exists.
- Read before completing or removing when an item UUID is not already known.
- Return a concise action receipt suitable for spoken confirmation.
