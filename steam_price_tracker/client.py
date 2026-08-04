"""HTTP client for Steam's storefront API."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError

from .exceptions import PriceUnavailableError, SteamAPIError
from .models import AppInfo, PriceOverview


class PriceSource(ABC):
    """Abstract source of current prices."""

    @abstractmethod
    def fetch_price(self, app_id: int) -> PriceOverview:
        """Return the current :class:`PriceOverview` for ``app_id``.

        Raises :class:`PriceUnavailableError` if the app has no listed price
        and :class:`SteamAPIError` on transport/protocol failures.
        """


class AppInfoSource(ABC):
    """Abstract source of app-specific metadata (name, etc.)."""

    @abstractmethod
    def fetch_app_info(self, app_id: int) -> AppInfo:
        """Return :class:`AppInfo` for ``app_id``."""


class StoreFront(PriceSource, AppInfoSource, ABC):
    """A backend that can serve both prices and app metadata."""


class SteamStoreClient(StoreFront):
    """Fetches US data from Steam's undocumented storefront JSON endpoint.

    The endpoint requires no API key. ``country_code`` is fixed to ``us`` by
    default so all stored prices share a single currency (USD).
    """

    BASE_URL = "https://store.steampowered.com/api/appdetails"

    def __init__(
        self,
        country_code: str = "us",
        timeout: float = 10.0,
        user_agent: str = "steam-price-tracker/0.1",
    ) -> None:
        self.country_code = country_code
        self.timeout = timeout
        self.user_agent = user_agent

    def _request(self, app_id: int, filters: str) -> dict:
        query = urlencode(
            {"appids": app_id, "cc": self.country_code, "filters": filters}
        )
        request = Request(
            f"{self.BASE_URL}?{query}",
            headers={"User-Agent": self.user_agent},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError) as exc:
            raise SteamAPIError(f"Request failed for app {app_id}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise SteamAPIError(f"Invalid JSON for app {app_id}: {exc}") from exc

        entry = payload.get(str(app_id))
        if not entry or not entry.get("success"):
            raise SteamAPIError(f"Steam reported failure for app {app_id}")
        return entry.get("data", {})

    def fetch_price(self, app_id: int) -> PriceOverview:
        data = self._request(app_id, filters="price_overview")
        overview = data.get("price_overview")
        if not overview:
            # success=True but no price => free / unreleased / region-locked
            raise PriceUnavailableError(app_id)
        return PriceOverview.from_api(overview)

    def fetch_app_info(self, app_id: int) -> AppInfo:
        data = self._request(app_id, filters="basic")
        name = data.get("name")
        if not name:
            raise SteamAPIError(f"No name returned for app {app_id}")
        return AppInfo(app_id=app_id, name=name)
