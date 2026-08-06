"""Steam price tracker: fetch US Steam prices and persist them as JSON."""
from __future__ import annotations

from .alerts import (
    Alerter,
    CompositeAlerter,
    ConsoleAlerter,
    EmailAlerter,
    EmailConfig,
)
from .client import (
    AppInfoSource,
    AppSearchSource,
    PriceSource,
    SteamStoreClient,
    StoreFront,
)
from .exceptions import (
    PriceTrackerError,
    PriceUnavailableError,
    SteamAPIError,
)
from .models import AppInfo, PriceAlert, PriceOverview, PriceRecord, SearchResult
from .storage import (
    AlertStateStore,
    AppInfoStore,
    JsonAlertStateStore,
    JsonAppInfoStore,
    JsonPriceStore,
    PriceStore,
)
from .tracker import PriceTracker

__version__ = "0.3.0"

__all__ = [
    "PriceSource",
    "AppInfoSource",
    "AppSearchSource",
    "StoreFront",
    "SteamStoreClient",
    "PriceStore",
    "JsonPriceStore",
    "AppInfoStore",
    "JsonAppInfoStore",
    "PriceOverview",
    "PriceRecord",
    "AppInfo",
    "SearchResult",
    "PriceAlert",
    "Alerter",
    "ConsoleAlerter",
    "CompositeAlerter",
    "EmailAlerter",
    "EmailConfig",
    "AlertStateStore",
    "JsonAlertStateStore",
    "PriceTracker",
    "PriceTrackerError",
    "SteamAPIError",
    "PriceUnavailableError",
]
