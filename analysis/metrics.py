"""Spend, conversions, CPA and ROAS per channel, daily and weekly.

CPA (cost per acquisition) = spend / conversions.
ROAS (return on ad spend) = revenue / spend.
Both use platform-reported (last-touch) conversions, which is exactly why
they can mislead. Attribution models in week 2 correct for that.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _ratios(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    paid = (df["conversions"] > 0) & (df["spend"] > 0)
    df["cpa"] = np.where(paid, df["spend"] / df["conversions"].replace(0, np.nan), np.nan)
    df["roas"] = np.where(df["spend"] > 0, df["revenue"] / df["spend"].replace(0, np.nan), np.nan)
    return df.round({"spend": 2, "revenue": 2, "cpa": 2, "roas": 2})


def daily_metrics(daily: pd.DataFrame) -> pd.DataFrame:
    return _ratios(daily.sort_values(["channel", "date"]))


def weekly_metrics(daily: pd.DataFrame) -> pd.DataFrame:
    d = daily.copy()
    d["week_start"] = d["date"] - pd.to_timedelta(d["date"].dt.weekday, unit="D")
    w = d.groupby(["channel", "week_start"], as_index=False)[["spend", "conversions", "revenue"]].sum()
    return _ratios(w)


def summary(daily: pd.DataFrame, last_days: int = 7) -> pd.DataFrame:
    """Each channel's totals over the most recent window."""
    end = daily["date"].max()
    recent = daily[daily["date"] > end - pd.Timedelta(days=last_days)]
    s = recent.groupby("channel", as_index=False)[["spend", "conversions", "revenue"]].sum()
    return _ratios(s)
