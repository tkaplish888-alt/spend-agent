"""Week 1 entry point: load data, compute metrics, flag anomalies.

    python run.py              # analyze (generates demo data on first run)
    python run.py --regenerate # rebuild the demo account from the seed first

The agent loop (week 2) will call the same functions as tools.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import yaml

from analysis import anomalies, metrics
from sources import get_source

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"
ICON = {"critical": "!!", "warning": "! ", "review": "? "}


def load_config() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text())


def main() -> list[dict]:
    p = argparse.ArgumentParser()
    p.add_argument("--regenerate", action="store_true")
    args = p.parse_args()

    cfg = load_config()
    if args.regenerate and DATA.exists():
        shutil.rmtree(DATA)

    data = get_source(cfg, DATA).load()
    daily_m = metrics.daily_metrics(data.daily)
    weekly_m = metrics.weekly_metrics(data.daily)
    flags = anomalies.run_all(data, cfg)

    OUT.mkdir(exist_ok=True)
    daily_m.to_csv(OUT / "metrics_daily.csv", index=False)
    weekly_m.to_csv(OUT / "metrics_weekly.csv", index=False)
    (OUT / "flags.json").write_text(json.dumps(flags, indent=2))

    print(f"\nSpend Agent · {data.meta['label']} · {data.meta['start']} to {data.meta['end']}\n")
    print("Last 7 days by channel")
    print(metrics.summary(data.daily).to_string(index=False))
    print(f"\n{len(flags)} flags")
    for f in flags:
        print(f"  {ICON[f['severity']]} {f['id']} [{f['severity']}] {f['message']}")
    print()
    return flags


if __name__ == "__main__":
    main()
