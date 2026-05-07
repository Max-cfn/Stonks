STDOUT:
"""0005_cashflow_categories — create cashflow_categories table + categorization_rules.

Revision ID: 0005_cashflow_categories
Revises: 0004_cashflow_transactions
Create Date: 2026-05-02

Creates the categories table and adds the FK from cashflow_transactions.category_id
to cashflow_categories.id.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0005_cashflow_categories"
down_revision: str | None = "0004_cashflow_transactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Categories table
    op.create_table(
        "cashflow_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("group_name", sa.String(64), nullable=False, server_default="other"),
        sa.Column("icon", sa.String(8), nullable=False, server_default="📦"),
        sa.Column("color_hex", sa.String(7), nullable=False, server_default="#808080"),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # Name must be unique per user (or globally for system categories, user_id IS NULL)
        sa.UniqueConstraint("user_id", "name", name="uq_user_category_name"),
    )

    # 2. Categorization rules table (regex-based rules)
    op.create_table(
        "categorization_rules",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cashflow_categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pattern", sa.String(512), nullable=False),
        sa.Column("field", sa.String(32), nullable=False, server_default="description"),
        sa.Column("is_regex", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("category_id", "pattern", name="uq_category_pattern"),
    )

    # 3. Add FK from cashflow_transactions.category_id → cashflow_categories.id
    op.create_foreign_key(
        "fk_transactions_category",
        "cashflow_transactions",
        "cashflow_categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. Seed system default categories
    _seed_default_categories(op)


def downgrade() -> None:
    op.drop_constraint("fk_transactions_category", "cashflow_transactions", type_="foreignkey")
    op.drop_table("categorization_rules")
    op.drop_table("cashflow_categories")


def _seed_default_categories(op) -> None:
    """Insert system default categories."""
    from sqlalchemy.sql import text

    categories = [
        ("INCOME", "Salaire", "💰", "#2E7D32"),
        ("INCOME", "Freelance", "💻", "#2E7D32"),
        ("INCOME", "Aides", "🤝", "#2E7D32"),
        ("INCOME", "Remboursements", "↩️", "#2E7D32"),
        ("HOUSING", "Loyer", "🏠", "#E65100"),
        ("HOUSING", "Électricité", "⚡", "#E65100"),
        ("HOUSING", "Eau", "💧", "#E65100"),
        ("HOUSING", "Internet", "🌐", "#E65100"),
        ("HOUSING", "Assurance habitation", "🛡️", "#E65100"),
        ("FOOD", "Courses", "🛒", "#4CAF50"),
        ("FOOD", "Restaurant", "🍽️", "#4CAF50"),
        ("FOOD", "Café", "☕", "#4CAF50"),
        ("FOOD", "Livraison", "🛵", "#4CAF50"),
        ("TRANSPORT", "Essence", "⛽", "#1976D2"),
        ("TRANSPORT", "Transports en commun", "🚇", "#1976D2"),
        ("TRANSPORT", "Péage", "🛣️", "#1976D2"),
        ("TRANSPORT", "Parking", "🅿️", "#1976D2"),
        ("HEALTH", "Pharmacie", "💊", "#D32F2F"),
        ("HEALTH", "Médecin", "🩺", "#D32F2F"),
        ("HEALTH", "Mutuelle", "🏥", "#D32F2F"),
        ("SHOPPING", "Vêtements", "👕", "#9C27B0"),
        ("SHOPPING", "Électronique", "📱", "#9C27B0"),
        ("SHOPPING", "Maison", "🪴", "#9C27B0"),
        ("ENTERTAINMENT", "Abonnements", "📺", "#FF5722"),
        ("ENTERTAINMENT", "Loisirs", "🎮", "#FF5722"),
        ("ENTERTAINMENT", "Voyages", "✈️", "#FF5722"),
        ("ENTERTAINMENT", "Sport", "🏋️", "#FF5722"),
        ("FINANCIAL", "Frais bancaires", "🏦", "#607D8B"),
        ("FINANCIAL", "Impôts", "📝", "#607D8B"),
        ("FINANCIAL", "Crédit", "💳", "#607D8B"),
        ("OTHER", "Divers", "📦", "#808080"),
    ]

    stmt = text(
        "INSERT INTO cashflow_categories (id, user_id, name, group_name, icon, color_hex, is_system) "
        "VALUES (:id, NULL, :name, :group_name, :icon, :color_hex, TRUE)"
    )
    import uuid

    for group, name, icon, color in categories:
        op.execute(stmt.bindparams(
            id=uuid.uuid4(), name=name, group_name=group.lower(), icon=icon, color_hex=color
        ))

STDERR:

CODE: 0