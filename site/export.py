"""Bundle the agent's latest outputs into one file for the dashboard page.

    python site/export.py      (writes site/dashboard.json)

Run as a script: "site" is also the name of a Python built-in module.

Also precomputes the dark funnel slider: the demo account is regenerated at
several fixed shares of AI-agent buyers, and each attribution model is scored
against the truth at every step. The page only reads numbers; it runs nothing.
"""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis import attribution  # noqa: E402
from sources.demo_generator import generate_history  # noqa: E402

OUT = ROOT / "site" / "dashboard.json"

CHANNEL_NAMES = {
    "google_search": "Google Search", "meta": "Meta", "linkedin": "LinkedIn",
    "email": "Email", "direct": "Direct (no source)", "ai_agent": "AI assistants (invisible)",
}
MODEL_NAMES = {
    "first_touch": "First-touch", "last_touch": "Last-touch", "linear": "Linear",
    "time_decay": "Time-decay", "markov": "Markov",
}
TOOL_LABELS = {
    "review_last_run": "Checked whether last week's moves worked",
    "get_overview": "Looked at every channel's last 7 days",
    "get_flags": "Read the anomaly flags",
    "drill_down": "Drilled into one channel",
    "compare_attribution": "Compared the five attribution models",
    "get_self_reported": "Read 'How did you hear about us?' answers",
    "get_ledger": "Checked current budgets and guardrails",
    "set_budget": "Changed a budget",
    "recommend_test": "Recommended an incrementality test",
    "write_memo": "Wrote the memo",
}
SHARES = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]


def _read(p: Path):
    return json.loads(p.read_text())


def _hero(col: pd.Series) -> str:
    return str(col.drop(labels=["direct"], errors="ignore").idxmax())


def dark_funnel_scenarios(demo_cfg: dict) -> list[dict]:
    out = []
    for share in SHARES:
        cfg = copy.deepcopy(demo_cfg)
        cfg["dark_funnel"]["agent_share_start"] = share
        cfg["dark_funnel"]["agent_share_end"] = share
        with tempfile.TemporaryDirectory() as d:
            generate_history(cfg, Path(d))
            conv = pd.read_csv(Path(d) / "conversions.csv")
            jour = pd.read_csv(Path(d) / "journeys.csv")
            gt = _read(Path(d) / "ground_truth.json")
        credit = attribution.run_models(conv, jour)
        credit = credit / credit.sum()  # counts -> shares
        truth = {k: v["true_conversions"] for k, v in gt["channels"].items()}
        scores = attribution.score_against_truth(credit, truth)
        total = sum(truth.values())
        out.append({
            "agent_share": share,
            "true_share": {k: round(v / total, 4) for k, v in truth.items() if v},
            "credit_share": {m: {ch: round(float(v), 4) for ch, v in credit[m].items()} for m in credit.columns},
            "hero": {m: _hero(credit[m]) for m in credit.columns},
            "misallocated": scores["misallocated_share"].to_dict(),
        })
    return out


def main(root: Path = ROOT) -> dict:
    cfg = yaml.safe_load((root / "config.yaml").read_text())
    run = _read(root / "outputs" / "run.json")
    flags = _read(root / "outputs" / "flags.json")
    attr = _read(root / "outputs" / "attribution.json")
    score = _read(root / "outputs" / "scorecard.json")
    trace = _read(root / "outputs" / "trace.json")
    ledger = _read(root / "state" / "ledger.json")
    gt = _read(root / "data" / "ground_truth.json")
    memo = (root / "outputs" / "memo.md").read_text()

    verdicts = {v["flag_id"]: v for v in run.get("flag_verdicts", [])}
    total_true = sum(c["true_conversions"] for c in gt["channels"].values())
    # Budgets when the agent first took over: the "from" of its first move on a
    # channel, else the configured budget (LinkedIn had crept up to $450 by then).
    starting = {ch: c["budget"] for ch, c in cfg["demo"]["channels"].items()}
    for h in reversed(ledger.get("history", [])):
        for m in h.get("moves", []):
            starting[m["channel"]] = m["from"]

    data = {
        "label": "Synthetic data. Every number here is generated; no real ad account.",
        "channel_names": CHANNEL_NAMES,
        "model_names": MODEL_NAMES,
        "run": {k: run.get(k) for k in ["run", "ran_at", "data_end", "headline", "confidence"]},
        "memo_markdown": memo,
        "budgets": {"starting": starting, "current": ledger["daily_budgets"]},
        "moves_history": ledger.get("history", []),
        "tests": run.get("tests", []),
        "flags": [{**f, "verdict": verdicts.get(f["id"], {}).get("verdict"),
                   "verdict_reason": verdicts.get(f["id"], {}).get("reason")} for f in flags],
        "attribution": {
            "credit_share": attr["credit_share"],
            "disagreement": attr["disagreement"],
            "true_share": {ch: round(c["true_conversions"] / total_true, 4)
                           for ch, c in gt["channels"].items() if c["true_conversions"]},
        },
        "scorecard": score,
        "trace": [{"step": t["step"], "tool": t["tool"],
                   "label": TOOL_LABELS.get(t["tool"], t["tool"]),
                   # Short arguments only; long ones (memo text, test design) live elsewhere on the page.
                   "input": {k: v for k, v in t["input"].items() if len(str(v)) <= 40}} for t in trace],
        "dark_funnel_scenarios": dark_funnel_scenarios(cfg["demo"]),
    }
    OUT.write_text(json.dumps(data, indent=1))
    return data


if __name__ == "__main__":
    d = main()
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")
