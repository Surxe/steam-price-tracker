"""CLI: ``python -m steam_price_tracker [app_id ...]``.

With no arguments it updates every id in :data:`config.TRACKED_APP_IDS`.
"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import APP_INFO_PATH, STORE_PATH, TRACKED_APP_IDS
from .storage import JsonAppInfoStore, JsonPriceStore
from .tracker import PriceTracker


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
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    app_ids = args.app_ids or TRACKED_APP_IDS
    tracker = PriceTracker(
        store=JsonPriceStore(args.store),
        info_store=JsonAppInfoStore(args.app_info_store),
    )

    results = tracker.update_many(app_ids)
    for app_id, record in sorted(results.items()):
        info = tracker.info_store.get(app_id)
        name = info.name if info else str(app_id)
        print(f"{app_id} {name}: {record.price.final_formatted} ({record.price.currency})")

    # Non-zero exit if nothing succeeded.
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
