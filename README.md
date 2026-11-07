# Spend Agent

An autonomous weekly agent for paid media. It wakes itself up, checks whether last week's budget moves worked, investigates the account with its own tools, moves budget, and writes a memo with its full trace.

It's built for the dark funnel: more buyers now research inside ChatGPT or through an AI agent and arrive with no click trail. Click-based attribution then hands credit to whatever caught the last click. Spend Agent is designed to notice what it can't see.

> **Runs on synthetic data.** Every number in this repo is generated. It makes no claim about any real account or about how real buyer agents behave. Plug in your own data by editing `config.yaml` and writing one `DataSource`.

## Status

| Week | What | State |
| --- | --- | --- |
| 1 | Responsive demo account, metrics, anomaly flags | Done |
| 2 | Attribution models, tools, the autonomous loop, memo | Next |
| 3 | Weekly schedule, page, portfolio card | Planned |

## Run it

```bash
pip install -r requirements.txt
python run.py --regenerate   # build the demo account from the seed, then analyze
python -m pytest tests/      # the Week 1 gate
```

## How it fits together

1. `config.yaml` names the data source, channels, thresholds, dark funnel settings and action mode.
2. `sources/` holds the `DataSource` interface (one method, `load()`), `DemoSource`, and a documented `GoogleAdsSource` stub.
3. `sources/demo_generator.py` builds the synthetic account. Spend turns into conversions through a diminishing-returns response curve, so budgets in `state/ledger.json` shape the next simulated week.
4. `analysis/` computes CPA (spend ÷ conversions) and ROAS (revenue ÷ spend) per channel, and runs rule-based anomaly checks that hand the agent leads, not verdicts.
5. `agent/` is the loop (Week 2). `state/` holds its memory and the ledger.

## What's planted in the demo account

| # | Problem | What the agent should do |
| --- | --- | --- |
| 1 | Meta CPA doubles from day 60 | Flag the shift, pull budget |
| 2 | LinkedIn spend rises with zero conversions for 14 days | Flag the waste, pause it |
| 3 | Email drives ~4x more conversions than last-touch credits | Show the gap, recommend an incrementality test |
| 4 | Dark funnel: AI-assisted buyers climb from 5% to 40% of conversions, landing as branded search or direct | Notice the unexplained lift, cross-check self-reported answers, don't shift budget to search |
| — | Red herring: a one-week Google promo spike with steady CPA | Investigate, call it fine |

True causes live in `data/ground_truth.json` and `data/truth_conversions.csv`. The agent never loads them; they exist to score it.

## Connecting real data

Write a class in `sources/` that implements `load()` and returns the same `SpendData` columns as `DemoSource`, then set `data_source` in `config.yaml`. Set `action_mode: real` so every budget move becomes a proposal for a human instead of a change.
