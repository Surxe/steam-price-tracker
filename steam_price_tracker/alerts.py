"""Alert delivery strategies.

An :class:`Alerter` decides *how* a batch of fired
:class:`~steam_price_tracker.models.PriceAlert` objects is delivered. The tracker
decides *when* (threshold check on refresh) and hands over the whole batch at
once so a channel like email can aggregate them into a single message.

New channels are added by subclassing :class:`Alerter`; nothing else in the
tracker changes.
"""
from __future__ import annotations

import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Callable, Optional, Sequence

from . import config
from .models import PriceAlert
from .storage import AlertStateStore

STORE_URL = "https://store.steampowered.com/app/{app_id}"


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class Alerter(ABC):
    """Delivers a batch of fired price alerts somewhere."""

    @abstractmethod
    def send(self, alerts: Sequence[PriceAlert]) -> None:
        """Deliver ``alerts`` (may be empty — implementations should no-op then)."""


class ConsoleAlerter(Alerter):
    """Prints each alert to stdout.

    Not deduplicated: under the login systemd service every refresh's alerts
    land in the journal, which is useful for debugging.
    """

    def send(self, alerts: Sequence[PriceAlert]) -> None:
        for alert in alerts:
            print(alert.message)


class CompositeAlerter(Alerter):
    """Fans a batch out to several alerters (e.g. console + email)."""

    def __init__(self, alerters: Sequence[Alerter]) -> None:
        self._alerters = list(alerters)

    def send(self, alerts: Sequence[PriceAlert]) -> None:
        for alerter in self._alerters:
            alerter.send(alerts)


@dataclass(frozen=True)
class EmailConfig:
    """Everything needed to send via SMTP. The password is a Gmail App Password."""

    host: str
    port: int
    user: str          # authenticated account; also the From address
    password: str
    to_addr: str

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> Optional["EmailConfig"]:
        """Build from environment, or ``None`` if credentials are not both set.

        Presence of both user and password is the enable switch for email.
        """
        import os

        env = os.environ if env is None else env
        user = env.get("STEAM_TRACKER_SMTP_USER")
        password = env.get("STEAM_TRACKER_SMTP_PASSWORD")
        if not user or not password:
            return None
        return cls(
            host=config.SMTP_HOST,
            port=config.SMTP_PORT,
            user=user,
            password=password,
            to_addr=env.get("STEAM_TRACKER_EMAIL_TO", config.EMAIL_TO),
        )


class EmailAlerter(Alerter):
    """Sends one digest email per batch via Gmail SMTP, deduped to once/day/app.

    ``smtp_factory`` and ``today`` are injected so the compose/auth path can be
    tested without a network or real credentials.
    """

    def __init__(
        self,
        email_config: EmailConfig,
        state_store: AlertStateStore,
        smtp_factory: Callable[..., smtplib.SMTP] = smtplib.SMTP,
        today: Callable[[], str] = _utc_today,
    ) -> None:
        self.config = email_config
        self.state_store = state_store
        self.smtp_factory = smtp_factory
        self.today = today

    def send(self, alerts: Sequence[PriceAlert]) -> None:
        self.try_send(alerts)

    def try_send(self, alerts: Sequence[PriceAlert]) -> bool:
        """Send the digest; return ``True`` only if an email was delivered.

        Errors are caught and reported (never crash the refresh); a caught error
        or an all-deduped/empty batch returns ``False``.
        """
        today = self.today()
        # Dedup: drop apps already emailed today.
        fresh = [
            a
            for a in alerts
            if self.state_store.last_emailed(a.app_id) != today
        ]
        if not fresh:
            return False

        message = self._compose(fresh)
        try:
            self._deliver(message)
        except smtplib.SMTPAuthenticationError as exc:
            print(
                "Email alert failed: SMTP authentication rejected. Check the "
                "App Password and that 2-Step Verification is on for "
                f"{self.config.user}. ({exc})"
            )
            return False
        except (smtplib.SMTPException, OSError) as exc:
            print(f"Email alert failed: {exc}")
            return False

        for alert in fresh:
            self.state_store.mark_emailed(alert.app_id, today)
        return True

    def _compose(self, alerts: Sequence[PriceAlert]) -> EmailMessage:
        count = len(alerts)
        noun = "game" if count == 1 else "games"
        lines = []
        for alert in alerts:
            lines.append(alert.message)
            lines.append(f"    {STORE_URL.format(app_id=alert.app_id)}")
            lines.append("")
        message = EmailMessage()
        message["Subject"] = f"Steam price alert: {count} {noun} at/below your target"
        message["From"] = self.config.user
        message["To"] = self.config.to_addr
        message.set_content("\n".join(lines).rstrip() + "\n")
        return message

    def _deliver(self, message: EmailMessage) -> None:
        with self.smtp_factory(self.config.host, self.config.port) as server:
            server.starttls()
            server.login(self.config.user, self.config.password)
            server.send_message(message)


class EphemeralAlertState(AlertStateStore):
    """Non-persistent state store: never dedups. For the --test-email path."""

    def last_emailed(self, app_id: int) -> Optional[str]:
        return None

    def mark_emailed(self, app_id: int, date: str) -> None:
        pass
