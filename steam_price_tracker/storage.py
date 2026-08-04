"""Persistence layer for price history and app metadata."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Optional

from .models import AppInfo, PriceRecord


class _JsonFile:
    """Shared JSON-document read/write with atomic replace.

    The whole document is rewritten on each save, which is fine for the modest
    number of apps this tracker targets.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def write(self, raw: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(raw, fh, indent=2, sort_keys=True)
            fh.write("\n")
        tmp.replace(self.path)


# --------------------------------------------------------------------------- #
# Prices
# --------------------------------------------------------------------------- #
class PriceStore(ABC):
    """Abstract store of price history, keyed by app id then date."""

    @abstractmethod
    def save(self, record: PriceRecord) -> None:
        """Persist ``record`` under its app id and date (same-day overwrites)."""

    @abstractmethod
    def get_history(self, app_id: int) -> Dict[str, PriceRecord]:
        """Return every dated record for ``app_id``, keyed by date."""

    @abstractmethod
    def get_latest(self, app_id: int) -> Optional[PriceRecord]:
        """Return the most recent record for ``app_id`` or ``None``."""


class JsonPriceStore(PriceStore):
    """Stores price history in a single JSON file.

    File shape::

        {
          "2399830": {
            "2026-08-04": {"fetched_at": "...", "price_overview": {...}}
          }
        }
    """

    def __init__(self, path: str | Path = "data/prices.json") -> None:
        self._file = _JsonFile(path)

    @property
    def path(self) -> Path:
        return self._file.path

    def save(self, record: PriceRecord) -> None:
        raw = self._file.load()
        app_history = raw.setdefault(str(record.app_id), {})
        app_history[record.date] = record.to_entry()
        self._file.write(raw)

    def get_history(self, app_id: int) -> Dict[str, PriceRecord]:
        raw = self._file.load()
        app_history = raw.get(str(app_id), {})
        return {
            date: PriceRecord.from_entry(app_id, entry)
            for date, entry in app_history.items()
        }

    def get_latest(self, app_id: int) -> Optional[PriceRecord]:
        history = self.get_history(app_id)
        if not history:
            return None
        latest_date = max(history)  # ISO dates sort lexicographically
        return history[latest_date]


# --------------------------------------------------------------------------- #
# App metadata
# --------------------------------------------------------------------------- #
class AppInfoStore(ABC):
    """Abstract store of app-specific metadata, keyed by app id."""

    @abstractmethod
    def has(self, app_id: int) -> bool:
        """Whether metadata for ``app_id`` has ever been stored."""

    @abstractmethod
    def get(self, app_id: int) -> Optional[AppInfo]:
        """Return stored :class:`AppInfo` for ``app_id`` or ``None``."""

    @abstractmethod
    def save(self, info: AppInfo) -> None:
        """Persist ``info`` for its app id."""


class JsonAppInfoStore(AppInfoStore):
    """Stores app metadata in a single JSON file, keyed by app id.

    File shape::

        {"2399830": {"name": "ARK: Survival Ascended", "fetched_at": "..."}}
    """

    def __init__(self, path: str | Path = "data/apps.json") -> None:
        self._file = _JsonFile(path)

    @property
    def path(self) -> Path:
        return self._file.path

    def has(self, app_id: int) -> bool:
        return str(app_id) in self._file.load()

    def get(self, app_id: int) -> Optional[AppInfo]:
        entry = self._file.load().get(str(app_id))
        return AppInfo.from_dict(app_id, entry) if entry else None

    def save(self, info: AppInfo) -> None:
        raw = self._file.load()
        raw[str(info.app_id)] = info.to_dict()
        self._file.write(raw)
