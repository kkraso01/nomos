"""Source adapter contract (per SOURCE_POLICY_AND_INGESTION.md §4).

Adapters perform acquisition-specific work ONLY (discover/fetch/normalize).
Canonical domain persistence, gate, dedup, hashing, versioning and provenance
are owned by the central IngestionService.
"""
from abc import ABC, abstractmethod
from typing import Any, Iterator, Optional


class SourceAdapter(ABC):
    name: str = "base"
    registry_key: Optional[str] = None  # SOURCE_REGISTRY_SEED.yaml source key this adapter feeds

    @abstractmethod
    def discover(self, cursor: Optional[str] = None) -> Iterator[dict]:
        """Yield acquisition records (each carrying enough to fetch one object)."""

    @abstractmethod
    def fetch(self, record: dict) -> bytes:
        """Acquire the raw representation of one record. Acquisition-specific."""

    @abstractmethod
    def normalize(self, raw: bytes, record: dict) -> list[dict]:
        """Turn one raw payload into one or more normalized canonical records.

        Normalized records carry: kind, canonical_key, title, language, body,
        structured fields + licence/provenance hints. Adapters never persist.
        """


class AdapterConfigError(Exception):
    pass