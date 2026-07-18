# Bring API Contract

The project pins `bring-api==1.1.2`, an unofficial async client requiring Python 3.11+.
It uses `aiohttp`; reuse one `ClientSession` and one authenticated `Bring` instance per
operation scope.

## Used Calls

```python
bring = Bring(session, email, password)
await bring.login()
lists = await bring.load_lists()
items = await bring.get_list(list_uuid)
await bring.save_item(list_uuid, item_name, specification, item_uuid)
await bring.complete_item(list_uuid, item_name, specification, item_uuid)
await bring.remove_item(list_uuid, item_name, item_uuid)
```

Current releases return typed dataclasses, not the dictionary shapes shown in some older
examples:

- `BringListResponse.lists: list[BringList]`
- `BringList.listUuid`, `BringList.name`, `BringList.theme`
- `BringItemsResponse.items.purchase` and `.recently`
- `BringPurchase.uuid`, `.itemId`, `.specification`

Map these fields to the repository's `ShoppingList` and `ShoppingItem` dataclasses before
returning data to a transport.

## Semantics

- `save_item` adds an item; an existing name may be updated by Bring matching rules. Pass
  a stable random UUID so an internal retry keeps the same item identity.
- `complete_item` moves an item to recently used. Supplying only a name can match the
  oldest duplicate.
- `remove_item` permanently removes an item. Prefer the item UUID obtained from
  `get_list` when duplicates are possible.
- The client retries one HTTP 502, 503, or 504 response after a randomized delay. Do not
  add an application retry around mutations; read the list after an uncertain failure.
- List UUID is the stable selector. A configured name is acceptable only when it matches
  exactly one accessible list, case-insensitively.

## Exceptions

Vendor failures inherit from `bring_api.exceptions.BringException`. Do not expose raw
authentication responses, headers, tokens, email addresses, or passwords in tool errors
or logs.

## Upgrade Procedure

Read the upstream release notes and `bring_api/types.py`, update mappings and protocol
signatures, run all offline checks, then exercise login plus add, read, complete, remove,
and cleanup on the dedicated live-test list. Do not loosen the pin based only on unit-test
success.
