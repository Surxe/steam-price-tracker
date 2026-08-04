"""Orchestration: fetch prices from a source and persist them to a store."""
from __future__ import annotations

from typing import Dict, Iterable, List

from .client import PriceSource, SteamStoreClient
from .exceptions import PriceTrackerError
from .models import PriceRecord
from .storage import JsonPriceStore, PriceStore


class PriceTracker:
    """Ties a :class:`PriceSource` to a :class:`PriceStore`.

    Both collaborators are injected, so the tracker is trivial to test with
    fakes and open to new sources (e.g. a different region) or stores (e.g. a
    database) without modification.
    """

    def __init__(
        self,
        source: PriceSource | None = None,
        store: PriceStore | None = None,
    ) -> None:
        self.source = source or SteamStoreClient(country_code="us")
        self.store = store or JsonPriceStore()

    def update(self, app_id: int) -> PriceRecord:
        """Fetch the current price for one app and persist it."""
        price = self.source.fetch_price(app_id)
        record = PriceRecord(app_id=app_id, price=price)
        self.store.save(record)
        return record

    def update_many(self, app_ids: Iterable[int]) -> Dict[int, PriceRecord]:
        """Update several apps, collecting per-app failures instead of aborting."""
        results: Dict[int, PriceRecord] = {}
        errors: List[str] = []
        for app_id in app_ids:
            try:
                results[app_id] = self.update(app_id)
            except PriceTrackerError as exc:
                errors.append(f"  app {app_id}: {exc}")
        if errors:
            # Surface failures but keep whatever succeeded.
            print("Some apps could not be updated:\n" + "\n".join(errors))
        return results
