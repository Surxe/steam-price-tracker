"""CLI: ``python -m steam_price_tracker [app_id ...]``.

With no arguments it updates every id in :data:`config.TRACKED_APP_IDS`.
"""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .alerts import (
    Alerter,
    CompositeAlerter,
    ConsoleAlerter,
    EmailAlerter,
    EmailConfig,
    EphemeralAlertState,
)
from .config import ALERT_STATE_PATH, APP_INFO_PATH, STORE_PATH, TRACKED_APP_IDS
from .models import PriceAlert, PriceOverview
from .storage import JsonAlertStateStore, JsonAppInfoStore, JsonPriceStore
from .tracker import PriceTracker


def _build_alerter(env: dict | None = None) -> Alerter:
    """Console alerts always; add email when SMTP credentials are present."""
    env = os.environ if env is None else env
    console = ConsoleAlerter()

    email_config = EmailConfig.from_env(env)
    if email_config is None:
        # Warn if creds are half-set so misconfiguration is not silent.
        if env.get("STEAM_TRACKER_SMTP_USER") or env.get("STEAM_TRACKER_SMTP_PASSWORD"):
            print(
                "Email disabled: set BOTH STEAM_TRACKER_SMTP_USER and "
                "STEAM_TRACKER_SMTP_PASSWORD. Using console alerts only."
            )
        return console

    email = EmailAlerter(email_config, JsonAlertStateStore(ALERT_STATE_PATH))
    return CompositeAlerter([console, email])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="steam_price_tracker",
        description="Fetch US Steam prices and store them as JSON.",
    )
    parser.add_argument(
        "app_ids",
        nargs="*",
        type=int,
        help="Steam app ids to update (default: config.TRACKED_APP_IDS).",
    )
    parser.add_argument(
        "--store", default=STORE_PATH, help=f"price store path (default: {STORE_PATH})."
    )
    parser.add_argument(
        "--app-info-store",
        default=APP_INFO_PATH,
        help=f"app metadata store path (default: {APP_INFO_PATH}).",
    )
    parser.add_argument(
        "--test-email",
        action="store_true",
        help="send a canned test alert to validate SMTP credentials, then exit",
    )
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    if args.test_email:
        return _send_test_email()

    app_ids = args.app_ids or TRACKED_APP_IDS
    tracker = PriceTracker(
        store=JsonPriceStore(args.store),
        info_store=JsonAppInfoStore(args.app_info_store),
        alerter=_build_alerter(),
    )

    results = tracker.update_many(app_ids)
    for app_id, record in sorted(results.items()):
        info = tracker.info_store.get(app_id)
        name = info.name if info else str(app_id)
        print(f"{app_id} {name}: {record.price.final_formatted} ({record.price.currency})")

    # Non-zero exit if nothing succeeded.
    return 0 if results else 1


def _send_test_email() -> int:
    """Send a canned alert via SMTP to validate credentials (bypasses dedup)."""
    email_config = EmailConfig.from_env()
    if email_config is None:
        print(
            "Email is not configured: set STEAM_TRACKER_SMTP_USER and "
            "STEAM_TRACKER_SMTP_PASSWORD."
        )
        return 1
    canned = PriceAlert(
        app_id=2399830,
        price=PriceOverview(
            currency="USD", initial=4499, final=4499,
            discount_percent=0, final_formatted="$44.99",
        ),
        threshold=50.0,
        name="ARK: Survival Ascended (test alert)",
    )
    ok = EmailAlerter(email_config, EphemeralAlertState()).try_send([canned])
    if ok:
        print(f"Test alert sent to {email_config.to_addr} (check inbox/spam).")
        return 0
    print("Test alert NOT sent — see the error above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
