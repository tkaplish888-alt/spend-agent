"""Week 1 gate: problems 1 and 2 caught, the red herring flagged for review
rather than missed or escalated, and the run is reproducible from the seed.

    python -m pytest tests/
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis import anomalies  # noqa: E402
from sources import DemoSource  # noqa: E402
from sources.demo_generator import advance_week, generate_history  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load((ROOT / "config.yaml").read_text())


@pytest.fixture(scope="module")
def run(cfg, tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    generate_history(cfg["demo"], d)
    data = DemoSource(cfg, d).load()
    return d, data, anomalies.run_all(data, cfg)


def _day(cfg, n):
    return (date.fromisoformat(cfg["demo"]["start_date"]) + timedelta(days=n)).isoformat()


def test_problem_1_meta_cpa_shift_caught_near_day_60(cfg, run):
    _, _, flags = run
    f = [x for x in flags if x["rule"] == "cpa_level_shift" and x["channel"] == "meta"]
    assert len(f) == 1
    planted = cfg["demo"]["planted"]["meta_cpa_doubles"]["from_day"]
    assert abs(date.fromisoformat(f[0]["since"]) - date.fromisoformat(_day(cfg, planted))).days <= 3


def test_problem_2_linkedin_spend_without_results(cfg, run):
    _, _, flags = run
    f = [x for x in flags if x["rule"] == "spend_without_results" and x["channel"] == "linkedin"]
    assert len(f) == 1
    assert f[0]["severity"] == "critical"
    assert f[0]["evidence"]["days"] >= cfg["demo"]["planted"]["linkedin_no_results"]["last_days"]
    assert f[0]["evidence"]["daily_spend_trend"] > 0
    # flagged once, not twice
    assert sum(1 for x in flags if x["channel"] == "linkedin") == 1


def test_red_herring_flagged_for_review_not_escalated(cfg, run):
    _, _, flags = run
    g = cfg["demo"]["planted"]["google_promo_spike"]
    f = [x for x in flags if x["rule"] == "spend_spike" and x["channel"] == "google_search"]
    assert len(f) == 1
    assert f[0]["severity"] == "review"
    assert f[0]["since"] == _day(cfg, g["from_day"])


def test_no_false_alarms_on_healthy_channels(run):
    _, _, flags = run
    assert not [x for x in flags if x["channel"] == "email"]
    assert not [x for x in flags if x["channel"] == "google_search" and x["severity"] != "review"]


def test_dark_funnel_surfaces_as_untracked_lift(run):
    _, _, flags = run
    f = [x for x in flags if x["rule"] == "untracked_lift"]
    assert len(f) == 1
    ev = f[0]["evidence"]
    assert ev["self_reported_ai_share_late"] > ev["self_reported_ai_share_early"]


def test_reproducible_from_seed(cfg, tmp_path):
    def digest(d):
        generate_history(cfg["demo"], d)
        return {p.name: hashlib.md5(p.read_bytes()).hexdigest() for p in sorted(d.iterdir())}
    assert digest(tmp_path / "a") == digest(tmp_path / "b")


def test_ledger_changes_next_week(cfg, tmp_path):
    """Closed loop: cutting LinkedIn in the ledger removes its spend next week."""
    generate_history(cfg["demo"], tmp_path)
    budgets = {ch: c["budget"] for ch, c in cfg["demo"]["channels"].items()}
    budgets["linkedin"] = 0
    week = advance_week(cfg["demo"], budgets, tmp_path, week=1)
    assert week[week["channel"] == "linkedin"]["spend"].sum() == 0
    assert week["date"].nunique() == 7
