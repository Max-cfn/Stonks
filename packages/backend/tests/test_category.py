"""Tests for category domain entity."""

import pytest

from stonks_backend.domain.cashflow.category import Category, CategoryGroup


class TestCategory:
    def test_create_system_category(self):
        cat = Category(
            name="Courses",
            group=CategoryGroup.FOOD,
            icon="🛒",
            color_hex="#4CAF50",
            is_system=True,
        )
        assert cat.name == "Courses"
        assert cat.group == CategoryGroup.FOOD
        assert cat.icon == "🛒"
        assert cat.is_system

    def test_create_user_category(self):
        import uuid

        user_id = uuid.uuid4()
        cat = Category(
            user_id=user_id,
            name="Mon abonnement spécial",
            group=CategoryGroup.ENTERTAINMENT,
        )
        assert cat.user_id == user_id
        assert not cat.is_system

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            Category(name="")

    def test_blank_name_raises(self):
        with pytest.raises(ValueError, match="must not be empty"):
            Category(name="   ")


class TestCategoryGroup:
    def test_all_groups(self):
        expected = {
            "income",
            "housing",
            "food",
            "transport",
            "health",
            "shopping",
            "entertainment",
            "financial",
            "other",
        }
        assert {g.value for g in CategoryGroup} == expected

    def test_group_string_values(self):
        assert CategoryGroup.INCOME == "income"
        assert CategoryGroup.HOUSING == "housing"
        assert CategoryGroup.FOOD == "food"
        assert CategoryGroup.TRANSPORT == "transport"
        assert CategoryGroup.HEALTH == "health"
        assert CategoryGroup.SHOPPING == "shopping"
        assert CategoryGroup.ENTERTAINMENT == "entertainment"
        assert CategoryGroup.FINANCIAL == "financial"
        assert CategoryGroup.OTHER == "other"
