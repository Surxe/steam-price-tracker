"""Programmatic read/write access to the ``TRACKED_APP_IDS`` list in config.py.

The list lives in source (per the project's convention) but is edited here by
parsing and re-rendering just the assignment block, so existing ids and their
inline ``# name`` comments are preserved.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.py")

# Captures `TRACKED_APP_IDS: list[int] = [ ... ]` in three groups: head, inner, tail.
_LIST_RE = re.compile(
    r"(TRACKED_APP_IDS\s*:\s*list\[int\]\s*=\s*\[)(.*?)(\])",
    re.DOTALL,
)
# One entry inside the list: an id, then an optional inline comment.
_ENTRY_RE = re.compile(r"(\d+)[ \t]*,?[ \t]*(#[^\n]*)?")


class RegistryError(Exception):
    """Raised when config.py cannot be parsed or edited."""


def _parse(text: str) -> Tuple[re.Match, List[Tuple[int, Optional[str]]]]:
    match = _LIST_RE.search(text)
    if not match:
        raise RegistryError("Could not locate TRACKED_APP_IDS list in config.py")
    entries: List[Tuple[int, Optional[str]]] = []
    for entry in _ENTRY_RE.finditer(match.group(2)):
        comment = (entry.group(2) or "").strip() or None
        entries.append((int(entry.group(1)), comment))
    return match, entries


def _render(entries: List[Tuple[int, Optional[str]]]) -> str:
    lines = ["TRACKED_APP_IDS: list[int] = ["]
    for app_id, comment in entries:
        line = f"    {app_id},"
        if comment:
            line += f"  {comment}"
        lines.append(line)
    lines.append("]")
    return "\n".join(lines)


def read_tracked_ids(config_path: Path = DEFAULT_CONFIG_PATH) -> List[int]:
    """Return the app ids currently registered, in file order."""
    _, entries = _parse(Path(config_path).read_text(encoding="utf-8"))
    return [app_id for app_id, _ in entries]


def add_tracked_id(
    app_id: int,
    name: Optional[str] = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> bool:
    """Append ``app_id`` (with optional ``name`` comment) to TRACKED_APP_IDS.

    Returns ``True`` if it was added, ``False`` if it was already present.
    Idempotent and safe to re-run. The rewritten file is syntax-checked before
    it is saved.
    """
    path = Path(config_path)
    text = path.read_text(encoding="utf-8")
    match, entries = _parse(text)

    if app_id in {existing for existing, _ in entries}:
        return False

    comment = f"# {name}" if name else None
    entries.append((app_id, comment))
    new_text = text[: match.start()] + _render(entries) + text[match.end() :]

    # Guard against writing a file that won't import.
    try:
        ast.parse(new_text)
    except SyntaxError as exc:  # pragma: no cover - defensive
        raise RegistryError(f"Refusing to write invalid config.py: {exc}") from exc

    path.write_text(new_text, encoding="utf-8")
    return True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="steam_price_tracker.registry",
        description="Read or edit the TRACKED_APP_IDS list.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="register an app id")
    p_add.add_argument("app_id", type=int)
    p_add.add_argument("--name", help="product name, stored as an inline comment")

    sub.add_parser("list", help="print registered app ids")

    args = parser.parse_args(argv)

    if args.command == "list":
        for app_id in read_tracked_ids():
            print(app_id)
        return 0

    if args.command == "add":
        added = add_tracked_id(args.app_id, args.name)
        if added:
            label = f" ({args.name})" if args.name else ""
            print(f"Registered {args.app_id}{label} in TRACKED_APP_IDS.")
        else:
            print(f"{args.app_id} is already registered; no change.")
        return 0

    return 1  # pragma: no cover


if __name__ == "__main__":
    sys.exit(main())
