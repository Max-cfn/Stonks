"""Bank registry — static catalog of supported banks and their connector configuration.

Loaded from banks.json at startup. Each bank entry maps a user-facing bank
to its ASPSP parameters for the relevant connector (Enable Banking, etc.).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BankInfo:
    """A bank/institution available for connection.

    Attributes:
        id: Unique slug (e.g. "lcl", "boursorama").
        name: Display name (localized, e.g. "LCL").
        country: ISO 3166-1 alpha-2 country code.
        connector_type: Which adapter to use ("enable_banking", "manual", etc.).
        connector_config: Connector-specific parameters (e.g. ASPSP name).
        supported: Whether the bank is actively supported (False = greyed out).
        account_types: List of account types this bank exposes.
        logo_path: Relative path to the bank logo for the frontend.
        notes: Additional information for the user or admin.
    """

    id: str
    name: str
    country: str
    connector_type: str
    connector_config: dict[str, Any]
    supported: bool = True
    account_types: list[str] | None = None
    logo_path: str = ""
    notes: str | None = None


class BankRegistry:
    """In-memory registry of supported banks, loaded from a JSON file."""

    def __init__(self, banks: list[BankInfo]) -> None:
        self._by_id: dict[str, BankInfo] = {b.id: b for b in banks}

    def get(self, bank_id: str) -> BankInfo | None:
        """Retrieve a single bank by its id."""
        return self._by_id.get(bank_id)

    def list_all(self) -> list[BankInfo]:
        """Return all banks (supported + unsupported)."""
        return list(self._by_id.values())

    def list_supported(self) -> list[BankInfo]:
        """Return only banks marked as supported."""
        return [b for b in self._by_id.values() if b.supported]

    def __len__(self) -> int:
        return len(self._by_id)

    @classmethod
    def from_json(cls, path: str | Path) -> BankRegistry:
        """Load the bank registry from a JSON file.

        Expected format:
        {
            "banks": [
                {
                    "id": "lcl",
                    "name": "LCL",
                    "country": "FR",
                    "connector_type": "enable_banking",
                    "connector_config": {"aspsp_name": "LCL", "aspsp_country": "FR"},
                    "supported": true,
                    "account_types": ["checking", "savings"],
                    "logo_path": "/logos/lcl.png",
                    "notes": null
                }
            ]
        }
        """
        with open(path) as f:
            data = json.load(f)

        banks = []
        for entry in data.get("banks", []):
            banks.append(
                BankInfo(
                    id=entry["id"],
                    name=entry["name"],
                    country=entry["country"],
                    connector_type=entry["connector_type"],
                    connector_config=entry.get("connector_config", {}),
                    supported=entry.get("supported", True),
                    account_types=entry.get("account_types"),
                    logo_path=entry.get("logo_path", ""),
                    notes=entry.get("notes"),
                )
            )

        logger.info("Loaded %d banks from %s", len(banks), path)
        return cls(banks)

    @classmethod
    def from_default_path(cls) -> BankRegistry:
        """Load from the default banks.json next to this module."""
        default_path = Path(__file__).parent / "banks.json"
        return cls.from_json(default_path)
