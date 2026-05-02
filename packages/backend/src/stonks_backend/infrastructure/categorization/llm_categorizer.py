"""LLMCategorizer — fallback categorization via DeepSeek V4 Flash (OpenRouter).

Used when RuleBasedCategorizer returns None (ambiguous transaction).
Calls DeepSeek V4 Flash with low cost (~$0.0002/call) for structured classification.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx

from stonks_backend.application.ports.cashflow import CategorizationPort
from stonks_backend.domain.cashflow.category import Category
from stonks_backend.domain.cashflow.transaction_entity import Transaction

if TYPE_CHECKING:
    from stonks_backend.infrastructure.persistence.cashflow_repo import CashflowSqlRepository

logger = logging.getLogger(__name__)

# OpenRouter API cost for DeepSeek V4 Flash: ~$0.00015/1K tokens
# Each categorization call: ~200 tokens → ~$0.00003/call — negligible
LLM_MODEL = "deepseek/deepseek-chat"  # V4 Flash equivalent via OpenRouter


class LLMCategorizer(CategorizationPort):
    """Uses an LLM to categorize transactions when rules fail.

    Constructs a prompt with the available categories and transaction details,
    expects a one-word category group response.
    """

    def __init__(
        self,
        repo: CashflowSqlRepository,
        api_key: str,
        base_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        self._repo = repo
        self._api_key = api_key
        self._base_url = base_url
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        self._categories_cache: list[Category] | None = None

    async def _get_categories(self) -> list[Category]:
        if self._categories_cache is None:
            self._categories_cache = await self._repo.get_default_categories()
        return self._categories_cache

    async def categorize(self, transaction: Transaction) -> Category | None:
        """Categorize a single transaction via LLM. Returns None on failure."""
        categories = await self._get_categories()
        if not categories:
            return None

        category_list = "\n".join(
            f"- {c.name} (group: {c.group.value})" for c in categories
        )

        prompt = (
            "Tu es un assistant de catégorisation financière. "
            "Attribue UNE seule catégorie à cette transaction bancaire.\n\n"
            f"Transaction:\n"
            f"  Description: {transaction.description}\n"
            f"  Montant: {transaction.amount}\n"
            f"  Créancier: {transaction.creditor_name or 'N/A'}\n"
            f"  Débiteur: {transaction.debtor_name or 'N/A'}\n\n"
            f"Catégories disponibles:\n{category_list}\n\n"
            "Réponds uniquement avec le NOM EXACT de la catégorie (ex: 'Courses'). Rien d'autre."
        )

        try:
            response = await self._client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": LLM_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 16,
                },
            )
            response.raise_for_status()
            data = response.json()
            category_name = data["choices"][0]["message"]["content"].strip()

            # Find matching category
            for c in categories:
                if c.name.lower() == category_name.lower():
                    return c

            # Fuzzy match: if LLM returns a group name, pick first category in that group
            for c in categories:
                if c.group.value.lower() == category_name.lower():
                    return c

            logger.info("LLM returned unrecognized category: %r", category_name)
            return None

        except Exception:
            logger.exception("LLM categorization failed")
            return None

    async def categorize_batch(
        self, transactions: list[Transaction]
    ) -> dict[int, Category]:
        """Categorize a batch sequentially (one LLM call per transaction)."""
        results: dict[int, Category] = {}
        for idx, tx in enumerate(transactions):
            cat = await self.categorize(tx)
            if cat is not None:
                results[idx] = cat
        return results

    async def close(self) -> None:
        await self._client.aclose()
