"""Week 2 plumbing: attribution models, tool guardrails, and the loop.

The loop tests use a scripted stand-in for Claude so they run offline and
free. They prove the machinery (memory, ledger, step cap, trace), not the
agent's judgment; that is checked by a real run plus agent.evaluate.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent import run_week  # noqa: E402
from agent.tools import ToolBox  # noqa: E402
from analysis import attribution  # noqa: E402
from sources import DemoSource  # noqa: E402
from sources.demo_generator import generate_history  # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load((ROOT / "config.yaml").read_text())


@pytest.fixture(scope="module")
def data(cfg, tmp_path_factory):
    d = tmp_path_factory.mktemp("data")
    gt = generate_history(cfg["demo"], d)
    return DemoSource(cfg, d).load(), gt


# ---------- attribution ----------

def test_every_model_gives_out_exactly_all_the_credit(data):
    d, _ = data
    credit = attribution.run_models(d.conversions, d.journeys)
    assert (credit.sum() - len(d.conversions)).abs().max() < 1


def test_last_touch_is_worst_and_markov_sees_email(data):
    d, gt = data
    credit = attribution.run_models(d.conversions, d.journeys)
    truth = {k: v["true_conversions"] for k, v in gt["channels"].items()}
    s = attribution.score_against_truth(credit, truth)
    assert s["misallocated_share"].idxmax() == "last_touch"
    assert abs(s.loc["markov", "err_email"]) < 0.03
    # no click model can see the AI-agent buyers
    assert (s["err_ai_agent"] < -0.1).all()


# ---------- guardrails ----------

def _box(d, cfg):
    ledger = {"daily_budgets": {"google_search": 600, "meta": 500, "linkedin": 450, "email": 40}}
    return ToolBox(data=d, cfg=cfg, ledger=ledger, log=[])


def test_budget_increase_capped_but_pause_allowed(data, cfg):
    box = _box(data[0], cfg)
    assert "error" in box.set_budget("google_search", 2000, "test", "high")
    assert box.set_budget("linkedin", 0, "zero results", "high")["staged"]["to"] == 0


def test_memo_needs_a_verdict_on_every_flag(data, cfg):
    box = _box(data[0], cfg)
    assert "error" in box.write_memo("x", [], "memo", "low")
    verdicts = [{"flag_id": f["id"], "verdict": "watch", "reason": "r"} for f in box.flags]
    assert box.write_memo("x", verdicts, "memo", "low") == {"done": True}


# ---------- the loop, with a scripted stand-in for Claude ----------

class ScriptedClaude:
    """Calls tools in a fixed order, reading flag ids from earlier results."""

    def __init__(self, plan):
        self.plan = plan
        self.messages = self

    def create(self, **kw):
        msgs = kw["messages"]
        step = sum(1 for m in msgs if m["role"] == "assistant")
        nudged = any(isinstance(m["content"], list) and any(
            isinstance(c, dict) and c.get("type") == "text" and "Step cap" in c.get("text", "")
            for c in m["content"]) for m in msgs if m["role"] == "user")
        if "tool_choice" in kw or nudged:
            step = len(self.plan) - 1
        name, args = self.plan[min(step, len(self.plan) - 1)]
        if name == "write_memo":
            flags = []
            for m in msgs:
                if m["role"] == "user" and isinstance(m["content"], list):
                    for c in m["content"]:
                        if c.get("type") == "tool_result" and '"flags"' in c["content"]:
                            flags = json.loads(c["content"])["flags"]
            args = {"headline": "Paused LinkedIn.", "overall_confidence": "medium",
                    "memo_markdown": "## Last week's moves\nscripted",
                    "flag_verdicts": [{"flag_id": f["id"], "verdict": "watch", "reason": "r"} for f in flags]}
        return NS(content=[NS(type="text", text=f"step {step}"),
                           NS(type="tool_use", id=f"t{step}", name=name, input=args)],
                  stop_reason="tool_use")


PLAN = [
    ("review_last_run", {}),
    ("get_flags", {}),
    ("compare_attribution", {}),
    ("set_budget", {"channel": "linkedin", "daily_budget": 0, "reason": "zero results", "confidence": "high"}),
    ("write_memo", {}),
]


@pytest.fixture()
def root(tmp_path):
    for sub in ["state", "outputs"]:
        (tmp_path / sub).mkdir()
    shutil.copy(ROOT / "config.yaml", tmp_path / "config.yaml")
    return tmp_path


def test_two_runs_close_the_loop(cfg, root):
    run_week.reset(cfg, root)
    first = run_week.run(ScriptedClaude(PLAN), cfg, root)
    assert first["run"] == 1 and first["moves"][0]["channel"] == "linkedin"
    ledger = json.loads((root / "state" / "ledger.json").read_text())
    assert ledger["daily_budgets"]["linkedin"] == 0

    second = run_week.run(ScriptedClaude(PLAN), cfg, root)
    assert second["run"] == 2
    daily = pd.read_csv(root / "data" / "daily.csv", parse_dates=["date"])
    new_week = daily[daily["date"] > pd.Timestamp(first["data_end"])]
    assert new_week["date"].nunique() == 7
    assert new_week[new_week["channel"] == "linkedin"]["spend"].sum() == 0

    trace = json.loads((root / "outputs" / "trace.json").read_text())
    assert trace[0]["tool"] == "review_last_run"
    assert '"first_run": false' in trace[0]["result_preview"]


def test_review_reports_before_and_after(cfg, root):
    run_week.reset(cfg, root)
    run_week.run(ScriptedClaude(PLAN), cfg, root)
    from sources.demo_generator import advance_week
    log = json.loads((root / "state" / "agent_log.json").read_text())
    ledger = json.loads((root / "state" / "ledger.json").read_text())
    advance_week(cfg["demo"], ledger["daily_budgets"], root / "data", week=1)
    box = ToolBox(data=DemoSource(cfg, root / "data").load(), cfg=cfg, ledger=ledger, log=log)
    r = box.review_last_run()
    li = r["moves_and_outcomes"][0]
    assert li["week_before"]["spend"] > 0 and li["week_after"]["spend"] == 0
    assert r["days_since"] == 7


def test_step_cap_forces_the_memo(cfg, root):
    run_week.reset(cfg, root)
    looping = [("get_overview", {})] * 30 + [("write_memo", {})]
    cfg2 = {**cfg, "agent": {**cfg["agent"], "max_tool_calls": 4}}
    # get_flags is needed for verdicts; put it first
    entry = run_week.run(ScriptedClaude([("get_flags", {})] + looping), cfg2, root)
    assert entry["tool_calls"] <= 4 + 1
