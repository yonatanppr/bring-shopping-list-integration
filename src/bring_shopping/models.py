"""Stable application models independent of the upstream Bring response types."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ShoppingList:
    """A Bring shopping list available to the authenticated account."""

    uuid: str
    name: str
    theme: str


@dataclass(frozen=True, slots=True)
class ShoppingItem:
    """An item currently waiting to be purchased."""

    uuid: str
    name: str
    specification: str
