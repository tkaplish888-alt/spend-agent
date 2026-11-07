"""Tools the agent can choose to call.

Read-only tools look at the account. Two action tools stage budget changes
and test recommendations. write_memo ends the run.

The agent never sees ground truth. Everything here is what a real account
would expose: spend, reported conversions, journeys and self-reported answers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import pandas as pd

from analysis import anomalies, attribution, metrics

CONFIDENCE = ["low", "medium", "high"]
MAX_INCREASE = 0.5  # a channel can grow at most 50% per run; cuts and pauses are unlimited


def _records(df: pd.DataFrame) -> list[dict]:
    df = df.copy()
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.date.astype(str)
    return json.loads(df.to_json(orient="records"))


@dataclass
class ToolBox:
    data: object
    cfg: dict
    ledger: dict
    log: list
    staged: dict = field(default_factory=dict)
    tests: list = field(default_factory=list)
    memo: dict | None = None

    def __post_init__(self):
        self.paid = self.data.meta["paid_channels"]
        self.flags = anomalies.run_all(self.data, self.cfg)
        self.credit = attribution.run_models(self.data.conversions, self.data.journeys)

    # ---------- read-only ----------

    def review_last_run(self) -> dict:
        if not self.log:
            return {"first_run": True, "note": "No previous run. Nothing to review."}
        last = self.log[-1]
        d = self.data.daily
        cut = pd.Timestamp(last["data_end"])
        before = d[(d["date"] > cut - pd.Timedelta(days=7)) & (d["date"] <= cut)]
        after = d[d["date"] > cut]
        outcomes = []
        for mv in last.get("moves", []):
            ch = mv["channel"]
            b, a = before[before["channel"] == ch], after[after["channel"] == ch]
            def week(x):
                s, c = float(x["spend"].sum()), int(x["conversions"].sum())
                return {"spend": round(s, 2), "conversions": c, "cpa": round(s / c, 2) if c else None}
            outcomes.append({**mv, "week_before": week(b), "week_after": week(a)})
        total = lambda x: {"spend": round(float(x[x["channel"].isin(self.paid)]["spend"].sum()), 2),
                           "conversions": int(x["conversions"].sum())}
        return {
            "first_run": False, "previous_run": last["run"], "previous_headline": last["headline"],
            "previous_confidence": last["confidence"], "moves_and_outcomes": outcomes,
            "tests_recommended": last.get("tests", []),
            "account_week_before": total(before), "account_week_after": total(after),
            "days_since": int(after["date"].nunique()),
        }

    def get_overview(self) -> dict:
        d = self.data.daily
        end = d["date"].max()
        last7 = d[d["date"] > end - pd.Timedelta(days=7)]
        prior = d[(d["date"] <= end - pd.Timedelta(days=7)) & (d["date"] > end - pd.Timedelta(days=35))]
        cur = metrics._ratios(last7.groupby("channel", as_index=False)[["spend", "conversions", "revenue"]].sum())
        base = prior.groupby("channel")[["spend", "conversions", "revenue"]].sum() / 4
        base = metrics._ratios(base.reset_index())
        merged = cur.merge(base, on="channel", suffixes=("", "_prior4wk_avg"))
        return {"label": self.data.meta["label"], "data_range": [self.data.meta["start"], self.data.meta["end"]],
                "note": "Conversions are platform-reported (last tracked click). 'direct' has no tracked click.",
                "last_7_days_vs_prior_4_week_average": _records(merged)}

    def get_flags(self) -> dict:
        return {"flags": self.flags,
                "note": "Rule-based leads, not verdicts. 'review' means investigate before deciding."}

    def drill_down(self, channel: str, granularity: str = "week", periods: int = 8) -> dict:
        if channel not in self.paid + [self.data.meta["untracked_channel"]]:
            return {"error": f"Unknown channel {channel}. Choose from {self.paid + ['direct']}."}
        periods = max(1, min(int(periods), 26 if granularity == "week" else 60))
        if granularity == "day":
            m = metrics.daily_metrics(self.data.daily)
            m = m[m["channel"] == channel].tail(periods)
            cols = ["date", "spend", "conversions", "revenue", "cpa", "roas"]
        else:
            m = metrics.weekly_metrics(self.data.daily)
            m = m[m["channel"] == channel].tail(periods)
            cols = ["week_start", "spend", "conversions", "revenue", "cpa", "roas"]
        return {"channel": channel, "granularity": granularity, "rows": _records(m[cols])}

    def compare_attribution(self) -> dict:
        share = (self.credit / self.credit.sum()).round(3)
        spend = self.data.daily.groupby("channel")["spend"].sum()
        return {
            "models": attribution.__doc__.strip().split("\n\n")[1],
            "credit_share_by_model": json.loads(share.to_json(orient="index")),
            "disagreement": json.loads(attribution.disagreement(self.credit).to_json(orient="index")),
            "implied_cpa_by_model": json.loads(attribution.implied_cpa(self.credit, spend).to_json(orient="index")),
            "note": "Models only see tracked clicks. Large spread means credit depends on the rule, not the data.",
        }

    def get_self_reported(self) -> dict:
        c = self.data.conversions.dropna(subset=["self_reported"]).copy()
        c["week_start"] = c["date"] - pd.to_timedelta(c["date"].dt.weekday, unit="D")
        table = pd.crosstab(c["week_start"], c["self_reported"], normalize="index").round(3)
        table["responses"] = c.groupby("week_start").size()
        table = table.reset_index()
        return {"question": "How did you hear about us?",
                "response_rate": round(len(c) / len(self.data.conversions), 3),
                "weekly_answer_share": _records(table)}

    def get_ledger(self) -> dict:
        return {"mode": self.cfg["action_mode"], "daily_budgets": self.ledger["daily_budgets"],
                "staged_this_run": self.staged,
                "guardrails": f"Max +{int(MAX_INCREASE * 100)}% per channel per run; cuts and pauses (0) allowed. "
                              + ("Demo mode: changes apply to the simulated ledger."
                                 if self.cfg["action_mode"] == "demo" else
                                 "Real mode: changes become proposals for a human to approve.")}

    # ---------- actions ----------

    def set_budget(self, channel: str, daily_budget: float, reason: str, confidence: str) -> dict:
        if channel not in self.paid:
            return {"error": f"Unknown channel {channel}. Choose from {self.paid}."}
        if confidence not in CONFIDENCE:
            return {"error": f"confidence must be one of {CONFIDENCE}"}
        current = float(self.ledger["daily_budgets"][channel])
        new = max(0.0, float(daily_budget))
        if new > current * (1 + MAX_INCREASE):
            return {"error": f"Blocked: {channel} can rise at most to {current * (1 + MAX_INCREASE):.0f}/day this run."}
        self.staged[channel] = {"channel": channel, "from": current, "to": round(new, 2),
                                "reason": reason, "confidence": confidence}
        return {"staged": self.staged[channel], "applies": "after this run" if self.cfg["action_mode"] == "demo"
                else "as a proposal for human approval"}

    def recommend_test(self, channel: str, hypothesis: str, design: str) -> dict:
        t = {"channel": channel, "hypothesis": hypothesis, "design": design}
        self.tests.append(t)
        return {"recorded": t}

    def write_memo(self, headline: str, flag_verdicts: list, memo_markdown: str, overall_confidence: str) -> dict:
        if overall_confidence not in CONFIDENCE:
            return {"error": f"overall_confidence must be one of {CONFIDENCE}"}
        known = {f["id"] for f in self.flags}
        missing = known - {v.get("flag_id") for v in flag_verdicts}
        if missing:
            return {"error": f"Give a verdict for every flag. Missing: {sorted(missing)}"}
        self.memo = {"headline": headline, "flag_verdicts": flag_verdicts,
                     "memo_markdown": memo_markdown, "overall_confidence": overall_confidence}
        return {"done": True}

    # ---------- dispatch ----------

    def call(self, name: str, args: dict) -> dict:
        fn = getattr(self, name, None)
        if name not in {t["name"] for t in TOOLS} or fn is None:
            return {"error": f"Unknown tool {name}"}
        try:
            return fn(**args)
        except TypeError as e:
            return {"error": f"Bad arguments for {name}: {e}"}


def _schema(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props, "required": required or []}


CH = {"type": "string", "enum": ["google_search", "meta", "linkedin", "email", "direct"]}
PAID_CH = {"type": "string", "enum": ["google_search", "meta", "linkedin", "email"]}
CONF = {"type": "string", "enum": CONFIDENCE}

TOOLS = [
    {"name": "review_last_run", "description": "Your previous run's moves, tests and headline, with each moved channel's numbers the week before and after. Call this first.", "input_schema": _schema({})},
    {"name": "get_overview", "description": "Each channel's last 7 days vs its prior 4-week weekly average: spend, reported conversions, revenue, CPA, ROAS.", "input_schema": _schema({})},
    {"name": "get_flags", "description": "Rule-based anomaly flags with evidence. Leads to investigate, not conclusions.", "input_schema": _schema({})},
    {"name": "drill_down", "description": "One channel's metrics by week or by day.", "input_schema": _schema({"channel": CH, "granularity": {"type": "string", "enum": ["week", "day"]}, "periods": {"type": "integer", "description": "How many recent weeks or days"}}, ["channel"])},
    {"name": "compare_attribution", "description": "Credit share per channel under five attribution models (first-touch, last-touch, linear, time-decay, Markov), where they disagree, and implied CPA under each.", "input_schema": _schema({})},
    {"name": "get_self_reported", "description": "Weekly share of answers to 'How did you hear about us?' from buyers who answered.", "input_schema": _schema({})},
    {"name": "get_ledger", "description": "Current daily budgets, anything staged this run, and the guardrails on changes.", "input_schema": _schema({})},
    {"name": "set_budget", "description": "Stage a new daily budget for one channel. Use 0 to pause. Calling again for the same channel replaces the earlier change.", "input_schema": _schema({"channel": PAID_CH, "daily_budget": {"type": "number"}, "reason": {"type": "string", "description": "Cite the numbers behind this move"}, "confidence": CONF}, ["channel", "daily_budget", "reason", "confidence"])},
    {"name": "recommend_test", "description": "Recommend an incrementality test: hold a channel back for part of the audience and measure what actually drops.", "input_schema": _schema({"channel": CH, "hypothesis": {"type": "string"}, "design": {"type": "string", "description": "Who is held out, for how long, what is measured"}}, ["channel", "hypothesis", "design"])},
    {"name": "write_memo", "description": "Finish the run. Give a verdict on every flag and the memo a growth lead would read.", "input_schema": _schema({
        "headline": {"type": "string", "description": "One sentence: the most important thing this week"},
        "flag_verdicts": {"type": "array", "items": _schema({"flag_id": {"type": "string"}, "verdict": {"type": "string", "enum": ["act", "dismiss", "watch"]}, "reason": {"type": "string"}}, ["flag_id", "verdict", "reason"])},
        "memo_markdown": {"type": "string"},
        "overall_confidence": CONF}, ["headline", "flag_verdicts", "memo_markdown", "overall_confidence"])},
]
