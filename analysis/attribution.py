"""Five attribution models: rules for splitting each sale's credit across
the channels the buyer touched.

- first_touch: all credit to the first tracked touch
- last_touch: all credit to the last tracked touch (what ad platforms report)
- linear: credit split evenly across every touch
- time_decay: later touches get more, halving for each step back
- markov: credit by removal effect, the share of conversions lost if that
  channel vanished from every journey (built on a transition matrix)

A conversion with no tracked touches goes to "direct". No model can see the
dark funnel: buyers who researched through an AI agent leave no touch, so
every model hands their credit to search or direct. That blind spot is the point.
"""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

MODELS = ["first_touch", "last_touch", "linear", "time_decay", "markov"]
DIRECT = "direct"


def paths(conversions: pd.DataFrame, journeys: pd.DataFrame) -> dict[str, list[str]]:
    """conversion_id -> ordered list of touched channels."""
    j = journeys.sort_values(["conversion_id", "step"])
    grouped = j.groupby("conversion_id")["channel"].apply(list).to_dict()
    return {cid: grouped.get(cid, []) for cid in conversions["conversion_id"]}


def _rule_based(p: dict[str, list[str]]) -> dict[str, dict[str, float]]:
    out = {m: defaultdict(float) for m in MODELS if m != "markov"}
    for path in p.values():
        if not path:
            for m in out:
                out[m][DIRECT] += 1
            continue
        out["first_touch"][path[0]] += 1
        out["last_touch"][path[-1]] += 1
        for ch in path:
            out["linear"][ch] += 1 / len(path)
        w = np.array([0.5 ** (len(path) - 1 - i) for i in range(len(path))])
        w /= w.sum()
        for ch, wi in zip(path, w):
            out["time_decay"][ch] += wi
    return out


def _markov(p: dict[str, list[str]], nulls: list[list[str]] | None = None) -> dict[str, float]:
    """First-order Markov removal effect.

    States: start, each channel, conv, null. Converting paths end in conv;
    non-converting paths (if a source supplies them) end in null. Removing a
    channel sends anyone who reaches it to null. Credit is each channel's
    removal effect, scaled so all credit sums to the conversion count.
    """
    seqs = [(path or [DIRECT]) + ["conv"] for path in p.values()]
    seqs += [path + ["null"] for path in (nulls or [])]
    channels = sorted({s for seq in seqs for s in seq} - {"conv", "null"})
    states = ["start"] + channels + ["conv", "null"]
    idx = {s: i for i, s in enumerate(states)}
    counts = np.zeros((len(states), len(states)))
    for seq in seqs:
        prev = "start"
        for s in seq:
            counts[idx[prev], idx[s]] += 1
            prev = s
    counts[idx["conv"], idx["conv"]] = counts[idx["null"], idx["null"]] = 1

    def p_conv(removed: str | None) -> float:
        c = counts.copy()
        if removed:
            r = idx[removed]
            c[:, idx["null"]] += c[:, r]
            c[:, r] = 0
            c[r, :] = 0
            c[r, idx["null"]] = 1
        rows = c.sum(axis=1, keepdims=True)
        rows[rows == 0] = 1
        T = c / rows
        transient = [idx["start"]] + [idx[ch] for ch in channels]
        Q = T[np.ix_(transient, transient)]
        R = T[np.ix_(transient, [idx["conv"]])]
        absorb = np.linalg.solve(np.eye(len(transient)) - Q, R)
        return float(absorb[0, 0])

    base = p_conv(None)
    effects = {ch: max(0.0, 1 - p_conv(ch) / base) if base else 0.0 for ch in channels}
    total = sum(effects.values()) or 1.0
    n = len(p)
    return {ch: n * e / total for ch, e in effects.items()}


def run_models(conversions: pd.DataFrame, journeys: pd.DataFrame) -> pd.DataFrame:
    """Credit per channel under each model. Rows: channel. Columns: models."""
    p = paths(conversions, journeys)
    credit = _rule_based(p)
    credit["markov"] = _markov(p)
    df = pd.DataFrame({m: pd.Series(credit[m]) for m in MODELS}).fillna(0.0)
    return df.round(1).sort_index()


def disagreement(credit: pd.DataFrame) -> pd.DataFrame:
    """How far the models are apart on each channel, as share of all sales."""
    share = credit / credit.sum()
    out = pd.DataFrame({
        "min_share": share.min(axis=1), "max_share": share.max(axis=1),
        "lowest_model": share.idxmin(axis=1), "highest_model": share.idxmax(axis=1),
    })
    out["spread"] = out["max_share"] - out["min_share"]
    return out.round(3).sort_values("spread", ascending=False)


def implied_cpa(credit: pd.DataFrame, spend: pd.Series) -> pd.DataFrame:
    """Cost per credited sale under each model (paid channels only)."""
    s = spend.reindex(credit.index).fillna(0)
    out = credit.apply(lambda col: np.where((col > 0) & (s > 0), s / col.replace(0, np.nan), np.nan))
    out.index = credit.index
    return out[s > 0].round(2)


def score_against_truth(credit: pd.DataFrame, truth_counts: dict[str, int]) -> pd.DataFrame:
    """Share of all credit each model put in the wrong place.

    Truth includes ai_agent, which no model can credit, so even a perfect
    click-based model scores above zero. Evaluation only: the agent never sees this.
    """
    keys = sorted(set(credit.index) | set(truth_counts))
    t = pd.Series({k: truth_counts.get(k, 0) for k in keys}, dtype=float)
    t = t / t.sum()
    rows = {}
    for m in credit.columns:
        c = credit[m].reindex(keys).fillna(0)
        c = c / c.sum()
        rows[m] = {"misallocated_share": round(float((c - t).abs().sum() / 2), 3),
                   **{f"err_{k}": round(float(c[k] - t[k]), 3) for k in keys}}
    return pd.DataFrame(rows).T.sort_values("misallocated_share")
