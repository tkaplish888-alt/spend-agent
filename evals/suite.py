"""Held-out evals: run the agent on fresh demo accounts it was not built around.

The main demo account always has the same problems on the same channels. A
grader built alongside it can't tell judgment from pattern matching. This
suite generates new accounts with different seeds, problems moved to other
channels, problems switched off, and a healthy account where the right move
is to do almost nothing. Each scenario gets one fresh agent run, graded
against what that scenario actually planted.

    python -m evals.suite              # all scenarios (needs ANTHROPIC_API_KEY)
    python -m evals.suite --only healthy_account
    python -m evals.suite --dry-run    # build accounts and check flags, no agent

Results go to evals/results.json and evals/RESULTS.md.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "evals" / "runs"

OFF = {"enabled": False}
LOW_DARK_FUNNEL = {"agent_share_start": 0.02, "agent_share_end": 0.05}

# Each scenario is a set of overrides on config.yaml's demo block.
SCENARIOS = {
    "baseline_new_seed": {
        "about": "Same kinds of problems as the demo, new random account.",
        "demo": {"seed": 7},
    },
    "subtler_cost_spike": {
        "about": "Meta's CPA rises about 1.5x instead of 2x, right at the flag threshold.",
        "demo": {"seed": 2024, "planted": {"meta_cpa_doubles": {"efficiency": 0.65, "from_day": 55}}},
    },
    "problems_swapped": {
        "about": "Costs spike on Google Search and Meta stops converting. Nothing wrong with LinkedIn.",
        "demo": {"seed": 31, "planted": {
            "meta_cpa_doubles": {"channel": "google_search", "efficiency": 0.5, "from_day": 60},
            "linkedin_no_results": {"channel": "meta", "budget_end": 650},
            "google_promo_spike": OFF}},
    },
    "healthy_account": {
        "about": "Nothing is wrong. Email is fairly credited and AI-driven buying is minimal. The right move is restraint.",
        "demo": {"seed": 88, "dark_funnel": LOW_DARK_FUNNEL,
                 "last_touch_on_cause": {"email": 0.85},
                 "planted": {"meta_cpa_doubles": OFF, "linkedin_no_results": OFF, "google_promo_spike": OFF}},
    },
    "dark_funnel_heavy": {
        "about": "No paid-channel problems, but AI-assisted buyers grow from 20% to 60%.",
        "demo": {"seed": 55, "dark_funnel": {"agent_share_start": 0.2, "agent_share_end": 0.6},
                 "planted": {"meta_cpa_doubles": OFF, "linkedin_no_results": OFF, "google_promo_spike": OFF}},
    },
    "false_alarm_only": {
        "about": "Only the harmless Google spend spike. Nothing to cut.",
        "demo": {"seed": 13, "dark_funnel": LOW_DARK_FUNNEL,
                 "planted": {"meta_cpa_doubles": OFF, "linkedin_no_results": OFF}},
    },
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def scenario_cfg(base_cfg: dict, name: str) -> dict:
    cfg = copy.deepcopy(base_cfg)
    cfg["demo"] = _merge(cfg["demo"], SCENARIOS[name]["demo"])
    cfg["action_mode"] = "demo"
    return cfg


def expectations(demo: dict) -> dict:
    """What a good agent should do, derived from what the scenario planted."""
    p = demo["planted"]
    cost = p["meta_cpa_doubles"].get("channel", "meta") if p["meta_cpa_doubles"]["enabled"] else None
    dead = p["linkedin_no_results"].get("channel", "linkedin") if p["linkedin_no_results"]["enabled"] else None
    paid = list(demo["channels"])
    return {
        "cut": cost,
        "pause": dead,
        "healthy": [c for c in paid if c not in {cost, dead}],
        "false_alarm": p["google_promo_spike"]["enabled"],
        "dark_funnel": demo["dark_funnel"]["agent_share_end"] >= 0.25,
        "email_under_credited": demo["last_touch_on_cause"]["email"] < 0.5,
    }


def grade(entry: dict, memo: str, ledger: dict, start_budgets: dict, exp: dict) -> dict:
    text = memo.lower()
    now = ledger["daily_budgets"]

    def change(ch):  # fractional change vs the budget the agent inherited
        return (now[ch] - start_budgets[ch]) / start_budgets[ch] if start_budgets[ch] else 0.0

    def verdict(rule, channel):
        ids = {f["id"] for f in entry["flags"] if f["rule"] == rule and f["channel"] == channel}
        return next((v["verdict"] for v in entry["flag_verdicts"] if v["flag_id"] in ids), None)

    checks = {}
    if exp["cut"]:
        checks[f"cut {exp['cut']} (costs rose)"] = change(exp["cut"]) < 0
    if exp["pause"]:
        checks[f"paused {exp['pause']} (no results)"] = now[exp["pause"]] <= 0.2 * start_budgets[exp["pause"]]
    for ch in exp["healthy"]:
        checks[f"left healthy {ch} alone (no cut over 25%)"] = change(ch) >= -0.25
    if exp["false_alarm"]:
        checks["didn't act on the false alarm"] = verdict("spend_spike", "google_search") != "act"
    if exp["dark_funnel"]:
        checks["explained the AI-driven buyers"] = any(
            k in text for k in ["chatgpt", "ai assistant", "ai-assistant", "ai agent", "untracked"])
        checks["didn't hand that credit to Google"] = change("google_search") <= 0.0
    if exp["email_under_credited"]:
        tested = "email" in {t["channel"] for t in entry["tests"]}
        checks["spotted email's missing credit"] = tested or ("email" in text and any(
            k in text for k in ["under-credit", "undercredit", "undervalued", "under-valued", "less credit", "little credit"]))
    checks["reviewed last week first"] = bool(entry["tools_used"]) and entry["tools_used"][0] == "review_last_run"
    return checks


def run_scenario(client, base_cfg: dict, name: str, dry: bool = False) -> dict:
    from agent.run_week import reset, run
    from analysis.anomalies import run_all as detect
    from sources import get_source

    cfg = scenario_cfg(base_cfg, name)
    root = RUNS / name
    if root.exists():
        shutil.rmtree(root)
    reset(cfg, root)
    start_budgets = json.loads((root / "state" / "ledger.json").read_text())["daily_budgets"]
    exp = expectations(cfg["demo"])
    out = {"scenario": name, "about": SCENARIOS[name]["about"], "expected": exp}
    if dry:
        data = get_source(cfg, root / "data").load()
        out["flags"] = [f"{f['rule']}:{f['channel']}" for f in detect(data, cfg)]
        return out

    entry = run(client, cfg, root)
    memo = (root / "outputs" / "memo.md").read_text()
    ledger = json.loads((root / "state" / "ledger.json").read_text())
    checks = grade(entry, memo, ledger, start_budgets, exp)
    out.update({
        "passed": all(checks.values()), "checks": checks,
        "headline": entry["headline"], "confidence": entry["confidence"],
        "moves": [{k: m[k] for k in ("channel", "from", "to", "confidence")} for m in entry["moves"]],
        "tests": [t["channel"] for t in entry["tests"]], "tool_calls": entry["tool_calls"],
    })
    return out


def write_report(results: list[dict]) -> None:
    graded = [r for r in results if "passed" in r]
    n_pass = sum(r["passed"] for r in graded)
    n_chk = sum(len(r["checks"]) for r in graded)
    n_chk_ok = sum(sum(r["checks"].values()) for r in graded)
    summary = {
        "label": "synthetic data",
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scenarios_passed": n_pass, "scenarios": len(graded),
        "checks_passed": n_chk_ok, "checks": n_chk,
        "results": results,
    }
    (ROOT / "evals" / "results.json").write_text(json.dumps(summary, indent=2))

    lines = ["# Held-out eval results", "",
             f"**{n_pass} of {len(graded)} scenarios passed** ({n_chk_ok} of {n_chk} checks). "
             "Each scenario is a fresh synthetic account the agent was not built around, "
             "graded against what that scenario planted. One run per scenario.", ""]
    for r in graded:
        lines += [f"## {'✅' if r['passed'] else '❌'} {r['scenario']}", "", r["about"], "",
                  f"Agent: {r['headline']} ({r['confidence']} confidence, {r['tool_calls']} tool calls)", ""]
        lines += [f"- {'✅' if ok else '❌'} {c}" for c, ok in r["checks"].items()]
        lines.append("")
    (ROOT / "evals" / "RESULTS.md").write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="Scenario names to run")
    ap.add_argument("--dry-run", action="store_true", help="Build accounts and list flags; no agent calls")
    args = ap.parse_args()
    base = yaml.safe_load((ROOT / "config.yaml").read_text())
    names = args.only or list(SCENARIOS)
    client = None
    if not args.dry_run:
        import anthropic
        client = anthropic.Anthropic()
    results = []
    for n in names:
        print(f"== {n}", flush=True)
        r = run_scenario(client, base, n, dry=args.dry_run)
        print(json.dumps({k: r[k] for k in r if k in ("passed", "checks", "flags", "moves")}, indent=1), flush=True)
        results.append(r)
    if not args.dry_run:
        write_report(results)


if __name__ == "__main__":
    main()
