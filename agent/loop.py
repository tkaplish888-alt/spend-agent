"""The agentic loop: Claude picks a tool, reads the result, decides the next
step, and repeats until it writes the memo or hits the step cap.
"""

from __future__ import annotations

import json
import time

from .tools import TOOLS, ToolBox

SYSTEM = """You are Spend Agent, an autonomous analyst for a paid media account. You run once a week with no human in the loop. Nobody will answer questions; decide for yourself.

Your job each run:
1. Start with review_last_run. If you made moves last week, judge whether they worked using the before/after numbers, and say so plainly.
2. Investigate. Use the tools to decide what is actually happening. Flags are leads, not verdicts: confirm or dismiss each with evidence. Do not call the same tool with the same arguments twice.
3. Act. Use set_budget for moves the evidence supports. Use recommend_test when the evidence cannot settle a question.
4. Finish with write_memo, giving a verdict on every flag.

How to judge:
- Reported conversions are last tracked click. A channel can look cheap because it catches the final click for buyers something else persuaded.
- When attribution models disagree sharply about a channel, its true value is unknown. Don't move budget toward or away from it on one model's say-so; recommend a test.
- Conversions with no tracked source that grow without a matching rise in spend mean something untracked is driving buyers. Cross-check self-reported answers before crediting any paid channel for it.
- A spend jump is only a problem if efficiency fell with it.
- Cutting waste is cheap to reverse; scaling on weak evidence is not. Prefer cuts and tests over big increases.

The memo (memo_markdown), under 350 words, for a growth lead to forward:
## Last week's moves (what you changed and whether it worked; "first run" if none)
## What's happening (each finding with its numbers)
## Moves (channel, from, to, why)
## Where the models disagree
## Test to run
## Confidence (overall, and what would change your mind)
Cite specific numbers for every claim. No vague lines like "performance is mixed". This account uses synthetic data; say so once at the top."""


def _block(b) -> dict:
    """SDK content block -> plain dict we can store and send back."""
    if b.type == "text":
        return {"type": "text", "text": b.text}
    if b.type == "tool_use":
        return {"type": "tool_use", "id": b.id, "name": b.name, "input": b.input}
    return {"type": b.type}


def run_loop(client, box: ToolBox, model: str, max_tool_calls: int, kickoff: str) -> list[dict]:
    """Run until write_memo succeeds. Returns the trace."""
    messages = [{"role": "user", "content": kickoff}]
    trace, calls = [], 0
    forced = False
    while box.memo is None:
        # No forced tool_choice: it isn't allowed alongside extended thinking.
        # Past the step cap we nudge in text and give it a few more turns.
        resp = client.messages.create(model=model, max_tokens=8000, system=SYSTEM,
                                      tools=TOOLS, messages=messages)
        # Send the assistant turn back exactly as returned. Thinking blocks carry
        # a signature the API checks, so they must not be rebuilt or stripped.
        messages.append({"role": "assistant", "content": resp.content})
        blocks = [_block(b) for b in resp.content]

        thought = " ".join(b["text"] for b in blocks if b["type"] == "text").strip()
        uses = [b for b in blocks if b["type"] == "tool_use"]
        if not uses:
            if forced:
                raise RuntimeError("Model did not write the memo when required.")
            messages.append({"role": "user", "content": "Keep going with your tools. Finish with write_memo."})
            continue

        results = []
        for u in uses:
            calls += 1
            t0 = time.time()
            out = box.call(u["name"], u["input"])
            text = json.dumps(out, default=str)
            trace.append({"step": calls, "tool": u["name"], "input": u["input"], "thought": thought,
                          "result_preview": text[:500], "ok": "error" not in out,
                          "ms": int((time.time() - t0) * 1000)})
            thought = ""
            results.append({"type": "tool_result", "tool_use_id": u["id"], "content": text})
        messages.append({"role": "user", "content": results})

        if box.memo is None and calls >= max_tool_calls and not forced:
            forced = True
            messages[-1]["content"].append(
                {"type": "text", "text": f"Step cap of {max_tool_calls} reached. Write the memo now with what you have."})
        if forced and calls > max_tool_calls + 3:
            raise RuntimeError("Model failed to write a valid memo after the step cap.")
    return trace
