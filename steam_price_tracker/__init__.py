"""Steam price tracker: fetch US Steam prices and persist them as JSON."""
from __future__ import annotations

from .client import (
    AppInfoSource,
    PriceSource,
    SteamStoreClient,
    StoreFront,
)
from .exceptions import (
    PriceTrackerError,
    PriceUnavailableError,
    SteamAPIError,
)
from .models import AppInfo, PriceOverview, PriceRecord
from .storage import (
    AppInfoStore,
    JsonAppInfoStore,
    JsonPriceStore,
    PriceStore,
)
from .tracker import PriceTracker

__version__ = "0.2.0"

__all__ = [
    "PriceSource",
    "AppInfoSource",
    "StoreFront",
    "SteamStoreClient",
    "PriceStore",
    "JsonPriceStore",
    "AppInfoStore",
    "JsonAppInfoStore",
    "PriceOverview",
    "PriceRecord",
    "AppInfo",
    "PriceTracker",
    "PriceTrackerError",
    "SteamAPIError",
    "PriceUnavailableError",
]
