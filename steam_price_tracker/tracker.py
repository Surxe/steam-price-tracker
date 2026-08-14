"""Orchestration: fetch current prices/metadata and fire alerts.

Prices are used only to evaluate alert thresholds for this run — no price
history is persisted. The only things stored are app metadata (fetched once)
and the per-app last-emailed date used to dedup email alerts.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Optional

from . import config
from .alerts import Alerter, ConsoleAlerter
from .client import SteamStoreClient, StoreFront
from .exceptions import PriceTrackerError
from .models import PriceAlert, PriceOverview
from .storage import AppInfoStore, JsonAppInfoStore


class PriceTracker:
    """Ties a :class:`StoreFront` source to the app-info store and alerters.

    All collaborators are injected, so the tracker is trivial to test with
    fakes and open to new sources (e.g. a different region) without
    modification.
    """

    def __init__(
        self,
        source: StoreFront | None = None,
        info_store: AppInfoStore | None = None,
        alerter: Alerter | None = None,
        thresholds: Optional[Mapping[int, float]] = None,
    ) -> None:
        self.source = source or SteamStoreClient(country_code="us")
        self.info_store = info_store or JsonAppInfoStore()
        self.alerter = alerter or ConsoleAlerter()
        # Per-app USD thresholds; defaults to the tracked-apps file.
        self.thresholds: Dict[int, float] = dict(
            config.alert_thresholds() if thresholds is None else thresholds
        )

    def update(self, app_id: int) -> PriceOverview:
        """Fetch the current price for one app (metadata too, if new).

        The first time an app is priced, its metadata (name, ...) is fetched and
        stored too. Price comes first, so an app with no price never triggers a
        metadata fetch. Metadata is never re-queried and its fetch is
        best-effort — staleness or absence is acceptable.
        """
        price = self.source.fetch_price(app_id)
        self._ensure_app_info(app_id)
        return price

    def update_many(self, app_ids: Iterable[int]) -> Dict[int, PriceOverview]:
        """Update several apps, then dispatch all fired alerts as one batch.

        Per-app failures are collected rather than aborting the run. Alerts are
        evaluated across the whole run and handed to the alerter once, so a
        channel like email can aggregate them into a single message.
        """
        results: Dict[int, PriceOverview] = {}
        alerts: List[PriceAlert] = []
        errors: List[str] = []
        for app_id in app_ids:
            try:
                price = self.update(app_id)
            except PriceTrackerError as exc:
                errors.append(f"  app {app_id}: {exc}")
                continue
            results[app_id] = price
            alert = self._evaluate_alert(app_id, price)
            if alert is not None:
                alerts.append(alert)
        if errors:
            print("Some apps could not be updated:\n" + "\n".join(errors))
        if alerts:
            self.alerter.send(alerts)
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

    def _evaluate_alert(
        self, app_id: int, price: PriceOverview
    ) -> Optional[PriceAlert]:
        """Return an alert if the app has a threshold and the price is at/below it.

        Pure: no side effects. Dispatch is the caller's job (batched per run).
        """
        threshold = self.thresholds.get(app_id)
        if threshold is None or price.final_amount > threshold:
            return None
        info = self.info_store.get(app_id)
        return PriceAlert(
            app_id=app_id,
            price=price,
            threshold=threshold,
            name=info.name if info else None,
        )
