"""One weekly run, start to finish.

1. Wake: called by the scheduler (or by hand).
2. If demo mode and this is not the first run, simulate the week that just
   passed under the budgets in state/ledger.json. Real mode skips this; the
   data source simply has a new week of data.
3. Recall, investigate, act: the agentic loop.
4. Record: apply staged moves to the ledger (demo) or write proposals (real),
   append to the agent log, write memo, trace and page data to outputs/.

    python -m agent.run_week            # one run
    python -m agent.run_week --reset    # wipe state and regenerate the demo account first
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from analysis import attribution
from sources import get_source
from sources.demo_generator import advance_week, generate_history

from .loop import run_loop
from .tools import ToolBox

ROOT = Path(__file__).resolve().parents[1]


def _paths(root: Path):
    return root / "data", root / "state", root / "outputs"


def _read(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def reset(cfg: dict, root: Path = ROOT) -> None:
    DATA, STATE, _ = _paths(root)
    STATE.mkdir(parents=True, exist_ok=True)
    if DATA.exists():
        shutil.rmtree(DATA)
    generate_history(cfg["demo"], DATA)
    budgets = {ch: c["budget"] for ch, c in cfg["demo"]["channels"].items()}
    li = cfg["demo"]["planted"]["linkedin_no_results"]
    if li["enabled"]:
        budgets[li.get("channel", "linkedin")] = li["budget_end"]
    (STATE / "ledger.json").write_text(json.dumps(
        {"label": "synthetic data", "mode": cfg["action_mode"], "week": 0,
         "daily_budgets": budgets, "history": []}, indent=2))
    (STATE / "agent_log.json").write_text("[]\n")


def run(client, cfg: dict, root: Path = ROOT) -> dict:
    DATA, STATE, OUT = _paths(root)
    ledger = _read(STATE / "ledger.json", None)
    log = _read(STATE / "agent_log.json", [])
    if ledger is None:
        reset(cfg, root)
        ledger, log = _read(STATE / "ledger.json", None), []

    if cfg["action_mode"] == "demo" and log:
        advance_week(cfg["demo"], ledger["daily_budgets"], DATA, week=len(log))

    data = get_source(cfg, DATA).load()
    box = ToolBox(data=data, cfg=cfg, ledger=ledger, log=log)
    run_no = len(log) + 1
    kickoff = (f"Weekly run {run_no}. Data covers {data.meta['start']} to {data.meta['end']}. "
               f"Mode: {cfg['action_mode']}. Begin.")
    trace = run_loop(client, box, cfg["agent"]["model"], cfg["agent"]["max_tool_calls"], kickoff)

    moves = list(box.staged.values())
    applied = cfg["action_mode"] == "demo"
    if applied:
        for mv in moves:
            ledger["daily_budgets"][mv["channel"]] = mv["to"]
        ledger["week"] = run_no
        ledger["history"].append({"run": run_no, "data_end": data.meta["end"], "moves": moves})
        (STATE / "ledger.json").write_text(json.dumps(ledger, indent=2))

    entry = {
        "run": run_no, "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_end": data.meta["end"], "headline": box.memo["headline"],
        "confidence": box.memo["overall_confidence"],
        "moves": [{**m, "applied": applied} for m in moves], "tests": box.tests,
        "flag_verdicts": box.memo["flag_verdicts"], "flags": box.flags,
        "tool_calls": len(trace), "tools_used": [t["tool"] for t in trace],
    }
    log.append(entry)
    (STATE / "agent_log.json").write_text(json.dumps(log, indent=2))

    OUT.mkdir(exist_ok=True)
    (OUT / "memo.md").write_text(box.memo["memo_markdown"])
    # Keep every run's memo and trace, not just the latest, for the Runs view.
    archive = OUT / "runs" / f"run_{run_no}"
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "memo.md").write_text(box.memo["memo_markdown"])
    (archive / "trace.json").write_text(json.dumps(trace, indent=2, default=str))
    (OUT / "trace.json").write_text(json.dumps(trace, indent=2, default=str))
    (OUT / "flags.json").write_text(json.dumps(box.flags, indent=2))
    credit = box.credit
    (OUT / "attribution.json").write_text(json.dumps({
        "credit_share": json.loads((credit / credit.sum()).round(4).to_json(orient="index")),
        "disagreement": json.loads(attribution.disagreement(credit).to_json(orient="index")),
    }, indent=2))
    (OUT / "run.json").write_text(json.dumps({**entry, "label": "synthetic data",
                                              "data_range": [data.meta["start"], data.meta["end"]],
                                              "budgets_after": ledger["daily_budgets"]}, indent=2))
    if not applied:
        (OUT / "proposals.json").write_text(json.dumps(moves, indent=2))
    return entry


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true", help="Wipe state and regenerate the demo account")
    args = p.parse_args()
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    if args.reset:
        reset(cfg)

    import anthropic
    entry = run(anthropic.Anthropic(), cfg)
    print(f"Run {entry['run']}: {entry['headline']}")
    print(f"  {entry['tool_calls']} tool calls · confidence {entry['confidence']}")
    for m in entry["moves"]:
        print(f"  move: {m['channel']} {m['from']:.0f} -> {m['to']:.0f}/day ({m['confidence']})")
    for t in entry["tests"]:
        print(f"  test: {t['channel']} · {t['hypothesis']}")
    print("  memo: outputs/memo.md · trace: outputs/trace.json")


if __name__ == "__main__":
    main()
