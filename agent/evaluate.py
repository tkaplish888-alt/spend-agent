"""Score the agent and the attribution models against the planted truth.

Evaluation only. Reads ground truth the agent never sees, and writes
outputs/scorecard.json for the page and the README.

    python -m agent.evaluate
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from analysis import attribution

ROOT = Path(__file__).resolve().parents[1]


def _flag_verdict(entry: dict, rule: str, channel: str) -> str | None:
    ids = {f["id"] for f in entry["flags"] if f["rule"] == rule and f["channel"] == channel}
    for v in entry["flag_verdicts"]:
        if v["flag_id"] in ids:
            return v["verdict"]
    return None


def _move(entry: dict, channel: str) -> dict | None:
    return next((m for m in entry["moves"] if m["channel"] == channel), None)


def score_run(entry: dict, memo: str) -> dict:
    text = memo.lower()
    meta, li, gs = _move(entry, "meta"), _move(entry, "linkedin"), _move(entry, "google_search")
    test_channels = {t["channel"] for t in entry["tests"]}
    checks = {
        "p1_meta_cut": bool(meta and meta["to"] < meta["from"]),
        "p2_linkedin_paused": bool(li and li["to"] <= 0.2 * li["from"]),
        "p3_email_gap_explained": "email" in test_channels or ("email" in text and "credit" in text),
        "p4_dark_funnel_explained": (
            _flag_verdict(entry, "untracked_lift", "direct") in {"act", "watch"}
            and any(k in text for k in ["chatgpt", "ai assistant", "ai agent", "untracked"])
        ),
        "p4_no_budget_chased_to_search": not (gs and gs["to"] > gs["from"]),
        "red_herring_dismissed": _flag_verdict(entry, "spend_spike", "google_search") in {"dismiss", None},
        "reviewed_last_week_first": bool(entry["tools_used"]) and entry["tools_used"][0] == "review_last_run",
    }
    if entry["run"] > 1:
        checks["judged_previous_moves"] = "first run" not in text
    return checks


def main(root: Path = ROOT) -> dict:
    log = json.loads((root / "state" / "agent_log.json").read_text())
    gt = json.loads((root / "data" / "ground_truth.json").read_text())
    conv = pd.read_csv(root / "data" / "conversions.csv")
    jour = pd.read_csv(root / "data" / "journeys.csv")
    truth = {k: v["true_conversions"] for k, v in gt["channels"].items()}
    scores = attribution.score_against_truth(attribution.run_models(conv, jour), truth)

    memo = (root / "outputs" / "memo.md").read_text() if (root / "outputs" / "memo.md").exists() else ""
    card = {
        "label": "synthetic data",
        "attribution_misallocated_share": scores["misallocated_share"].to_dict(),
        "note": "Truth includes AI-agent buyers no click model can see, so no model scores zero.",
        "latest_run": log[-1]["run"] if log else None,
        "checks": score_run(log[-1], memo) if log else {},
    }
    (root / "outputs" / "scorecard.json").write_text(json.dumps(card, indent=2))
    return card


if __name__ == "__main__":
    c = main()
    print(json.dumps(c, indent=2))
