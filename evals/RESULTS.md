# Held-out eval results

**6 of 8 scenarios passed** (61 of 63 checks). Each scenario is a fresh synthetic account the agent was not built around, graded against what that scenario planted. One run per scenario.

## ❌ baseline_new_seed

Same kinds of problems as the demo, new random account.

Agent: LinkedIn spent $5,249 over 14 days with zero conversions and is paused; Meta CPA is up 2.2x so it is trimmed 25%; the direct surge tracks AI-assistant referrals, not paid. (medium confidence, 12 tool calls)

- ✅ cut meta (costs rose)
- ✅ paused linkedin (no results)
- ✅ left healthy google_search alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ didn't act on the false alarm
- ✅ explained the AI-driven buyers
- ✅ didn't hand that credit to Google
- ❌ spotted email's missing credit
- ✅ reviewed last week first

## ✅ subtler_cost_spike

Meta's CPA rises about 1.5x instead of 2x, right at the flag threshold.

Agent: LinkedIn spent $5,417 over 14 days with zero conversions and is paused; Meta CPA is up about 50% and trimmed 15%; direct growth looks AI-driven, not paid. (medium confidence, 13 tool calls)

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

Agent: Meta spent $8,082 over 14 days with zero conversions, so I paused it. Direct growth lines up with AI-assistant mentions, not paid spend. (medium confidence, 13 tool calls)

- ❌ cut google_search (costs rose)
- ✅ paused meta (no results)
- ✅ left healthy linkedin alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ explained the AI-driven buyers
- ✅ didn't hand that credit to Google
- ✅ spotted email's missing credit
- ✅ reviewed last week first

## ✅ healthy_account

Nothing is wrong. Email is fairly credited and AI-driven buying is minimal. The right move is restraint.

Agent: No budget moves this week: LinkedIn CPA is up but sits above the 1.5 ROAS target under 4 of 5 attribution models, so I'm testing it rather than cutting. (medium confidence, 11 tool calls)

- ✅ left healthy google_search alone (no cut over 25%)
- ✅ left healthy meta alone (no cut over 25%)
- ✅ left healthy linkedin alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ reviewed last week first

## ✅ dark_funnel_heavy

No paid-channel problems, but AI-assisted buyers grow from 20% to 60%.

Agent: Direct conversions jumped 3.6x on flat spend alongside a rise in AI-assistant self-reports, so no paid channel should get the credit and no budgets move this week. (medium confidence, 11 tool calls)

- ✅ left healthy google_search alone (no cut over 25%)
- ✅ left healthy meta alone (no cut over 25%)
- ✅ left healthy linkedin alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ explained the AI-driven buyers
- ✅ didn't hand that credit to Google
- ✅ spotted email's missing credit
- ✅ reviewed last week first

## ✅ false_alarm_only

Only the harmless Google spend spike. Nothing to cut.

Agent: No budget moves this week: no channel shows a sustained efficiency drop, and LinkedIn, the weakest channel, is above the 1.5 ROAS target under 4 of 5 attribution models, so it gets a test instead of a cut. (medium confidence, 11 tool calls)

- ✅ left healthy google_search alone (no cut over 25%)
- ✅ left healthy meta alone (no cut over 25%)
- ✅ left healthy linkedin alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ didn't act on the false alarm
- ✅ spotted email's missing credit
- ✅ reviewed last week first

## ✅ unseen_cost_spike_linkedin

Added in v2. LinkedIn's costs rise about 2x; Meta and the rest are fine.

Agent: Direct conversions are up about 6x (about 10 to 62-66 per week) with no spend change, and self-reports point to AI assistants, so no paid channel should get credit; LinkedIn CPA is up 45% and is trimmed 20%. (medium confidence, 11 tool calls)

- ✅ cut linkedin (costs rose)
- ✅ left healthy google_search alone (no cut over 25%)
- ✅ left healthy meta alone (no cut over 25%)
- ✅ left healthy email alone (no cut over 25%)
- ✅ didn't act on the false alarm
- ✅ explained the AI-driven buyers
- ✅ didn't hand that credit to Google
- ✅ spotted email's missing credit
- ✅ reviewed last week first

## ✅ unseen_email_goes_dark

Added in v2. Email stops converting for two weeks; moderate AI-driven buying; no other problems.

Agent: Email spent $752 over 15 days with zero conversions, so I paused it. Direct's lift is untracked demand that looks AI-driven, and I left budgets alone. (medium confidence, 12 tool calls)

- ✅ paused email (no results)
- ✅ left healthy google_search alone (no cut over 25%)
- ✅ left healthy meta alone (no cut over 25%)
- ✅ left healthy linkedin alone (no cut over 25%)
- ✅ explained the AI-driven buyers
- ✅ didn't hand that credit to Google
- ✅ spotted email's missing credit
- ✅ reviewed last week first
