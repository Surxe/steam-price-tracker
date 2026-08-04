"""Persistence layer for price records."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

from .models import PriceRecord


class PriceStore(ABC):
    """Abstract store keyed by Steam app id."""

    @abstractmethod
    def save(self, record: PriceRecord) -> None:
        """Persist (or overwrite) the record for ``record.app_id``."""

    @abstractmethod
    def get(self, app_id: int) -> Optional[PriceRecord]:
        """Return the stored record for ``app_id`` or ``None``."""

    @abstractmethod
    def all(self) -> Dict[int, PriceRecord]:
        """Return every stored record keyed by app id."""


class JsonPriceStore(PriceStore):
    """Stores records in a single JSON file, keyed by app id.

    File shape::

        {
          "2399830": {"app_id": 2399830, "fetched_at": "...",
                      "price_overview": {...}}
        }

    Reads happen lazily and the full document is rewritten on each save, which
    is fine for the modest number of apps this tracker targets.
    """

    def __init__(self, path: str | Path = "data/prices.json") -> None:
        self.path = Path(path)

    def _load_raw(self) -> dict:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _write_raw(self, raw: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic-ish write: dump to temp file then replace.
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(raw, fh, indent=2, sort_keys=True)
            fh.write("\n")
        tmp.replace(self.path)

    def save(self, record: PriceRecord) -> None:
        raw = self._load_raw()
        raw[str(record.app_id)] = record.to_dict()
        self._write_raw(raw)

    def get(self, app_id: int) -> Optional[PriceRecord]:
        raw = self._load_raw()
        entry = raw.get(str(app_id))
        return PriceRecord.from_dict(entry) if entry else None

    def all(self) -> Dict[int, PriceRecord]:
        raw = self._load_raw()
        return {int(k): PriceRecord.from_dict(v) for k, v in raw.items()}
