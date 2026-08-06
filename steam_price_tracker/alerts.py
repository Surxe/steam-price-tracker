"""Alert delivery strategies.

An :class:`Alerter` decides *how* a fired :class:`~steam_price_tracker.models.PriceAlert`
is delivered. The tracker decides *when* (threshold check on refresh). New
channels — email, Slack, a desktop notification — are added by subclassing
:class:`Alerter`; nothing else in the tracker changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from .models import PriceAlert


class Alerter(ABC):
    """Delivers a fired price alert somewhere."""

    @abstractmethod
    def send(self, alert: PriceAlert) -> None:
        """Deliver ``alert``."""


class ConsoleAlerter(Alerter):
    """Prints the alert to stdout.

    Placeholder delivery until an email connector is wired in; under the login
    systemd service this lands in the journal.
    """

    def send(self, alert: PriceAlert) -> None:
        print(alert.message)
