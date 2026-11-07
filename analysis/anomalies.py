"""Rule-based anomaly checks: numbers that break their usual pattern.

Each rule returns flags with the evidence behind them. Severity:
- critical: money is clearly being wasted right now
- warning: a sustained change worth acting on
- review: something moved; the agent should investigate before deciding

The rules are deliberately simple. Their job is to hand the agent leads,
not verdicts; the agent decides what a flag means.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _series(daily: pd.DataFrame, channel: str) -> pd.DataFrame:
    return daily[daily["channel"] == channel].sort_values("date").reset_index(drop=True)


def cpa_level_shift(daily: pd.DataFrame, channels: list[str], ratio: float, min_days: int) -> list[dict]:
    """Find the split that best separates a cheaper past from a pricier present."""
    flags = []
    for ch in channels:
        s = _series(daily, ch)
        n = len(s)
        spend, conv = s["spend"].to_numpy(), s["conversions"].to_numpy()
        best = None
        for k in range(min_days, n - min_days + 1):
            cb, ca = conv[:k].sum(), conv[k:].sum()
            if cb == 0 or ca == 0:
                continue
            before, after = spend[:k].sum() / cb, spend[k:].sum() / ca
            r = after / before
            if best is None or r > best[0]:
                best = (r, k, before, after)
        if best and best[0] >= ratio:
            r, k, before, after = best
            start = s.loc[k, "date"].date().isoformat()
            flags.append({
                "rule": "cpa_level_shift", "channel": ch, "severity": "warning",
                "since": start,
                "evidence": {"cpa_before": round(before, 2), "cpa_after": round(after, 2),
                             "ratio": round(r, 2), "days_after": n - k},
                "message": f"{ch} CPA rose {r:.1f}x, from ${before:.0f} to ${after:.0f}, starting {start}.",
            })
    return flags


def spend_without_results(daily: pd.DataFrame, channels: list[str], min_days: int) -> list[dict]:
    """Spend still going out with zero conversions, up to the latest day."""
    flags = []
    for ch in channels:
        s = _series(daily, ch)
        streak = 0
        for _, row in s[::-1].iterrows():
            if row["spend"] > 0 and row["conversions"] == 0:
                streak += 1
            else:
                break
        if streak >= min_days:
            window = s.tail(streak)
            slope = float(np.polyfit(np.arange(streak), window["spend"].to_numpy(), 1)[0])
            start = window["date"].iloc[0].date().isoformat()
            flags.append({
                "rule": "spend_without_results", "channel": ch, "severity": "critical",
                "since": start,
                "evidence": {"days": streak, "spend": round(float(window["spend"].sum()), 2),
                             "daily_spend_trend": round(slope, 2)},
                "message": (f"{ch} spent ${window['spend'].sum():,.0f} over {streak} days with zero conversions"
                            + (", and spend is still rising." if slope > 0 else ".")),
            })
    return flags


def spend_spikes(daily: pd.DataFrame, channels: list[str], ratio: float, benign_cpa: float) -> list[dict]:
    """Days where spend jumps above its trailing median, judged by what CPA did."""
    flags = []
    for ch in channels:
        s = _series(daily, ch)
        med = s["spend"].rolling(14, min_periods=7).median().shift(1)
        hot = (s["spend"] > ratio * med).to_numpy()
        i = 0
        while i < len(s):
            if not hot[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(s) and hot[j + 1]:
                j += 1
            ep = s.iloc[i:j + 1]
            base = s.iloc[max(0, i - 28):i]
            cpa_ep = ep["spend"].sum() / max(ep["conversions"].sum(), 1)
            cpa_base = base["spend"].sum() / max(base["conversions"].sum(), 1)
            cpa_ratio = cpa_ep / cpa_base
            benign = cpa_ratio <= benign_cpa
            start, end = ep["date"].iloc[0].date().isoformat(), ep["date"].iloc[-1].date().isoformat()
            flags.append({
                "rule": "spend_spike", "channel": ch, "severity": "review" if benign else "warning",
                "since": start, "until": end,
                "evidence": {"days": len(ep), "spend_vs_median": round(float((ep["spend"] / med.iloc[i:j + 1]).mean()), 2),
                             "cpa_during": round(cpa_ep, 2), "cpa_before": round(cpa_base, 2),
                             "cpa_ratio": round(cpa_ratio, 2)},
                "message": (f"{ch} spend jumped for {len(ep)} days ({start} to {end}); CPA "
                            + (f"held at ${cpa_ep:.0f} vs ${cpa_base:.0f}. Likely fine, confirm before acting."
                               if benign else f"rose to ${cpa_ep:.0f} from ${cpa_base:.0f}.")),
            })
            i = j + 1
    return flags


def untracked_lift(daily: pd.DataFrame, conversions: pd.DataFrame, untracked: str,
                   ratio: float, early_days: int = 28, late_days: int = 21) -> list[dict]:
    """Conversions with no click source growing faster than anything explains."""
    start, end = daily["date"].min(), daily["date"].max()
    early_end = start + pd.Timedelta(days=early_days)
    late_start = end - pd.Timedelta(days=late_days - 1)

    def per_day(frame, lo, hi, col="conversions", ch=None):
        f = frame[(frame["date"] >= lo) & (frame["date"] <= hi)]
        if ch:
            f = f[f["channel"] == ch]
        return f[col].sum() / f["date"].nunique()

    d_early = per_day(daily, start, early_end - pd.Timedelta(days=1), ch=untracked)
    d_late = per_day(daily, late_start, end, ch=untracked)
    paid = daily[daily["channel"] != untracked]
    s_early = per_day(paid, start, early_end - pd.Timedelta(days=1), col="spend")
    s_late = per_day(paid, late_start, end, col="spend")

    sr = conversions.dropna(subset=["self_reported"])
    ai = sr["self_reported"].str.contains("ChatGPT|AI assistant", regex=True)
    ai_early = ai[sr["date"] < early_end].mean()
    ai_late = ai[sr["date"] >= late_start].mean()

    r = d_late / d_early if d_early else float("inf")
    if r < ratio:
        return []
    return [{
        "rule": "untracked_lift", "channel": untracked, "severity": "review",
        "since": late_start.date().isoformat(),
        "evidence": {"direct_per_day_early": round(d_early, 1), "direct_per_day_late": round(d_late, 1),
                     "ratio": round(r, 2), "paid_spend_ratio": round(s_late / s_early, 2),
                     "self_reported_ai_share_early": round(float(ai_early), 3),
                     "self_reported_ai_share_late": round(float(ai_late), 3)},
        "message": (f"Direct conversions grew {r:.1f}x ({d_early:.1f} to {d_late:.1f}/day) while paid spend "
                    f"moved {s_late / s_early:.2f}x. Self-reported AI answers went from "
                    f"{ai_early:.0%} to {ai_late:.0%}. Something untracked is driving buyers."),
    }]


def run_all(data, cfg: dict) -> list[dict]:
    a = cfg["anomalies"]
    paid = data.meta["paid_channels"]
    dead = spend_without_results(data.daily, paid, a["zero_result_days"])
    # A channel converting nothing already has its flag; a CPA shift on it is noise.
    live = [ch for ch in paid if ch not in {f["channel"] for f in dead}]
    flags = (
        dead
        + cpa_level_shift(data.daily, live, a["cpa_shift_ratio"], a["cpa_shift_min_days"])
        + spend_spikes(data.daily, paid, a["spend_spike_ratio"], a["spike_benign_cpa_ratio"])
        + untracked_lift(data.daily, data.conversions, data.meta["untracked_channel"], a["untracked_lift_ratio"])
    )
    order = {"critical": 0, "warning": 1, "review": 2}
    flags.sort(key=lambda f: order[f["severity"]])
    for i, f in enumerate(flags, 1):
        f["id"] = f"F{i}"
    return flags
