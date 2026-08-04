"""Tests using an in-memory fake source + a temp-file store."""
from __future__ import annotations

from pathlib import Path

import pytest

from steam_price_tracker import (
    JsonPriceStore,
    PriceOverview,
    PriceTracker,
    PriceUnavailableError,
)
from steam_price_tracker.client import PriceSource


class FakeSource(PriceSource):
    """Serves canned prices; raises for unknown ids."""

    def __init__(self, prices: dict[int, PriceOverview]):
        self._prices = prices

    def fetch_price(self, app_id: int) -> PriceOverview:
        if app_id not in self._prices:
            raise PriceUnavailableError(app_id)
        return self._prices[app_id]


ARK = PriceOverview(
    currency="USD", initial=4499, final=4499,
    discount_percent=0, final_formatted="$44.99",
)


def test_update_persists_under_app_id(tmp_path: Path):
    store = JsonPriceStore(tmp_path / "prices.json")
    tracker = PriceTracker(source=FakeSource({2399830: ARK}), store=store)

    record = tracker.update(2399830)

    assert record.price.final_amount == 44.99
    reloaded = store.get(2399830)
    assert reloaded is not None
    assert reloaded.price == ARK


def test_update_many_skips_failures(tmp_path: Path):
    store = JsonPriceStore(tmp_path / "prices.json")
    tracker = PriceTracker(source=FakeSource({2399830: ARK}), store=store)

    results = tracker.update_many([2399830, 111111])

    assert set(results) == {2399830}
    assert store.get(111111) is None


def test_unavailable_price_raises(tmp_path: Path):
    tracker = PriceTracker(
        source=FakeSource({}), store=JsonPriceStore(tmp_path / "p.json")
    )
    with pytest.raises(PriceUnavailableError):
        tracker.update(2399830)
