"""RuleBasedCategorizer — catégorise les transactions via règles regex.

Implements CategorizationPort using a prioritized list of regex patterns.
Patterns are loaded from the database (categorization_rules table) via
the repository. Additional built-in fallback patterns cover common
FR/EN transaction labels.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING
from uuid import UUID

from stonks_backend.application.ports.cashflow import CategorizationPort
from stonks_backend.domain.cashflow.category import Category, CategoryGroup
from stonks_backend.domain.cashflow.transaction_entity import Transaction

if TYPE_CHECKING:
    from stonks_backend.infrastructure.persistence.cashflow_repo import CashflowSqlRepository

logger = logging.getLogger(__name__)


# ── Built-in fallback patterns (FR + EN) ────────────────────────────
# Format: (field, regex_pattern, category_group, category_name, icon, color)
# Priority: earlier in list = higher priority (checked first).
_BUILTIN_PATTERNS: list[tuple[str, str, CategoryGroup, str, str, str]] = [
    # INCOME
    ("description", r"\b(salaire|salaire\s*net|traitement|paie\s|salary|wage|payroll)\b",
     CategoryGroup.INCOME, "Salaire", "💰", "#2E7D32"),
    ("description", r"\b(freelance|honoraires|prestation|mission|consulting)\b",
     CategoryGroup.INCOME, "Freelance", "💻", "#2E7D32"),
    ("description", r"\b(remboursement|reimbursement|refund|remb\.?|avoir)\b",
     CategoryGroup.INCOME, "Remboursements", "↩️", "#2E7D32"),
    ("description", r"\b(CAF|alloc|APL|aides?|bourse|scholarship|grant)\b",
     CategoryGroup.INCOME, "Aides", "🤝", "#2E7D32"),

    # HOUSING
    ("description", r"\b(loyer|rent|charges?\s*copro|propri[ée]taire|landlord)\b",
     CategoryGroup.HOUSING, "Loyer", "🏠", "#E65100"),
    # ⚠️ "total\s+energ" (with space) to avoid matching "TOTALENERG" (fuel station)
    ("description", r"\b([ée]lectricit[ée]|EDF|engie|total\s+energ|electricity|power)\b",
     CategoryGroup.HOUSING, "Électricité", "⚡", "#E65100"),
    ("description", r"\b(eau|water|veolia|suez|saur)\b",
     CategoryGroup.HOUSING, "Eau", "💧", "#E65100"),
    ("description", r"\b(internet|fibre|box|orange|free|bouygues|sfr|broadband)\b",
     CategoryGroup.HOUSING, "Internet", "🌐", "#E65100"),
    ("description", r"\b(assurance\s*hab|home\s*insur|MAIF|MMA|axa\b|matmut|maaf|allianz)\b",
     CategoryGroup.HOUSING, "Assurance habitation", "🛡️", "#E65100"),

    # FOOD
    ("description", r"\b(courses?|supermarch[ée]|carrefour|leclerc|auchan|intermarch[ée]|"
     r"lidl|aldi|monoprix|franprix|casino|grocery|supermarket)\b",
     CategoryGroup.FOOD, "Courses", "🛒", "#4CAF50"),
    ("description", r"\b(restaurant|resto|pizzeria|sushi|burger|kebab|mc\s*do|"
     r"mcdonalds?|quick|kfc|diner|brasserie|bistrot)\b",
     CategoryGroup.FOOD, "Restaurant", "🍽️", "#4CAF50"),
    ("description", r"\b(caf[ée]|starbucks|coffee|columbus|nespresso)\b",
     CategoryGroup.FOOD, "Café", "☕", "#4CAF50"),
    ("description", r"\b(uber\s*eats|deliveroo|just\s*eat|livraison|delivery|takeaway)\b",
     CategoryGroup.FOOD, "Livraison", "🛵", "#4CAF50"),

    # TRANSPORT
    ("description", r"\b(essence|gasoil|diesel|gazole|sp98|sp95|e10|fuel|gas\s*station|"
     r"totalenerg|esso|shell|bp\b|avia|elane)\b",
     CategoryGroup.TRANSPORT, "Essence", "⛽", "#1976D2"),
    # Parking removed from this pattern; dedicated Parking rule below
    ("description", r"\b(transport|m[ée]tro|bus|tram|ratp|sncf|t[ée]l[ée]p[ée]age|"
     r"p[ée]age|vinci|navigo|t[ée]l[ée]carte|public\s*transport)\b",
     CategoryGroup.TRANSPORT, "Transports en commun", "🚇", "#1976D2"),
    ("description", r"\b(parking|stationnement|horodateur|indigo|effia)\b",
     CategoryGroup.TRANSPORT, "Parking", "🅿️", "#1976D2"),

    # HEALTH
    ("description", r"\b(pharmaci[ea]|m[ée]dicament|ordo|pharmacy|drugstore)\b",
     CategoryGroup.HEALTH, "Pharmacie", "💊", "#D32F2F"),
    ("description", r"\b(m[ée]decin|docteur|consultation|medical|g[ée]n[ée]raliste|"
     r"sp[ée]cialiste|dentiste|ophtalmo|dermato|kine|kin[ée]sith)\b",
     CategoryGroup.HEALTH, "Médecin", "🩺", "#D32F2F"),
    ("description", r"\b(mutuelle|compl[ée]mentaire\s*sant[ée]|health\s*insur)\b",
     CategoryGroup.HEALTH, "Mutuelle", "🏥", "#D32F2F"),

    # SHOPPING
    ("description", r"\b(v[êe]tement|habit|zara|h&m|uniqlo|decathlon|kiabi|primark|"
     r"clothing|fashion|shoes|chaussure|sneakers)\b",
     CategoryGroup.SHOPPING, "Vêtements", "👕", "#9C27B0"),
    ("description", r"\b([ée]lectronique|fnac|darty|boulanger|amazon|cdiscount|"
     r"apple|samsung|dell|electronics|gadget)\b",
     CategoryGroup.SHOPPING, "Électronique", "📱", "#9C27B0"),
    ("description", r"\b(maison|d[ée]co|ikea|leroy\s*merlin|castorama|maison\s*du\s*monde|"
     r"bricolage|furniture|home\s*decor)\b",
     CategoryGroup.SHOPPING, "Maison", "🪴", "#9C27B0"),

    # ENTERTAINMENT — Sport BEFORE Abonnements to avoid "abonnement" greed
    ("description", r"\b(sport|gym|fitness|basic.fit|keepcool|salle\s*sport)\b",
     CategoryGroup.ENTERTAINMENT, "Sport", "🏋️", "#FF5722"),
    ("description", r"\b(abonnement|subscription|netflix|spotify|deezer|disney\+|"
     r"prime\s*video|canal\+|youtube\s*premium)\b",
     CategoryGroup.ENTERTAINMENT, "Abonnements", "📺", "#FF5722"),
    ("description", r"\b(cin[ée]ma|th[ée][âa]tre|concert|spectacle|festival|mus[ée]e|"
     r"loisir|jeux?|playstation|nintendo|xbox|steam|hobby)\b",
     CategoryGroup.ENTERTAINMENT, "Loisirs", "🎮", "#FF5722"),
    ("description", r"\b(voyage|billet\s*avion|airbnb|booking|hotel|train|vol|"
     r"air\s*france|easyjet|ryanair|travel|flight)\b",
     CategoryGroup.ENTERTAINMENT, "Voyages", "✈️", "#FF5722"),

    # FINANCIAL
    ("description", r"\b(frais\s*banc|commission|cotisation\s*cb|bank\s*fee|frais\s*tenu[eé])\b",
     CategoryGroup.FINANCIAL, "Frais bancaires", "🏦", "#607D8B"),
    ("description", r"\b(imp[ôo]t|taxe|dgfip|fisc|urssaf|tva|vat|income\s*tax)\b",
     CategoryGroup.FINANCIAL, "Impôts", "📝", "#607D8B"),
    ("description", r"\b(cr[ée]dit|pr[êe]t|emprunt|[ée]ch[ée]ance|mensualit[ée]|loan)\b",
     CategoryGroup.FINANCIAL, "Crédit", "💳", "#607D8B"),

    # Specific creditor names
    ("creditor_name", r"(La\s*Poste|Colissimo|Chronopost)",
     CategoryGroup.SHOPPING, "Maison", "🪴", "#9C27B0"),
    ("creditor_name", r"(Google|Apple|Microsoft)",
     CategoryGroup.ENTERTAINMENT, "Abonnements", "📺", "#FF5722"),
]


class RuleBasedCategorizer(CategorizationPort):
    """Categorizes transactions using regex rules from DB + built-in fallbacks.

    Priority order:
    1. DB rules (highest priority first)
    2. Built-in patterns (in list order)
    3. Returns None if no rule matches — caller falls back to LLM
    """

    def __init__(self, repo: CashflowSqlRepository) -> None:
        self._repo = repo
        self._db_rules: list[tuple[str, str, int, UUID]] | None = None

    async def _ensure_rules_loaded(self) -> None:
        if self._db_rules is None:
            self._db_rules = await self._repo.get_rule_categories_map()

    async def categorize(self, transaction: Transaction) -> Category | None:
        return await self._categorize_impl(transaction)

    async def _categorize_impl(self, transaction: Transaction) -> Category | None:
        await self._ensure_rules_loaded()
        assert self._db_rules is not None

        # Phase 1: DB rules
        for field, pattern, _priority, category_id in self._db_rules:
            text_val = self._get_field(transaction, field)
            if text_val and self._match(pattern, text_val):
                cat = await self._repo.get_category(category_id)
                if cat is not None:
                    return cat

        # Phase 2: Built-in patterns
        for field, pattern, group, name, _icon, _color in _BUILTIN_PATTERNS:
            text_val = self._get_field(transaction, field)
            if text_val and self._match(pattern, text_val):
                cats = await self._repo.get_default_categories()
                for c in cats:
                    if c.group == group and c.name.lower() == name.lower():
                        return c
        return None

    async def categorize_batch(
        self, transactions: list[Transaction]
    ) -> dict[int, Category]:
        results: dict[int, Category] = {}
        for idx, tx in enumerate(transactions):
            cat = await self._categorize_impl(tx)
            if cat is not None:
                results[idx] = cat
        return results

    @staticmethod
    def _match(pattern: str, text: str) -> bool:
        try:
            return bool(re.search(pattern, text.strip(), re.IGNORECASE))
        except re.error:
            logger.warning("Invalid regex pattern: %r", pattern)
            return False

    @staticmethod
    def _get_field(transaction: Transaction, field: str) -> str | None:
        field_lower = field.lower()
        if field_lower == "description":
            return transaction.description
        elif field_lower == "creditor_name":
            return transaction.creditor_name
        elif field_lower == "debtor_name":
            return transaction.debtor_name
        elif field_lower == "amount":
            return str(transaction.amount)
        return None
