Build a single-page web app called **Ad Spend Agent**: a weekly review screen for supervising an autonomous AI agent that manages a demo ad budget. It is not a classic analytics dashboard. Lead with what the agent decided and why, then show evidence. Read everything from the attached dashboard.json, saved as `src/data/dashboard.json`. Never invent or hardcode numbers. No backend, no database, no login. Keep it to this one page.

AUDIENCE
Founders and growth leads reviewing the agent's week in two minutes. Plain language; define any jargon in one short line.

LAYOUT
Desktop: slim left sidebar plus main column. Mobile: sidebar becomes a simple top bar, everything stacks.

SIDEBAR (static, no interactions)
- "Ad Spend Agent" wordmark and one line: "An AI agent that manages a weekly ad budget, checks its own work, and admits what it can't see."
- A plain list of runs from `moves_history` (Run 1, Run 2…) with the latest highlighted. Not clickable.
- A muted note with `label` (synthetic data).
- Footer: "Built by Tonishqa Kaplish · tonishqakaplish.com"

MAIN COLUMN, IN THIS ORDER
1. **This week's decision.** `run.headline` as the page heading, with run number, `run.data_end`, and a confidence badge (`run.confidence`). Below it, one card per move in the latest run of `moves_history`: channel name, from → to daily budget, `reason`, `confidence`, and a small "Reversible" tag. If the latest run has no moves, show one card: "Held steady. No budget changes this week." Under the cards, one muted line: "Demo mode: the agent applies moves itself. In real mode, each move becomes an approval request."
2. **Did last week's moves work?** Render the "Last week's moves" section of `memo_markdown` (the text between "## Last week's moves" and the next "##") as its own card.
3. **Needs your attention.** Rows from `flags`, sorted act → watch → dismiss. Each row: `message`, a status badge (`verdict`), and an expandable `verdict_reason`. Dismissed flags are collapsed under "Dismissed (n)".
4. **Budgets.** A compact row of channel tiles: starting vs current daily budget (`budgets`), with the change shown as a delta.
5. **Evidence** (three tabs):
   - *Who gets the credit:* grouped bar chart from `attribution.credit_share` (one bar per model) plus a Truth bar from `attribution.true_share`. Use `channel_names` and `model_names`. "AI assistants (invisible)" has a Truth bar but no model bars; keep it visible, that gap is the point. Caption: "Five common rules for splitting credit for a sale. Where they disagree, nobody really knows a channel's value."
   - *What the agent can't see:* slider over `dark_funnel_scenarios` (0% to 60%), labeled "Share of buyers who research through AI assistants." Show Google Search's Last-touch credit vs its true share as two large numbers, "Last-touch gets X% of credit wrong" from `misallocated.last_touch`, and a small ranked list of all five models' `misallocated`. Caption: "These buyers leave no clicks, so click-based credit keeps flowing to whatever caught the last click."
   - *Recommended test:* cards from `tests` (channel, hypothesis, design).
6. **Run trace.** One collapsed line: "Took N steps:" followed by the step `label`s joined with arrows. Expanding it shows a numbered list with each `tool` name, and its `input` if not empty, in small monospace.
7. **The full memo.** Collapsed by default ("Read the full memo"); expands to render `memo_markdown` as a clean report.
8. **Scorecard.** Small checklist from `scorecard.checks` with friendly names (e.g. p2_linkedin_paused → "Paused the channel spending with no results"), green check or red cross, footnote `scorecard.note`.

Calm by default: only sections 1 to 3 are fully open. Everything else is compact or collapsed.

STYLE
Professional and calm, like Linear or Vercel's dashboard. Not whimsical, not a generic analytics template. White and light-gray surfaces, near-black text, one accent (deep indigo) for the agent's actions. Status colors only where meaningful: green = worked/done, amber = watch, gray = dismissed, red only for failures. Inter for text, a monospace font for numbers, money and tool names. Thin borders, subtle shadows, 8px radius, generous whitespace.
