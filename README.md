# Ad Spend Agent

An autonomous AI agent for paid media. Every week it wakes itself up, checks whether last week's budget moves worked, investigates the account with its own tools, reallocates budget, and writes a memo with its full trace. A separate evaluation grades it against ground truth it never sees, including held-out scenarios it wasn't built around.

It's built for the **dark funnel**: more buyers now research in ChatGPT or through AI agents and arrive with no click trail. Click-based attribution then hands their credit to whatever caught the last click, usually branded search. The agent is designed to notice what it can't see and to test rather than guess.

> **Synthetic data.** Every number here is generated. Nothing describes a real ad account or how real buyer agents behave. Connecting a real account means writing one `DataSource` and changing `config.yaml`; the ad platform connectors themselves are not built yet.

## Results at a glance

- **Held-out evals, v1 → v2: 3 of 6 → 6 of 8 scenarios** (42/46 → 61/63 checks), including 2 scenarios added after v1 to check the fix generalizes. Details below and in [`evals/RESULTS.md`](evals/RESULTS.md).
- **Main demo account:** paused the channel spending with no results, trimmed the channel whose costs rose, attributed the direct-traffic surge to AI-assisted buyers instead of paid search, ignored the false alarm, then judged its own moves the following week.
- **Attribution benchmark:** last-click misattributes 44% of credit on the demo account; the best click-based model still misses about 23%, because AI-assisted buyers leave no clicks.

## How it works

1. **Data** (`sources/`): a `DataSource` interface with one method, `load()`. `DemoSource` builds a synthetic account: spend turns into conversions through a diminishing-returns response curve (conversions = max × spend ÷ (spend + k)), so the agent's budget moves change what it sees the next week.
2. **Analysis** (`analysis/`): CPA (spend ÷ conversions), ROAS (revenue ÷ spend), rule-based anomaly flags (leads, not verdicts), and five multi-touch attribution models: first-touch, last-touch, linear, time-decay and Markov (credit by how many sales you'd lose if a channel vanished).
3. **Agent** (`agent/`): Claude with 11 tools. It reviews last week first, investigates, stages budget changes, recommends incrementality tests (geo holdouts), and writes a memo with a verdict on every flag.
4. **Guardrails:** max 15 tool calls per run; no channel can rise more than 50% per run; a minimum ROAS target. In demo mode it moves a simulated ledger. In real-account mode every move becomes a proposal for a human (human-in-the-loop).
5. **Schedule:** GitHub Actions runs it every Monday and commits the memo, trace and ledger.

Tools: `review_last_run`, `get_overview`, `get_flags`, `get_trends`, `drill_down`, `compare_attribution`, `get_self_reported`, `get_ledger`, `set_budget`, `recommend_test`, `write_memo`.

## Evaluation

### Ground truth

The demo account's code decides what actually caused every sale, so it knows the truth no real company has. True causes live in `data/ground_truth.json`. The agent's tools never read it; only the graders do.

| Planted in the main demo account | What a good agent does |
| --- | --- |
| Meta's CPA doubles from day 60 | Trim Meta |
| LinkedIn spends for 14 days with zero conversions | Pause it |
| Email drives ~4x more sales than last-click credits | Flag the gap, test before scaling |
| AI-assisted buyers grow from 5% to 40%, landing as branded search or direct | Explain the lift, don't hand the credit to Google |
| Red herring: a one-week Google promo spike with steady CPA | Dismiss it |

### Held-out evals (`evals/`)

A grader written alongside one demo account can't tell judgment from pattern matching. So `evals/suite.py` generates fresh accounts the agent wasn't built around: new seeds, a subtler cost spike, problems moved to other channels, a healthy account where the right move is restraint, a heavy dark funnel, and a false alarm on its own. Each is graded against what that scenario planted.

**v1: 3 of 6 scenarios** ([`evals/v1/RESULTS.md`](evals/v1/RESULTS.md)). Two failure patterns:

1. It trimmed LinkedIn in three accounts because it was the least efficient channel, even though LinkedIn was still profitable (about $2 back per $1). It ranked channels instead of judging them against a target.
2. When costs rose on Google Search, the rule-based flags missed it (AI-assisted buyers searching the brand prop up Google's reported numbers). The agent noticed the decline but was too cautious to act.

**v2 changes:** a business target (keep a channel if it returns at least $1.50 per $1 under any reasonable attribution model), a `get_trends` tool so it checks every channel, not only flagged ones, and a rule to trim a channel whose costs rose 40%+ over three weeks and test it.

**v2: 6 of 8 scenarios** ([`evals/RESULTS.md`](evals/RESULTS.md)), including both scenarios added after v1. The LinkedIn over-trimming is gone. Still failing:

1. **Swapped problems:** Google's reported CPA rose 30%, under the 40% trigger, and its ROAS stayed far above target, so the agent set a tripwire and a test instead of trimming. Defensible on the numbers it could see, but its true cost per sale had roughly doubled.
2. **Email's missing credit:** in v2 it notes email's wide credit range but no longer calls out that last-click under-credits it. The profitability framing seems to have crowded this out. Next fix.

One run per scenario, so results carry run-to-run noise. Graders are rule-based; when a check failed on wording rather than substance, the check was fixed and saved runs re-scored without new agent calls (`--regrade`).

### Attribution benchmark (main demo account)

| Model | Credit in the wrong place |
| --- | --- |
| First-touch | 23% |
| Markov | 24% |
| Linear | 29% |
| Time-decay | 34% |
| Last-touch (what ad platforms report) | 44% |

No model reaches zero, because ground truth includes AI-assisted buyers that no click-based model can see. That gap is why the agent treats model disagreement as uncertainty and recommends tests.

## Run it

On GitHub: add `ANTHROPIC_API_KEY` as a repository secret. **Weekly run** runs every Monday (tick "reset" to start the demo account over). **Held-out evals** runs the scenario suite on demand.

Locally:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
python -m agent.run_week --reset   # fresh demo account, first run
python -m agent.run_week           # the simulated week moves on under its budgets, then it runs again
python -m agent.evaluate           # score the main account against ground truth
python -m evals.suite              # held-out scenarios (one agent run each)
python -m evals.suite --dry-run    # build the scenario accounts and list their flags, no agent
python -m pytest tests/            # offline tests, no API key needed
python site/export.py              # bundle outputs into site/dashboard.json for the dashboard
```

## Connecting real data

Write a class in `sources/` that implements `load()` and returns the same `SpendData` columns as `DemoSource`, then set `data_source` in `config.yaml` and `action_mode: real`. In real-account mode the ground-truth evaluation doesn't exist; the held-out suite becomes the regression test before changing the agent, and incrementality tests become the real-world scorecard.

Built by [Tonishqa Kaplish](https://tonishqakaplish.com).
