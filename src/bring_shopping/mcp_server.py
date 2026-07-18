"""Local stdio MCP server for Bring shopping-list operations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Literal
from uuid import uuid4

from bring_api.exceptions import BringException
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.session import ServerSession
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import BaseModel, ConfigDict, Field

from bring_shopping.exceptions import BringIntegrationError
from bring_shopping.models import ShoppingItem, ShoppingList
from bring_shopping.service import BringShoppingService, connect_bring
from bring_shopping.settings import BringSettings

MAX_BATCH_ITEMS = 20
MAX_RESULT_ITEMS = 500


class ToolModel(BaseModel):
    """Strict base model for MCP input and output contracts."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AddItemInput(ToolModel):
    """One item to add to a shopping list."""

    name: str = Field(min_length=1, max_length=200)
    specification: str = Field(default="", max_length=500)


class ItemTargetInput(ToolModel):
    """One existing purchase item to complete or remove."""

    name: str = Field(min_length=1, max_length=200)
    specification: str = Field(default="", max_length=500)
    item_uuid: str | None = Field(default=None, min_length=1, max_length=100)


class ShoppingListOutput(ToolModel):
    """Shopping-list data returned by a tool."""

    uuid: str
    name: str
    theme: str


class ShoppingItemOutput(ToolModel):
    """Current purchase-item data returned by a tool."""

    uuid: str
    name: str
    specification: str


class ListsOutput(ToolModel):
    """All shopping lists visible to the configured account."""

    lists: list[ShoppingListOutput]


class ItemsOutput(ToolModel):
    """A bounded page of current purchase items."""

    shopping_list: ShoppingListOutput
    items: list[ShoppingItemOutput]
    total_count: int
    truncated: bool


class MutationItemOutput(ToolModel):
    """One item included in a successful mutation receipt."""

    name: str
    specification: str
    item_uuid: str | None


class MutationOutput(ToolModel):
    """Structured receipt for a successful batch mutation."""

    request_id: str
    action: Literal["added", "completed", "removed"]
    shopping_list: ShoppingListOutput
    items: list[MutationItemOutput]


@dataclass(frozen=True, slots=True)
class AppContext:
    """Dependencies shared for the lifetime of one server process."""

    service: BringShoppingService


ToolContext = Context[ServerSession, AppContext, object]
BatchAddItems = Annotated[list[AddItemInput], Field(min_length=1, max_length=MAX_BATCH_ITEMS)]
BatchItemTargets = Annotated[list[ItemTargetInput], Field(min_length=1, max_length=MAX_BATCH_ITEMS)]
ListUuid = Annotated[str | None, Field(min_length=1, max_length=100)]
ResultLimit = Annotated[int, Field(ge=1, le=MAX_RESULT_ITEMS)]

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)
ADDITIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)
DESTRUCTIVE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=True,
)


def _service(ctx: ToolContext) -> BringShoppingService:
    return ctx.request_context.lifespan_context.service


def _list_output(shopping_list: ShoppingList) -> ShoppingListOutput:
    return ShoppingListOutput.model_validate(shopping_list, from_attributes=True)


def _item_output(item: ShoppingItem) -> ShoppingItemOutput:
    return ShoppingItemOutput.model_validate(item, from_attributes=True)


def _tool_failure(
    action: str,
    error: BringIntegrationError | BringException,
    *,
    completed: int = 0,
    total: int = 1,
) -> ToolError:
    if isinstance(error, BringIntegrationError):
        detail = str(error)
    else:
        detail = "Bring rejected the request or was unavailable"
    if completed:
        detail = (
            f"{detail}. At least {completed} of {total} items were confirmed before the failure; "
            "read the list before retrying"
        )
    return ToolError(f"Could not {action}: {detail}")


def create_server(
    service: BringShoppingService | None = None,
    *,
    json_response: bool = False,
    stateless_http: bool = False,
    transport_security: TransportSecuritySettings | None = None,
) -> FastMCP[AppContext]:
    """Build a server, optionally injecting an offline service for tests."""

    @asynccontextmanager
    async def lifespan(_: FastMCP[AppContext]) -> AsyncIterator[AppContext]:
        if service is not None:
            yield AppContext(service=service)
            return
        settings = BringSettings.from_env()
        async with connect_bring(settings) as connected_service:
            yield AppContext(service=connected_service)

    server = FastMCP(
        "Bring Shopping",
        instructions=(
            "Manage Bring shopping lists. Preserve item wording, put quantities in the "
            "specification field, and read items before ambiguous completion or removal."
        ),
        lifespan=lifespan,
        json_response=json_response,
        stateless_http=stateless_http,
        transport_security=transport_security,
    )

    @server.tool(
        name="bring_list_lists",
        title="List Bring shopping lists",
        annotations=READ_ONLY,
    )
    async def list_lists(ctx: ToolContext) -> ListsOutput:
        """List every shopping list visible to the configured Bring account."""
        try:
            lists = await _service(ctx).list_lists()
        except (BringIntegrationError, BringException) as error:
            raise _tool_failure("list shopping lists", error) from error
        return ListsOutput(lists=[_list_output(item) for item in lists])

    @server.tool(
        name="bring_get_items",
        title="Read Bring shopping items",
        annotations=READ_ONLY,
    )
    async def get_items(
        ctx: ToolContext,
        list_uuid: ListUuid = None,
        limit: ResultLimit = 200,
    ) -> ItemsOutput:
        """Read current purchase items from one unambiguously selected shopping list."""
        try:
            selected = await _service(ctx).resolve_list(list_uuid)
            items = await _service(ctx).get_items(list_uuid=selected.uuid)
        except (BringIntegrationError, BringException) as error:
            raise _tool_failure("read shopping items", error) from error
        return ItemsOutput(
            shopping_list=_list_output(selected),
            items=[_item_output(item) for item in items[:limit]],
            total_count=len(items),
            truncated=len(items) > limit,
        )

    @server.tool(
        name="bring_add_items",
        title="Add Bring shopping items",
        annotations=ADDITIVE,
    )
    async def add_items(
        items: BatchAddItems,
        ctx: ToolContext,
        list_uuid: ListUuid = None,
    ) -> MutationOutput:
        """Add up to 20 items, using specification for quantities and qualifiers."""
        receipts: list[MutationItemOutput] = []
        selected: ShoppingList | None = None
        for item in items:
            item_uuid = str(uuid4())
            try:
                selected = await _service(ctx).add_item(
                    item.name,
                    specification=item.specification,
                    item_uuid=item_uuid,
                    list_uuid=list_uuid,
                )
            except (BringIntegrationError, BringException) as error:
                raise _tool_failure(
                    "add shopping items",
                    error,
                    completed=len(receipts),
                    total=len(items),
                ) from error
            receipts.append(
                MutationItemOutput(
                    name=item.name,
                    specification=item.specification,
                    item_uuid=item_uuid,
                )
            )
        assert selected is not None
        return MutationOutput(
            request_id=str(ctx.request_id),
            action="added",
            shopping_list=_list_output(selected),
            items=receipts,
        )

    @server.tool(
        name="bring_complete_items",
        title="Complete Bring shopping items",
        annotations=DESTRUCTIVE,
    )
    async def complete_items(
        items: BatchItemTargets,
        ctx: ToolContext,
        list_uuid: ListUuid = None,
    ) -> MutationOutput:
        """Move up to 20 purchase items to Bring's recently used items."""
        receipts: list[MutationItemOutput] = []
        selected: ShoppingList | None = None
        for item in items:
            try:
                selected = await _service(ctx).complete_item(
                    item.name,
                    specification=item.specification,
                    item_uuid=item.item_uuid,
                    list_uuid=list_uuid,
                )
            except (BringIntegrationError, BringException) as error:
                raise _tool_failure(
                    "complete shopping items",
                    error,
                    completed=len(receipts),
                    total=len(items),
                ) from error
            receipts.append(
                MutationItemOutput(
                    name=item.name,
                    specification=item.specification,
                    item_uuid=item.item_uuid,
                )
            )
        assert selected is not None
        return MutationOutput(
            request_id=str(ctx.request_id),
            action="completed",
            shopping_list=_list_output(selected),
            items=receipts,
        )

    @server.tool(
        name="bring_remove_items",
        title="Permanently remove Bring shopping items",
        annotations=DESTRUCTIVE,
    )
    async def remove_items(
        items: BatchItemTargets,
        confirm: bool,
        ctx: ToolContext,
        list_uuid: ListUuid = None,
    ) -> MutationOutput:
        """Permanently remove up to 20 items; confirm must be true."""
        if not confirm:
            raise ToolError("Permanent removal requires confirm=true")
        receipts: list[MutationItemOutput] = []
        selected: ShoppingList | None = None
        for item in items:
            try:
                selected = await _service(ctx).remove_item(
                    item.name,
                    item_uuid=item.item_uuid,
                    list_uuid=list_uuid,
                )
            except (BringIntegrationError, BringException) as error:
                raise _tool_failure(
                    "remove shopping items",
                    error,
                    completed=len(receipts),
                    total=len(items),
                ) from error
            receipts.append(
                MutationItemOutput(
                    name=item.name,
                    specification=item.specification,
                    item_uuid=item.item_uuid,
                )
            )
        assert selected is not None
        return MutationOutput(
            request_id=str(ctx.request_id),
            action="removed",
            shopping_list=_list_output(selected),
            items=receipts,
        )

    return server


server = create_server()


def main() -> None:
    """Run the local stdio MCP server."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
