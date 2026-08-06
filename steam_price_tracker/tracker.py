"""Orchestration: fetch prices/metadata from a source and persist them."""
from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional

from . import config
from .alerts import Alerter, ConsoleAlerter
from .client import SteamStoreClient, StoreFront
from .exceptions import PriceTrackerError
from .models import PriceAlert, PriceRecord
from .storage import (
    AppInfoStore,
    JsonAppInfoStore,
    JsonPriceStore,
    PriceStore,
)


class PriceTracker:
    """Ties a :class:`StoreFront` source to price and app-info stores.

    All collaborators are injected, so the tracker is trivial to test with
    fakes and open to new sources (e.g. a different region) or stores (e.g. a
    database) without modification.
    """

    def __init__(
        self,
        source: StoreFront | None = None,
        store: PriceStore | None = None,
        info_store: AppInfoStore | None = None,
        alerter: Alerter | None = None,
        thresholds: Optional[Mapping[int, float]] = None,
    ) -> None:
        self.source = source or SteamStoreClient(country_code="us")
        self.store = store or JsonPriceStore()
        self.info_store = info_store or JsonAppInfoStore()
        self.alerter = alerter or ConsoleAlerter()
        # Per-app USD thresholds; defaults to whatever config declares.
        self.thresholds: Dict[int, float] = dict(
            config.ALERT_THRESHOLDS if thresholds is None else thresholds
        )

    def update(self, app_id: int) -> PriceRecord:
        """Fetch the current price for one app and persist it under today's date.

        The first time an app is priced, its metadata (name, ...) is fetched and
        stored too. Price comes first, so an app with no price never triggers a
        metadata fetch. Metadata is never re-queried and its fetch is
        best-effort — staleness or absence is acceptable.
        """
        price = self.source.fetch_price(app_id)
        record = PriceRecord(app_id=app_id, price=price)
        self.store.save(record)
        self._ensure_app_info(app_id)
        self._maybe_alert(record)
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
            print("Some apps could not be updated:\n" + "\n".join(errors))
        return results

    def _ensure_app_info(self, app_id: int) -> None:
        """Fetch and store app metadata only if it has never been stored.

        Best-effort: a metadata fetch failure is reported but never fails an
        otherwise-successful price update.
        """
        if self.info_store.has(app_id):
            return
        try:
            info = self.source.fetch_app_info(app_id)
        except PriceTrackerError as exc:
            print(f"  app {app_id}: could not fetch metadata: {exc}")
            return
        self.info_store.save(info)

    def _maybe_alert(self, record: PriceRecord) -> None:
        """Fire an alert if the app has a threshold and the price is at/below it."""
        threshold = self.thresholds.get(record.app_id)
        if threshold is None or record.price.final_amount > threshold:
            return
        info = self.info_store.get(record.app_id)
        alert = PriceAlert(
            app_id=record.app_id,
            price=record.price,
            threshold=threshold,
            name=info.name if info else None,
        )
        self.alerter.send(alert)
