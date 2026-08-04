"""Domain models for Steam price data."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


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
class PriceRecord:
    """A timestamped price snapshot for a single app, ready for storage."""

    app_id: int
    price: PriceOverview
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "app_id": self.app_id,
            "fetched_at": self.fetched_at,
            "price_overview": self.price.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PriceRecord":
        return cls(
            app_id=data["app_id"],
            price=PriceOverview.from_api(data["price_overview"]),
            fetched_at=data["fetched_at"],
        )
