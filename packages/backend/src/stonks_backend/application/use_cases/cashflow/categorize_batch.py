"""CategorizeBatch — categorizes a batch of transactions using rules + LLM fallback."""

from __future__ import annotations

import logging
from uuid import UUID

from stonks_backend.application.ports.cashflow import CashflowRepositoryPort, CategorizationPort
from stonks_backend.domain.cashflow.category import Category
from stonks_backend.domain.cashflow.transaction_entity import Transaction

logger = logging.getLogger(__name__)


class CategorizeBatchError(Exception):
    """Raised when batch categorization fails."""


class CategorizeBatch:
    """Categorize transactions: first try rules, then LLM fallback for ambiguous ones.

    Usage:
        use_case = CategorizeBatch(rule_categorizer, llm_categorizer, cashflow_repo)
        results = await use_case.categorize(transactions)
        # results maps transaction index → Category
    """

    def __init__(
        self,
        rule_categorizer: CategorizationPort,
        llm_categorizer: CategorizationPort,
        cashflow_repo: CashflowRepositoryPort,
    ) -> None:
        self._rules = rule_categorizer
        self._llm = llm_categorizer
        self._repo = cashflow_repo

    async def categorize(self, transactions: list[Transaction]) -> dict[int, UUID]:
        """Categorize transactions using a two-phase approach.

        Phase 1: Apply rule-based categorization (fast, deterministic).
        Phase 2: For unmatched transactions, use LLM fallback.

        Returns:
            dict mapping transaction index → category_id assigned.
            Not all transactions may be categorized (LLM can also return None).
        """
        if not transactions:
            return {}

        # Phase 1: Rules
        rule_results = await self._rules.categorize_batch(transactions)

        # Identify unmatched indices
        unmatched = [(idx, tx) for idx, tx in enumerate(transactions) if idx not in rule_results]

        # Phase 2: LLM fallback for unmatched
        llm_results: dict[int, Category] = {}
        if unmatched:
            logger.info(
                "Rule categorizer matched %d/%d, invoking LLM for %d remaining",
                len(rule_results),
                len(transactions),
                len(unmatched),
            )
            unmatched_txs = [tx for _, tx in unmatched]
            llm_results = await self._llm.categorize_batch(unmatched_txs)

            # Remap indices: LLM returns dict[index_in_batch] → Category
            # Our batch is unmatched, so remap to global indices
            remapped: dict[int, Category] = {}
            for batch_idx, cat in llm_results.items():
                global_idx = unmatched[batch_idx][0]
                remapped[global_idx] = cat
            llm_results = remapped

        # Merge results
        all_results: dict[int, UUID] = {}
        for idx, cat in rule_results.items():
            all_results[idx] = cat.id
        for idx, cat in llm_results.items():
            all_results[idx] = cat.id

        logger.info(
            "Categorization complete: %d matched (rules=%d, llm=%d) out of %d",
            len(all_results),
            len(rule_results),
            len(llm_results),
            len(transactions),
        )

        return all_results

    async def categorize_and_persist(self, transactions: list[Transaction]) -> int:
        """Categorize transactions and persist category assignments.

        Returns:
            Number of transactions that were categorized.
        """
        results = await self.categorize(transactions)

        categorized = 0
        for idx, category_id in results.items():
            if idx < len(transactions):
                transactions[idx].assign_category(category_id)
                categorized += 1

        return categorized
