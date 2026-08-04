"""Exception hierarchy for the price tracker."""
from __future__ import annotations


class PriceTrackerError(Exception):
    """Base class for all price-tracker errors."""


class SteamAPIError(PriceTrackerError):
    """The Steam storefront API request failed or returned an error."""


class PriceUnavailableError(PriceTrackerError):
    """The app exists but has no US price (free, unreleased, or region-locked)."""

    def __init__(self, app_id: int):
        self.app_id = app_id
        super().__init__(f"No US price_overview available for app {app_id}")
