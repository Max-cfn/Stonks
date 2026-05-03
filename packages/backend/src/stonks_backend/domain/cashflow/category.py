"""Category domain entity — classifies a transaction (e.g. "Alimentation", "Loyer")."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class CategoryGroup(StrEnum):
    """Top-level grouping of categories."""

    INCOME = "income"
    HOUSING = "housing"
    FOOD = "food"
    TRANSPORT = "transport"
    HEALTH = "health"
    SHOPPING = "shopping"
    ENTERTAINMENT = "entertainment"
    FINANCIAL = "financial"
    OTHER = "other"


@dataclass(kw_only=True, slots=True)
class Category:
    """A spending/income category.

    System categories have `user_id=None`. Users can create custom categories.
    """

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    user_id: uuid.UUID | None = None  # None = system default
    name: str
    group: CategoryGroup = CategoryGroup.OTHER
    icon: str = "📦"
    color_hex: str = "#808080"
    parent_id: uuid.UUID | None = None  # For sub-categories
    is_system: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Category name must not be empty")
