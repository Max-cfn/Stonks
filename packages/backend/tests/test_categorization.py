"""Tests for RuleBasedCategorizer — 50+ patterns covering FR/EN transactions."""

import uuid
from unittest.mock import AsyncMock

import pytest

from stonks_backend.domain.cashflow.money import Money
from stonks_backend.domain.cashflow.transaction_entity import Transaction
from stonks_backend.infrastructure.categorization.rule_categorizer import (
    RuleBasedCategorizer,
)


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Mock CashflowSqlRepository with empty rules and system categories."""
    from stonks_backend.domain.cashflow.category import Category, CategoryGroup

    repo = AsyncMock()
    repo.get_rule_categories_map.return_value = []
    system_cats = [
        Category(
            name="Salaire",
            group=CategoryGroup.INCOME,
            icon="💰",
            color_hex="#2E7D32",
            is_system=True,
        ),
        Category(
            name="Freelance",
            group=CategoryGroup.INCOME,
            icon="💻",
            color_hex="#2E7D32",
            is_system=True,
        ),
        Category(
            name="Remboursements",
            group=CategoryGroup.INCOME,
            icon="↩️",
            color_hex="#2E7D32",
            is_system=True,
        ),
        Category(
            name="Aides", group=CategoryGroup.INCOME, icon="🤝", color_hex="#2E7D32", is_system=True
        ),
        Category(
            name="Loyer",
            group=CategoryGroup.HOUSING,
            icon="🏠",
            color_hex="#E65100",
            is_system=True,
        ),
        Category(
            name="Électricité",
            group=CategoryGroup.HOUSING,
            icon="⚡",
            color_hex="#E65100",
            is_system=True,
        ),
        Category(
            name="Eau", group=CategoryGroup.HOUSING, icon="💧", color_hex="#E65100", is_system=True
        ),
        Category(
            name="Internet",
            group=CategoryGroup.HOUSING,
            icon="🌐",
            color_hex="#E65100",
            is_system=True,
        ),
        Category(
            name="Assurance habitation",
            group=CategoryGroup.HOUSING,
            icon="🛡️",
            color_hex="#E65100",
            is_system=True,
        ),
        Category(
            name="Courses", group=CategoryGroup.FOOD, icon="🛒", color_hex="#4CAF50", is_system=True
        ),
        Category(
            name="Restaurant",
            group=CategoryGroup.FOOD,
            icon="🍽️",
            color_hex="#4CAF50",
            is_system=True,
        ),
        Category(
            name="Café", group=CategoryGroup.FOOD, icon="☕", color_hex="#4CAF50", is_system=True
        ),
        Category(
            name="Livraison",
            group=CategoryGroup.FOOD,
            icon="🛵",
            color_hex="#4CAF50",
            is_system=True,
        ),
        Category(
            name="Essence",
            group=CategoryGroup.TRANSPORT,
            icon="⛽",
            color_hex="#1976D2",
            is_system=True,
        ),
        Category(
            name="Transports en commun",
            group=CategoryGroup.TRANSPORT,
            icon="🚇",
            color_hex="#1976D2",
            is_system=True,
        ),
        Category(
            name="Parking",
            group=CategoryGroup.TRANSPORT,
            icon="🅿️",
            color_hex="#1976D2",
            is_system=True,
        ),
        Category(
            name="Pharmacie",
            group=CategoryGroup.HEALTH,
            icon="💊",
            color_hex="#D32F2F",
            is_system=True,
        ),
        Category(
            name="Médecin",
            group=CategoryGroup.HEALTH,
            icon="🩺",
            color_hex="#D32F2F",
            is_system=True,
        ),
        Category(
            name="Mutuelle",
            group=CategoryGroup.HEALTH,
            icon="🏥",
            color_hex="#D32F2F",
            is_system=True,
        ),
        Category(
            name="Vêtements",
            group=CategoryGroup.SHOPPING,
            icon="👕",
            color_hex="#9C27B0",
            is_system=True,
        ),
        Category(
            name="Électronique",
            group=CategoryGroup.SHOPPING,
            icon="📱",
            color_hex="#9C27B0",
            is_system=True,
        ),
        Category(
            name="Maison",
            group=CategoryGroup.SHOPPING,
            icon="🪴",
            color_hex="#9C27B0",
            is_system=True,
        ),
        Category(
            name="Abonnements",
            group=CategoryGroup.ENTERTAINMENT,
            icon="📺",
            color_hex="#FF5722",
            is_system=True,
        ),
        Category(
            name="Loisirs",
            group=CategoryGroup.ENTERTAINMENT,
            icon="🎮",
            color_hex="#FF5722",
            is_system=True,
        ),
        Category(
            name="Voyages",
            group=CategoryGroup.ENTERTAINMENT,
            icon="✈️",
            color_hex="#FF5722",
            is_system=True,
        ),
        Category(
            name="Sport",
            group=CategoryGroup.ENTERTAINMENT,
            icon="🏋️",
            color_hex="#FF5722",
            is_system=True,
        ),
        Category(
            name="Frais bancaires",
            group=CategoryGroup.FINANCIAL,
            icon="🏦",
            color_hex="#607D8B",
            is_system=True,
        ),
        Category(
            name="Impôts",
            group=CategoryGroup.FINANCIAL,
            icon="📝",
            color_hex="#607D8B",
            is_system=True,
        ),
        Category(
            name="Crédit",
            group=CategoryGroup.FINANCIAL,
            icon="💳",
            color_hex="#607D8B",
            is_system=True,
        ),
        Category(
            name="Divers", group=CategoryGroup.OTHER, icon="📦", color_hex="#808080", is_system=True
        ),
    ]
    repo.get_default_categories.return_value = system_cats
    return repo


@pytest.fixture
def categorizer(mock_repo):
    return RuleBasedCategorizer(mock_repo)


def make_tx(
    description: str, amount_str: str = "-50.00", creditor: str | None = None
) -> Transaction:
    """Helper to create a test transaction."""
    return Transaction(
        account_id=uuid.uuid4(),
        amount=Money(amount_str, "EUR"),
        currency="EUR",
        description=description,
        creditor_name=creditor,
    )


@pytest.mark.asyncio
class TestCategorizationFrench:
    async def test_salaire(self, categorizer):
        cat = await categorizer.categorize(make_tx("VIR SALAIRE JANVIER 2026"))
        assert cat is not None
        assert cat.name == "Salaire"

    async def test_courses_carrefour(self, categorizer):
        cat = await categorizer.categorize(make_tx("CARREFOUR PARIS 75012 CARTE 28/01"))
        assert cat is not None
        assert cat.name == "Courses"

    async def test_courses_leclerc(self, categorizer):
        cat = await categorizer.categorize(make_tx("E.LECLERC ST DENIS"))
        assert cat is not None
        assert cat.name == "Courses"

    async def test_courses_auchan(self, categorizer):
        cat = await categorizer.categorize(make_tx("AUCHAN VELIZY 2"))
        assert cat is not None
        assert cat.name == "Courses"

    async def test_loyer(self, categorizer):
        cat = await categorizer.categorize(make_tx("LOYER JANVIER 2026"))
        assert cat is not None
        assert cat.name == "Loyer"

    async def test_restaurant(self, categorizer):
        cat = await categorizer.categorize(make_tx("RESTAURANT LE PETIT BISTROT PARIS"))
        assert cat is not None
        assert cat.name == "Restaurant"

    async def test_restaurant_mcdonalds(self, categorizer):
        cat = await categorizer.categorize(make_tx("MCDONALDS 123 PARIS"))
        assert cat is not None
        assert cat.name == "Restaurant"

    async def test_electricite_edf(self, categorizer):
        cat = await categorizer.categorize(make_tx("EDF ELECTRICITE PRELEVEMENT"))
        assert cat is not None
        assert cat.name == "Électricité"

    async def test_eau_veolia(self, categorizer):
        cat = await categorizer.categorize(make_tx("VEOLIA EAU FACTURE BIMESTRIELLE"))
        assert cat is not None
        assert cat.name == "Eau"

    async def test_internet_orange(self, categorizer):
        cat = await categorizer.categorize(make_tx("ORANGE ABONNEMENT INTERNET FIBRE"))
        assert cat is not None
        assert cat.name == "Internet"

    async def test_assurance_habitation(self, categorizer):
        cat = await categorizer.categorize(make_tx("MAIF ASSURANCE HABITATION ECHEANCE"))
        assert cat is not None
        assert cat.name == "Assurance habitation"

    async def test_essence_total(self, categorizer):
        cat = await categorizer.categorize(make_tx("TOTALENERG ESSENCE SP98"))
        assert cat is not None
        assert cat.name == "Essence"

    async def test_transports_ratp(self, categorizer):
        cat = await categorizer.categorize(make_tx("RATP NAVIGO MENSUEL"))
        assert cat is not None
        assert cat.name == "Transports en commun"

    async def test_pharmacie(self, categorizer):
        cat = await categorizer.categorize(make_tx("PHARMACIE DE LA GARE PARIS"))
        assert cat is not None
        assert cat.name == "Pharmacie"

    async def test_medecin(self, categorizer):
        cat = await categorizer.categorize(make_tx("DR DUPONT CONSULTATION 30MIN"))
        assert cat is not None
        assert cat.name == "Médecin"

    async def test_netflix(self, categorizer):
        cat = await categorizer.categorize(make_tx("NETFLIX.COM ABONNEMENT MENSUEL"))
        assert cat is not None
        assert cat.name == "Abonnements"

    async def test_spotify(self, categorizer):
        cat = await categorizer.categorize(make_tx("SPOTIFY PREMIUM ABONNEMENT"))
        assert cat is not None
        assert cat.name == "Abonnements"

    async def test_impots(self, categorizer):
        cat = await categorizer.categorize(make_tx("DGFIP IMPOTS 2026 TIERS"))
        assert cat is not None
        assert cat.name == "Impôts"

    async def test_frais_bancaires(self, categorizer):
        cat = await categorizer.categorize(make_tx("FRAIS TENUE DE COMPTE TRIMESTRE"))
        assert cat is not None
        assert cat.name == "Frais bancaires"

    async def test_remboursement(self, categorizer):
        cat = await categorizer.categorize(make_tx("REMBOURSEMENT SANTE CPAM", amount_str="+25.00"))
        assert cat is not None
        assert cat.name == "Remboursements"

    async def test_freelance_payment(self, categorizer):
        cat = await categorizer.categorize(
            make_tx("VIREMENT HONORAIRES MISSION DEV", amount_str="+3000.00")
        )
        assert cat is not None
        assert cat.name == "Freelance"

    async def test_caf(self, categorizer):
        cat = await categorizer.categorize(
            make_tx("CAF APL VERSEMENT MENSUEL", amount_str="+350.00")
        )
        assert cat is not None
        assert cat.name == "Aides"

    async def test_vetements(self, categorizer):
        cat = await categorizer.categorize(make_tx("ZARA CHAMPS ELYSEES ACHAT VETEMENTS"))
        assert cat is not None
        assert cat.name == "Vêtements"

    async def test_electronique(self, categorizer):
        cat = await categorizer.categorize(make_tx("FNAC PARIS ACHAT ELECTRONIQUE"))
        assert cat is not None
        assert cat.name == "Électronique"

    async def test_maison_ikea(self, categorizer):
        cat = await categorizer.categorize(make_tx("IKEA VELIZY ACHATS MAISON"))
        assert cat is not None
        assert cat.name == "Maison"

    async def test_voyage_airbnb(self, categorizer):
        cat = await categorizer.categorize(make_tx("AIRBNB RESERVATION VOYAGE"))
        assert cat is not None
        assert cat.name == "Voyages"

    async def test_sport(self, categorizer):
        cat = await categorizer.categorize(make_tx("BASIC FIT ABONNEMENT SALLE SPORT"))
        assert cat is not None
        assert cat.name == "Sport"

    async def test_café(self, categorizer):
        cat = await categorizer.categorize(make_tx("STARBUCKS COFFEE PARIS 75008"))
        assert cat is not None
        assert cat.name == "Café"

    async def test_livraison_ubereats(self, categorizer):
        cat = await categorizer.categorize(make_tx("UBER EATS COMMANDE LIVRAISON"))
        assert cat is not None
        assert cat.name == "Livraison"

    async def test_parking(self, categorizer):
        cat = await categorizer.categorize(make_tx("INDIGO PARKING STATIONNEMENT"))
        assert cat is not None
        assert cat.name == "Parking"


@pytest.mark.asyncio
class TestCategorizationEnglish:
    async def test_salary(self, categorizer):
        cat = await categorizer.categorize(make_tx("SALARY PAYMENT JANUARY", amount_str="+5000.00"))
        assert cat is not None
        assert cat.name == "Salaire"

    async def test_grocery_walmart(self, categorizer):
        cat = await categorizer.categorize(make_tx("WALMART SUPERMARKET GROCERY"))
        assert cat is not None
        assert cat.name == "Courses"

    async def test_rent(self, categorizer):
        cat = await categorizer.categorize(make_tx("MONTHLY RENT PAYMENT LANDLORD"))
        assert cat is not None
        assert cat.name == "Loyer"

    async def test_electricity_bill(self, categorizer):
        cat = await categorizer.categorize(make_tx("ELECTRICITY BILL POWER COMPANY"))
        assert cat is not None
        assert cat.name == "Électricité"

    async def test_water_bill(self, categorizer):
        cat = await categorizer.categorize(make_tx("WATER UTILITY BILL"))
        assert cat is not None
        assert cat.name == "Eau"

    async def test_clothing(self, categorizer):
        cat = await categorizer.categorize(make_tx("H&M CLOTHING PURCHASE"))
        assert cat is not None
        assert cat.name == "Vêtements"

    async def test_netflix_en(self, categorizer):
        cat = await categorizer.categorize(make_tx("NETFLIX SUBSCRIPTION MONTHLY"))
        assert cat is not None
        assert cat.name == "Abonnements"

    async def test_flight(self, categorizer):
        cat = await categorizer.categorize(make_tx("AIR FRANCE FLIGHT TICKET"))
        assert cat is not None
        assert cat.name == "Voyages"

    async def test_gym(self, categorizer):
        cat = await categorizer.categorize(make_tx("GYM FITNESS MEMBERSHIP"))
        assert cat is not None
        assert cat.name == "Sport"


@pytest.mark.asyncio
class TestCategorizationEdgeCases:
    async def test_unknown_transaction_returns_none(self, categorizer):
        cat = await categorizer.categorize(make_tx("XYZ ABC 123 UNKNOWN"))
        assert cat is None

    async def test_empty_description_returns_none(self, categorizer):
        cat = await categorizer.categorize(make_tx(""))
        assert cat is None

    async def test_creditor_name_match(self, categorizer):
        cat = await categorizer.categorize(make_tx("COLIS", creditor="La Poste"))
        assert cat is not None


@pytest.mark.asyncio
class TestCategorizeBatch:
    async def test_batch_mixed(self, categorizer):
        txs = [
            make_tx("CARREFOUR COURSES"),
            make_tx("SALAIRE MENSUEL", amount_str="+2500.00"),
            make_tx("UNKNOWN XYZ 123"),
            make_tx("NETFLIX ABONNEMENT"),
        ]
        results = await categorizer.categorize_batch(txs)
        assert len(results) >= 3
        assert results[0].name == "Courses"
        assert results[1].name == "Salaire"
        assert 2 not in results
