Build a single-page dashboard called **Ad Spend Agent**. It shows what an autonomous AI marketing agent did this week on a demo ad account. It reads everything from one JSON file I'm attaching (dashboard.json). Save it as `src/data/dashboard.json` and import it. Do not invent or hardcode any numbers; every figure comes from that file. No backend, no database, no login.

WHO IT'S FOR
Founders and growth leads who glance at it for two minutes. Plain language, no jargon without a one-line explanation.

TOP OF PAGE
- Title "Ad Spend Agent", subtitle: "An AI agent that manages a weekly ad budget, checks its own work, and admits what it can't see."
- A small pill showing `label` ("Synthetic data...") so it's always clear this is a demo.
- The `run.headline` as a large sentence, with run number, `run.data_end` and a confidence badge from `run.confidence`.

SECTIONS, IN THIS ORDER
1. **What the agent did.** Cards for each channel in `budgets`: starting daily budget, current daily budget, and the change (e.g. "LinkedIn $450 → $0, paused"). Below, a simple timeline from `moves_history`: each run, each move, its `reason` and `confidence`. If a run has no moves, show "Held steady: no changes."
2. **What it noticed.** One row per item in `flags`: `message`, plus a verdict badge from `verdict` (act / watch / dismiss) and `verdict_reason` in an expandable line.
3. **Who gets the credit?** A grouped bar chart from `attribution.credit_share` (channels on the x-axis, one bar per model, colors per model), plus a "Truth" bar from `attribution.true_share`. Use `channel_names` and `model_names` for labels. One-line explainer: "Five common rules for splitting credit for a sale. Where they disagree, nobody really knows that channel's value."
4. **The dark funnel slider.** A slider over `dark_funnel_scenarios` (agent_share 0% to 60%), labeled "Share of buyers who research through AI assistants". For the selected step show:
   - Google Search: credit under Last-touch vs its true share (two big numbers, the gap highlighted).
   - "Last-touch gets X% of the credit wrong" from `misallocated.last_touch`.
   - A small bar list of all five models' `misallocated` values.
   Explainer: "These buyers leave no clicks. As they grow, click-based credit keeps flowing to whatever caught the last click."
5. **How it thought.** A numbered vertical timeline from `trace`: each step's `label`, with the tool `input` shown small if not empty.
6. **The memo.** Render `memo_markdown` as formatted markdown in a readable card.
7. **Scorecard.** From `scorecard.checks`, a checklist with green checks or red crosses, with friendly names (e.g. p2_linkedin_paused → "Paused the channel spending with no results"). Footnote with `scorecard.note`.

STYLE
Calm, editorial, a little playful. Off-white background, deep ink text, one accent color (warm coral) used sparingly for the agent's actions. Rounded cards, generous spacing, clean sans-serif. Fully responsive; on mobile, sections stack and the chart scrolls horizontally. Footer: "Built by Tonishqa Kaplish · Synthetic data · tonishqakaplish.com".
