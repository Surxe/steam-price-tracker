"""Tests for search rendering and the config registry editor."""
from __future__ import annotations

import shutil
from pathlib import Path

from steam_price_tracker import SearchResult
from steam_price_tracker import registry
from steam_price_tracker.search import to_json, to_markdown

CONFIG_SRC = Path(__file__).resolve().parent.parent / "steam_price_tracker" / "config.py"

RESULTS = [
    SearchResult(app_id=2399830, name="ARK: Survival Ascended", type="app"),
    SearchResult(app_id=346110, name="ARK: Survival Evolved", type="app"),
]


# --------------------------- search rendering ---------------------------- #
def test_markdown_has_row_per_result():
    md = to_markdown(RESULTS)
    assert "| # | App ID | Type | Name |" in md
    assert "`2399830`" in md and "ARK: Survival Ascended" in md
    assert md.count("\n") == 3  # header + separator + 2 rows -> 3 newlines


def test_markdown_escapes_pipes():
    md = to_markdown([SearchResult(app_id=1, name="A | B", type="app")])
    assert "A \\| B" in md


def test_markdown_empty():
    assert to_markdown([]) == "_No matching apps found._"


def test_json_roundtrips_fields():
    import json

    data = json.loads(to_json(RESULTS))
    assert data[0] == {"app_id": 2399830, "name": "ARK: Survival Ascended", "type": "app"}


# ------------------------------- registry -------------------------------- #
def _temp_config(tmp_path: Path) -> Path:
    dst = tmp_path / "config.py"
    shutil.copy(CONFIG_SRC, dst)
    return dst


def test_add_tracked_id_appends_with_comment(tmp_path: Path):
    cfg = _temp_config(tmp_path)
    assert registry.add_tracked_id(346110, "ARK: Survival Evolved", cfg) is True
    assert registry.read_tracked_ids(cfg) == [2399830, 346110]
    assert "346110,  # ARK: Survival Evolved" in cfg.read_text()


def test_add_tracked_id_is_idempotent(tmp_path: Path):
    cfg = _temp_config(tmp_path)
    assert registry.add_tracked_id(2399830, "dup", cfg) is False
    assert registry.read_tracked_ids(cfg) == [2399830]


def test_edited_config_still_imports(tmp_path: Path):
    import importlib.util

    cfg = _temp_config(tmp_path)
    registry.add_tracked_id(346110, "ARK: Survival Evolved", cfg)
    spec = importlib.util.spec_from_file_location("cfg_under_test", cfg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.TRACKED_APP_IDS == [2399830, 346110]
    assert module.STORE_PATH == "data/prices.json"


# ------------------------------ thresholds ------------------------------- #
# A synthetic config with an EMPTY threshold dict, so these tests are
# deterministic regardless of what the real config.py currently declares.
_SYNTHETIC_CONFIG = '''\
from __future__ import annotations

TRACKED_APP_IDS: list[int] = [
    2399830,
]

STORE_PATH = "data/prices.json"
APP_INFO_PATH = "data/apps.json"
ALERT_STATE_PATH = "data/alert_state.json"

ALERT_THRESHOLDS: dict[int, float] = {}

EMAIL_TO = "eethansur@gmail.com"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
'''


def _empty_threshold_config(tmp_path: Path) -> Path:
    dst = tmp_path / "config.py"
    dst.write_text(_SYNTHETIC_CONFIG, encoding="utf-8")
    return dst


def test_set_threshold_from_empty(tmp_path: Path):
    cfg = _empty_threshold_config(tmp_path)
    assert registry.read_alert_thresholds(cfg) == {}
    prev = registry.set_alert_threshold(2399830, 30.0, "ARK: Survival Ascended", cfg)
    assert prev is None
    assert registry.read_alert_thresholds(cfg) == {2399830: 30.0}
    assert "2399830: 30.0,  # ARK: Survival Ascended" in cfg.read_text()


def test_set_threshold_updates_existing(tmp_path: Path):
    cfg = _empty_threshold_config(tmp_path)
    registry.set_alert_threshold(2399830, 30.0, config_path=cfg)
    prev = registry.set_alert_threshold(2399830, 25.0, config_path=cfg)
    assert prev == 30.0
    assert registry.read_alert_thresholds(cfg) == {2399830: 25.0}


def test_thresholds_config_still_imports(tmp_path: Path):
    import importlib.util

    cfg = _empty_threshold_config(tmp_path)
    registry.set_alert_threshold(2399830, 30.0, "ARK: Survival Ascended", cfg)
    registry.set_alert_threshold(346110, 12.5, "ARK: Survival Evolved", cfg)
    spec = importlib.util.spec_from_file_location("cfg_thr", cfg)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ALERT_THRESHOLDS == {2399830: 30.0, 346110: 12.5}
