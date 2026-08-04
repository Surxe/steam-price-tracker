"""HTTP client for Steam's storefront price API."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError

from .exceptions import PriceUnavailableError, SteamAPIError
from .models import PriceOverview


class PriceSource(ABC):
    """Abstract price source. Swap implementations for testing or new backends."""

    @abstractmethod
    def fetch_price(self, app_id: int) -> PriceOverview:
        """Return the current :class:`PriceOverview` for ``app_id``.

        Raises :class:`PriceUnavailableError` if the app has no listed price
        and :class:`SteamAPIError` on transport/protocol failures.
        """


class SteamStoreClient(PriceSource):
    """Fetches US pricing from Steam's undocumented storefront JSON endpoint.

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

    def _build_url(self, app_id: int) -> str:
        query = urlencode(
            {
                "appids": app_id,
                "cc": self.country_code,
                "filters": "price_overview",
            }
        )
        return f"{self.BASE_URL}?{query}"

    def fetch_price(self, app_id: int) -> PriceOverview:
        request = Request(
            self._build_url(app_id),
            headers={"User-Agent": self.user_agent},
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (URLError, TimeoutError) as exc:
            raise SteamAPIError(f"Request failed for app {app_id}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise SteamAPIError(f"Invalid JSON for app {app_id}: {exc}") from exc

        return self._parse(app_id, payload)

    @staticmethod
    def _parse(app_id: int, payload: dict) -> PriceOverview:
        entry = payload.get(str(app_id))
        if not entry or not entry.get("success"):
            raise SteamAPIError(f"Steam reported failure for app {app_id}")

        overview = entry.get("data", {}).get("price_overview")
        if not overview:
            # success=True but no price => free / unreleased / region-locked
            raise PriceUnavailableError(app_id)

        return PriceOverview.from_api(overview)
