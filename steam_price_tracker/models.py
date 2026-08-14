"""Domain models for Steam price and app data."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PriceOverview:
    """A single price snapshot as returned by Steam's ``price_overview`` block.

    Monetary values are kept in the currency's minor unit (cents) exactly as
    Steam reports them; use :pyattr:`final_amount` for a human-friendly float.
    """

    currency: str
    initial: int          # base price, in cents
    final: int            # current price after discount, in cents
    discount_percent: int
    final_formatted: str

    @property
    def final_amount(self) -> float:
        """Current price as a major-unit float (e.g. 44.99)."""
        return self.final / 100

    @property
    def initial_amount(self) -> float:
        """Base price as a major-unit float."""
        return self.initial / 100

    @classmethod
    def from_api(cls, data: dict) -> "PriceOverview":
        """Build from a raw Steam ``price_overview`` dict."""
        return cls(
            currency=data["currency"],
            initial=data["initial"],
            final=data["final"],
            discount_percent=data["discount_percent"],
            final_formatted=data.get("final_formatted", ""),
        )

    def to_dict(self) -> dict:
        return {
            "currency": self.currency,
            "initial": self.initial,
            "final": self.final,
            "discount_percent": self.discount_percent,
            "final_formatted": self.final_formatted,
        }


@dataclass(frozen=True)
class SearchResult:
    """One candidate returned by a store search."""

    app_id: int
    name: str
    type: str = ""  # e.g. "app", "dlc", "bundle"

    @classmethod
    def from_api(cls, item: dict) -> "SearchResult":
        """Build from a raw Steam ``storesearch`` item."""
        return cls(
            app_id=item["id"],
            name=item["name"],
            type=item.get("type", ""),
        )


@dataclass(frozen=True)
class PriceAlert:
    """A fired price alert: an app's current price met its configured threshold.

    ``threshold`` is in USD; the alert fires when the price is at or below it.
    """

    app_id: int
    price: PriceOverview
    threshold: float
    name: str | None = None

    @property
    def message(self) -> str:
        who = self.name or f"app {self.app_id}"
        return (
            f"[PRICE ALERT] {who}: {self.price.final_formatted} "
            f"is at or below your ${self.threshold:.2f} threshold"
        )


@dataclass(frozen=True)
class AppInfo:
    """App-specific metadata that rarely changes (name, etc.).

    Fetched once per app and allowed to go stale — it is never re-queried once
    stored.
    """

    app_id: int
    name: str
    fetched_at: str = field(default_factory=_utcnow_iso)

    def to_dict(self) -> dict:
        return {"name": self.name, "fetched_at": self.fetched_at}

    @classmethod
    def from_dict(cls, app_id: int, data: dict) -> "AppInfo":
        return cls(
            app_id=app_id,
            name=data["name"],
            fetched_at=data["fetched_at"],
        )
