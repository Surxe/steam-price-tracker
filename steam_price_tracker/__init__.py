"""Steam price tracker: fetch US Steam prices and email alerts for price drops."""
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
from .models import AppInfo, PriceAlert, PriceOverview, SearchResult
from .storage import (
    AlertStateStore,
    AppInfoStore,
    JsonAlertStateStore,
    JsonAppInfoStore,
)
from .tracker import PriceTracker

__version__ = "0.3.0"

__all__ = [
    "PriceSource",
    "AppInfoSource",
    "AppSearchSource",
    "StoreFront",
    "SteamStoreClient",
    "AppInfoStore",
    "JsonAppInfoStore",
    "PriceOverview",
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
