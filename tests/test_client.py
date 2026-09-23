"""Client tests: Steam's storefront JSON quirks, without real network I/O."""
from __future__ import annotations

import io
import json

import pytest

from steam_price_tracker import PriceUnavailableError
from steam_price_tracker import client as client_mod
from steam_price_tracker.client import SteamStoreClient
from steam_price_tracker.exceptions import SteamAPIError


def _patch_response(monkeypatch, payload: dict) -> None:
    """Make ``urlopen`` return a context manager serving ``payload`` as JSON."""

    class _FakeResponse(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def fake_urlopen(request, timeout=None):
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(client_mod, "urlopen", fake_urlopen)


def test_fetch_price_reads_price_overview(monkeypatch):
    _patch_response(
        monkeypatch,
        {
            "1203620": {
                "success": True,
                "data": {
                    "price_overview": {
                        "currency": "USD",
                        "initial": 3999,
                        "final": 3999,
                        "discount_percent": 0,
                        "final_formatted": "$39.99",
                    }
                },
            }
        },
    )
    price = SteamStoreClient().fetch_price(1203620)
    assert price.final_formatted == "$39.99"


def test_empty_list_data_is_unavailable_not_crash(monkeypatch):
    """Steam returns ``"data": []`` (a list) for priceless apps/bundles.

    Regression: this used to raise ``AttributeError: 'list' object has no
    attribute 'get'`` and abort the whole refresh run. It must surface as a
    normal :class:`PriceUnavailableError` instead.
    """
    _patch_response(monkeypatch, {"2384071": {"success": True, "data": []}})
    with pytest.raises(PriceUnavailableError):
        SteamStoreClient().fetch_price(2384071)


def test_success_false_is_api_error(monkeypatch):
    _patch_response(monkeypatch, {"999999": {"success": False}})
    with pytest.raises(SteamAPIError):
        SteamStoreClient().fetch_price(999999)


def test_empty_list_data_does_not_crash_app_info(monkeypatch):
    """The same ``data: []`` quirk must not crash metadata fetches either."""
    _patch_response(monkeypatch, {"2384071": {"success": True, "data": []}})
    with pytest.raises(SteamAPIError):
        # No name in an empty payload -> a clean SteamAPIError, not AttributeError.
        SteamStoreClient().fetch_app_info(2384071)
