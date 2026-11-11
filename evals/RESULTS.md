# Held-out eval results

**3 of 6 scenarios passed** (40 of 46 checks). Each scenario is a fresh synthetic account the agent was not built around, graded against what that scenario planted. One run per scenario.

## ✅ baseline_new_seed

Same kinds of problems as the demo, new random account.

Agent: LinkedIn spent $5,249 over 14 days with zero conversions and is paused; Meta CPA is up 2.4x and is cut 30%; the direct surge looks AI-driven, not paid-driven. (medium confidence, 13 tool calls)

- ✅ cut meta (costs rose)
- ✅ paused linkedin (no results)
- ✅ left healthy google_search alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ didn't act on the false alarm
- ✅ explained the AI-driven buyers
- ✅ didn't hand that credit to Google
- ✅ spotted email's missing credit
- ✅ reviewed last week first

## ✅ subtler_cost_spike

Meta's CPA rises about 1.5x instead of 2x, right at the flag threshold.

Agent: LinkedIn spent $5,417 in 14 days with zero conversions, so I paused it. Meta's CPA is up 50%, so I trimmed it. The direct-traffic surge looks AI-driven, not paid. (medium confidence, 14 tool calls)

- ✅ cut meta (costs rose)
- ✅ paused linkedin (no results)
- ✅ left healthy google_search alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ didn't act on the false alarm
- ✅ explained the AI-driven buyers
- ✅ didn't hand that credit to Google
- ✅ spotted email's missing credit
- ✅ reviewed last week first

## ❌ problems_swapped

Costs spike on Google Search and Meta stops converting. Nothing wrong with LinkedIn.

Agent: Meta spent $8,082 over 14 days with zero conversions, so I paused it. Direct's 2.4x rise lines up with AI-assistant mentions, not paid spend. (medium confidence, 13 tool calls)

- ❌ cut google_search (costs rose)
- ✅ paused meta (no results)
- ❌ left healthy linkedin alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ explained the AI-driven buyers
- ✅ didn't hand that credit to Google
- ❌ spotted email's missing credit
- ✅ reviewed last week first

## ✅ healthy_account

Nothing is wrong. Email is fairly credited and AI-driven buying is minimal. The right move is restraint.

Agent: LinkedIn is the one clear underperformer (ROAS 0.87, CPA $267), so I cut its budget 25%. Google Search's true value is unsettled, so I'm recommending a holdout test instead of moving its budget. (medium confidence, 11 tool calls)

- ✅ left healthy google_search alone (no cut over 25%)
- ✅ left healthy meta alone (no cut over 25%)
- ✅ left healthy linkedin alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ reviewed last week first

## ❌ dark_funnel_heavy

No paid-channel problems, but AI-assisted buyers grow from 20% to 60%.

Agent: Direct conversions jumped 3.6x with flat paid spend and AI-sourced self-reports doubled, so the lift is untracked AI-driven demand and no paid channel should be credited or scaled; LinkedIn cut 33%. (medium confidence, 14 tool calls)

- ✅ left healthy google_search alone (no cut over 25%)
- ✅ left healthy meta alone (no cut over 25%)
- ❌ left healthy linkedin alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ explained the AI-driven buyers
- ✅ didn't hand that credit to Google
- ✅ spotted email's missing credit
- ✅ reviewed last week first

## ❌ false_alarm_only

Only the harmless Google spend spike. Nothing to cut.

Agent: Cut LinkedIn 33% ($300 to $200/day) because every model shows it is the costliest channel at about $139 CPA, and test Google search incrementality before moving its budget. (medium confidence, 12 tool calls)

- ✅ left healthy google_search alone (no cut over 25%)
- ✅ left healthy meta alone (no cut over 25%)
- ❌ left healthy linkedin alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ didn't act on the false alarm
- ❌ spotted email's missing credit
- ✅ reviewed last week first
