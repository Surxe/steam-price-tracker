"""Tests using in-memory fakes + temp-file stores."""
from __future__ import annotations

from pathlib import Path

import pytest

from steam_price_tracker import (
    AppInfo,
    Alerter,
    JsonAppInfoStore,
    JsonPriceStore,
    PriceAlert,
    PriceOverview,
    PriceTracker,
    PriceUnavailableError,
)
from steam_price_tracker.client import StoreFront


class FakeAlerter(Alerter):
    """Records each dispatched batch instead of delivering it."""

    def __init__(self):
        self.batches: list[list[PriceAlert]] = []

    def send(self, alerts) -> None:
        self.batches.append(list(alerts))

    @property
    def sent(self) -> list[PriceAlert]:
        """Flattened alerts across all batches."""
        return [a for batch in self.batches for a in batch]


class FakeSource(StoreFront):
    """Serves canned prices/metadata; counts calls to prove caching."""

    def __init__(self, prices: dict[int, PriceOverview], names: dict[int, str]):
        self._prices = prices
        self._names = names
        self.price_calls = 0
        self.info_calls = 0

    def fetch_price(self, app_id: int) -> PriceOverview:
        self.price_calls += 1
        if app_id not in self._prices:
            raise PriceUnavailableError(app_id)
        return self._prices[app_id]

    def fetch_app_info(self, app_id: int) -> AppInfo:
        self.info_calls += 1
        return AppInfo(app_id=app_id, name=self._names[app_id])

    def search_apps(self, term: str, limit: int = 10):
        return []  # unused by tracker tests


ARK = PriceOverview(
    currency="USD", initial=4499, final=4499,
    discount_percent=0, final_formatted="$44.99",
)


def make_tracker(tmp_path: Path, source: FakeSource) -> PriceTracker:
    return PriceTracker(
        source=source,
        store=JsonPriceStore(tmp_path / "prices.json"),
        info_store=JsonAppInfoStore(tmp_path / "apps.json"),
    )


def test_price_is_keyed_by_date(tmp_path: Path):
    source = FakeSource({2399830: ARK}, {2399830: "ARK: Survival Ascended"})
    tracker = make_tracker(tmp_path, source)

    record = tracker.update(2399830)

    history = tracker.store.get_history(2399830)
    assert list(history) == [record.date]           # keyed by date
    assert history[record.date].price == ARK


def test_app_info_fetched_once_then_cached(tmp_path: Path):
    source = FakeSource({2399830: ARK}, {2399830: "ARK: Survival Ascended"})
    tracker = make_tracker(tmp_path, source)

    tracker.update(2399830)
    tracker.update(2399830)  # second call: metadata must not be re-queried

    assert source.info_calls == 1
    assert source.price_calls == 2
    info = tracker.info_store.get(2399830)
    assert info is not None and info.name == "ARK: Survival Ascended"


def test_update_many_skips_failures(tmp_path: Path):
    source = FakeSource({2399830: ARK}, {2399830: "ARK: Survival Ascended"})
    tracker = make_tracker(tmp_path, source)

    results = tracker.update_many([2399830, 111111])

    assert set(results) == {2399830}
    assert tracker.store.get_latest(111111) is None


def test_unavailable_price_raises(tmp_path: Path):
    source = FakeSource({}, {2399830: "ARK: Survival Ascended"})
    tracker = make_tracker(tmp_path, source)
    with pytest.raises(PriceUnavailableError):
        tracker.update(2399830)


# --------------------------------- alerts -------------------------------- #
def _alert_tracker(tmp_path: Path, source: FakeSource, thresholds, alerter):
    return PriceTracker(
        source=source,
        store=JsonPriceStore(tmp_path / "prices.json"),
        info_store=JsonAppInfoStore(tmp_path / "apps.json"),
        alerter=alerter,
        thresholds=thresholds,
    )


def test_alert_fires_at_or_below_threshold(tmp_path: Path):
    source = FakeSource({2399830: ARK}, {2399830: "ARK: Survival Ascended"})
    alerter = FakeAlerter()
    # ARK is $44.99; threshold $44.99 -> "at or below" should fire.
    tracker = _alert_tracker(tmp_path, source, {2399830: 44.99}, alerter)

    tracker.update_many([2399830])

    assert len(alerter.sent) == 1
    alert = alerter.sent[0]
    assert alert.app_id == 2399830
    assert alert.threshold == 44.99
    assert alert.name == "ARK: Survival Ascended"
    assert "ARK: Survival Ascended" in alert.message


def test_no_alert_above_threshold(tmp_path: Path):
    source = FakeSource({2399830: ARK}, {2399830: "ARK: Survival Ascended"})
    alerter = FakeAlerter()
    tracker = _alert_tracker(tmp_path, source, {2399830: 30.00}, alerter)

    tracker.update_many([2399830])

    assert alerter.sent == []


def test_no_alert_without_threshold(tmp_path: Path):
    source = FakeSource({2399830: ARK}, {2399830: "ARK: Survival Ascended"})
    alerter = FakeAlerter()
    tracker = _alert_tracker(tmp_path, source, {}, alerter)

    tracker.update_many([2399830])

    assert alerter.sent == []


def test_alerts_dispatched_as_one_batch(tmp_path: Path):
    prices = {
        2399830: ARK,
        346110: PriceOverview("USD", 999, 999, 0, "$9.99"),
    }
    names = {2399830: "ARK: Survival Ascended", 346110: "ARK: Survival Evolved"}
    source = FakeSource(prices, names)
    alerter = FakeAlerter()
    # Both below their thresholds.
    tracker = _alert_tracker(
        tmp_path, source, {2399830: 50.0, 346110: 15.0}, alerter
    )

    tracker.update_many([2399830, 346110])

    # One dispatch (one email) carrying both alerts.
    assert len(alerter.batches) == 1
    assert {a.app_id for a in alerter.batches[0]} == {2399830, 346110}
