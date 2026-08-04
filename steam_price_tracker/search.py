"""Search Steam by product name and render candidates as Markdown or JSON.

CLI::

    python -m steam_price_tracker.search "<game name>" [--limit N] [--format md|json]

Designed for the ``add-app`` skill: the Markdown output can be dropped straight
into chat for the user to pick from, and the JSON output is machine-readable.
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

from .client import AppSearchSource, SteamStoreClient
from .exceptions import SteamAPIError
from .models import SearchResult


def to_json(results: List[SearchResult]) -> str:
    return json.dumps(
        [{"app_id": r.app_id, "name": r.name, "type": r.type} for r in results],
        indent=2,
    )


def _escape(cell: str) -> str:
    """Escape pipes so names never break the Markdown table."""
    return cell.replace("|", "\\|")


def to_markdown(results: List[SearchResult]) -> str:
    if not results:
        return "_No matching apps found._"
    lines = [
        "| # | App ID | Type | Name |",
        "| - | ------ | ---- | ---- |",
    ]
    for i, r in enumerate(results, start=1):
        lines.append(f"| {i} | `{r.app_id}` | {r.type} | {_escape(r.name)} |")
    return "\n".join(lines)


def search(
    term: str,
    limit: int = 10,
    source: Optional[AppSearchSource] = None,
) -> List[SearchResult]:
    source = source or SteamStoreClient(country_code="us")
    return source.search_apps(term, limit=limit)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="steam_price_tracker.search",
        description="Search Steam by product name for candidate app ids.",
    )
    parser.add_argument("term", help="game / product name to search for")
    parser.add_argument("--limit", type=int, default=10, help="max results (default 10)")
    parser.add_argument(
        "--format", choices=("md", "json"), default="md", help="output format"
    )
    args = parser.parse_args(argv)

    try:
        results = search(args.term, limit=args.limit)
    except SteamAPIError as exc:
        print(f"Search failed: {exc}", file=sys.stderr)
        return 1

    render = to_markdown if args.format == "md" else to_json
    print(render(results))
    return 0 if results else 2  # 2 == searched OK but nothing matched


if __name__ == "__main__":
    sys.exit(main())
