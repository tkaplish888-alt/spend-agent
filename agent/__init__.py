"""The autonomous loop. Built in week 2.

Each weekly run:
1. Wake: GitHub Actions starts the run; no human prompt.
2. Recall: read state/agent_log.json and judge last week's moves against what happened.
3. Investigate: Claude calls read-only tools (metrics, drill-downs, anomaly checks,
   attribution models, self-reported answers) and decides what to dig into, up to
   agent.max_tool_calls in config.yaml.
4. Act: in demo mode, write budget changes to state/ledger.json, which shapes next
   week's simulated data. In real mode, write proposals for a human instead.
5. Record: memo, flags, confidence and the full tool-call trace go to outputs/.
"""
