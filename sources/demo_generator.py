"""Synthetic paid-media account with planted problems and a dark funnel.

Every conversion has a true cause (a paid channel, email, or an AI agent the
buyer researched through). What the account *reports* is only the last
tracked click, which is what the agent gets to see. The true causes are kept
in ground-truth files the agent never loads; they exist to score it.

Spend turns into conversions through a diminishing-returns response curve,
so budgets in state/ledger.json change what the next simulated week looks like.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PAID = ["google_search", "meta", "linkedin", "email"]
UNTRACKED = "direct"
AGENT = "ai_agent"

SELF_REPORT_TRUE = {
    "google_search": "Google",
    "meta": "Instagram or Facebook ad",
    "linkedin": "LinkedIn",
    "email": "Your newsletter",
}


@dataclass
class DayResult:
    daily_rows: list
    conversions: list
    journeys: list
    truth: list


def _agent_share(d: int, cfg: dict) -> float:
    df = cfg["dark_funnel"]
    span = max(cfg["days"] - 1, 1)
    t = min(d / span, 1.0)
    return df["agent_share_start"] + (df["agent_share_end"] - df["agent_share_start"]) * t


def _efficiency(channel: str, d: int, cfg: dict) -> float:
    p = cfg["planted"]
    e = 1.0
    # The two problems default to Meta and LinkedIn, but either can be moved to
    # another channel with a "channel" key (used by the held-out eval suite).
    m = p["meta_cpa_doubles"]
    if channel == m.get("channel", "meta") and m["enabled"] and d >= m["from_day"]:
        e *= m["efficiency"]
    li = p["linkedin_no_results"]
    if channel == li.get("channel", "linkedin") and li["enabled"] and d >= cfg["days"] - li["last_days"]:
        e = 0.0
    g = p["google_promo_spike"]
    if channel == "google_search" and g["enabled"] and g["from_day"] <= d < g["from_day"] + g["days"]:
        e *= g["efficiency_mult"]
    return e


def history_budget(channel: str, d: int, cfg: dict) -> float:
    """Daily budget the account ran during the 90 days of history."""
    base = cfg["channels"][channel]["budget"]
    p = cfg["planted"]
    li = p["linkedin_no_results"]
    start = cfg["days"] - li["last_days"]
    if channel == li.get("channel", "linkedin") and li["enabled"] and d >= start:
        frac = (d - start + 1) / li["last_days"]
        return base + (li["budget_end"] - base) * frac
    g = p["google_promo_spike"]
    if channel == "google_search" and g["enabled"] and g["from_day"] <= d < g["from_day"] + g["days"]:
        return base * g["spend_mult"]
    return base


def _simulate_day(d: int, day: date, budgets: dict, cfg: dict, rng: np.random.Generator) -> DayResult:
    aov = cfg["avg_order_value"]
    lt = cfg["last_touch_on_cause"]
    df_cfg = cfg["dark_funnel"]
    rr = cfg["self_report"]["response_rate"]

    spend, caused, expected_total = {}, {}, 0.0
    for ch in PAID:
        c = cfg["channels"][ch]
        s = max(0.0, budgets[ch] * (1 + rng.normal(0, c["spend_noise"]))) if budgets[ch] > 0 else 0.0
        expected = _efficiency(ch, d, cfg) * c["cmax"] * s / (s + c["k"]) if s > 0 else 0.0
        spend[ch] = round(s, 2)
        caused[ch] = int(rng.poisson(expected))
        expected_total += expected

    share = _agent_share(d, cfg)
    caused[AGENT] = int(rng.poisson(share / (1 - share) * expected_total))

    conversions, journeys, truth = [], [], []
    reported = {ch: [0, 0.0] for ch in PAID + [UNTRACKED]}
    i = 0
    for cause, n in caused.items():
        for _ in range(n):
            cid = f"c{d:03d}-{i:04d}"
            i += 1
            if cause == AGENT:
                path = ["google_search"] if rng.random() < df_cfg["branded_search_share"] else []
            elif cause == "google_search":
                path = []
                if rng.random() < 0.2:
                    path.append("meta")
                if rng.random() < 0.1:
                    path.append("linkedin")
                path.append("google_search")
            else:
                path = [cause] if rng.random() < lt[cause] else [cause, "google_search"]
                if cause != "email" and rng.random() < 0.25:
                    path.insert(0, "email")
            last = path[-1] if path else UNTRACKED
            revenue = round(aov * float(rng.lognormal(0, 0.3)), 2)

            answer = None
            if rng.random() < rr:
                if cause == AGENT:
                    answer = rng.choice(
                        ["Asked ChatGPT", "An AI assistant recommended you", "Google"],
                        p=[0.45, 0.2, 0.35],
                    )
                else:
                    answer = rng.choice(
                        [SELF_REPORT_TRUE[cause], "Google", "Word of mouth"], p=[0.65, 0.2, 0.15]
                    )
                answer = str(answer)

            reported[last][0] += 1
            reported[last][1] += revenue
            conversions.append(
                {"conversion_id": cid, "date": day.isoformat(), "last_touch": last,
                 "revenue": revenue, "self_reported": answer}
            )
            for step, ch in enumerate(path):
                journeys.append({"conversion_id": cid, "step": step, "channel": ch})
            truth.append({"conversion_id": cid, "date": day.isoformat(), "cause": cause})

    daily_rows = [
        {"date": day.isoformat(), "channel": ch, "spend": spend.get(ch, 0.0),
         "conversions": reported[ch][0], "revenue": round(reported[ch][1], 2)}
        for ch in PAID + [UNTRACKED]
    ]
    return DayResult(daily_rows, conversions, journeys, truth)


def _frames(results: list[DayResult]):
    daily = pd.DataFrame([r for x in results for r in x.daily_rows])
    conv = pd.DataFrame([r for x in results for r in x.conversions])
    jour = pd.DataFrame([r for x in results for r in x.journeys])
    truth = pd.DataFrame([r for x in results for r in x.truth])
    return daily, conv, jour, truth


def _ground_truth(daily: pd.DataFrame, truth: pd.DataFrame, cfg: dict) -> dict:
    start = date.fromisoformat(cfg["start_date"])
    p = cfg["planted"]

    def day(n: int) -> str:
        return (start + timedelta(days=n)).isoformat()

    by_cause = truth["cause"].value_counts().to_dict()
    total = int(len(truth))
    spend = daily.groupby("channel")["spend"].sum().to_dict()
    reported = daily.groupby("channel")["conversions"].sum().to_dict()
    channels = {}
    for ch in PAID + [AGENT, UNTRACKED]:
        n = int(by_cause.get(ch, 0))
        channels[ch] = {
            "true_conversions": n,
            "true_share": round(n / total, 4) if total else 0.0,
            "reported_last_touch": int(reported.get(ch, 0)),
            "spend": round(float(spend.get(ch, 0.0)), 2),
            "true_cpa": round(spend.get(ch, 0.0) / n, 2) if n and spend.get(ch) else None,
        }
    li_start = cfg["days"] - p["linkedin_no_results"]["last_days"]
    g = p["google_promo_spike"]
    return {
        "label": "synthetic data",
        "seed": cfg["seed"],
        "days": cfg["days"],
        "channels": channels,
        "planted": [
            {"id": 1, "name": "meta_cpa_doubles", "channel": p["meta_cpa_doubles"].get("channel", "meta"),
             "from": day(p["meta_cpa_doubles"]["from_day"])},
            {"id": 2, "name": "linkedin_no_results", "channel": p["linkedin_no_results"].get("channel", "linkedin"),
             "from": day(li_start), "to": day(cfg["days"] - 1)},
            {"id": 3, "name": "email_under_credited", "channel": "email"},
            {"id": 4, "name": "dark_funnel", "channel": AGENT,
             "agent_share_start": cfg["dark_funnel"]["agent_share_start"],
             "agent_share_end": cfg["dark_funnel"]["agent_share_end"]},
            {"id": "red_herring", "name": "google_promo_spike", "channel": "google_search",
             "from": day(g["from_day"]), "to": day(g["from_day"] + g["days"] - 1)},
        ],
    }


def generate_history(cfg: dict, out_dir: Path) -> dict:
    """Write 90 days of history plus ground truth. Returns the ground truth."""
    rng = np.random.default_rng(cfg["seed"])
    start = date.fromisoformat(cfg["start_date"])
    results = []
    for d in range(cfg["days"]):
        budgets = {ch: history_budget(ch, d, cfg) for ch in PAID}
        results.append(_simulate_day(d, start + timedelta(days=d), budgets, cfg, rng))
    daily, conv, jour, truth = _frames(results)

    out_dir.mkdir(parents=True, exist_ok=True)
    daily.to_csv(out_dir / "daily.csv", index=False)
    conv.to_csv(out_dir / "conversions.csv", index=False)
    jour.to_csv(out_dir / "journeys.csv", index=False)
    truth.to_csv(out_dir / "truth_conversions.csv", index=False)
    gt = _ground_truth(daily, truth, cfg)
    (out_dir / "ground_truth.json").write_text(json.dumps(gt, indent=2))
    return gt


def advance_week(cfg: dict, budgets: dict, out_dir: Path, week: int) -> pd.DataFrame:
    """Simulate 7 more days from the ledger's daily budgets and append them.

    Planted problems persist: Meta stays inefficient and LinkedIn keeps
    converting nothing for as long as it gets budget. Returns the new daily rows.
    """
    daily_old = pd.read_csv(out_dir / "daily.csv")
    n_days = daily_old["date"].nunique()
    start = date.fromisoformat(cfg["start_date"])
    rng = np.random.default_rng(cfg["seed"] + 1000 * week)
    results = [
        _simulate_day(d, start + timedelta(days=d), budgets, cfg, rng)
        for d in range(n_days, n_days + 7)
    ]
    daily, conv, jour, truth = _frames(results)
    for name, frame in [("daily", daily), ("conversions", conv),
                        ("journeys", jour), ("truth_conversions", truth)]:
        path = out_dir / f"{name}.csv"
        pd.concat([pd.read_csv(path), frame]).to_csv(path, index=False)
    return daily
