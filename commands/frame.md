---
description: Frame the current request explicitly — Goal, Observation, Hypothesis, Verification — and say what should happen next.
argument-hint: "[request, or empty to use the conversation so far]"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
---

Frame this request explicitly, and stop. Do not implement anything this turn.

Request: $ARGUMENTS
(If empty, frame what the conversation is currently pointed at.)

Load the `premise:problem-framing` skill and apply it. Then print exactly this,
with one short line per item:

- Goal:
- Observation:
- Hypothesis:
- Verification:
- Next: <READY | CLARIFY | INVESTIGATE | PROCEED_WITH_ASSUMPTIONS> — one line on why.

Leave an item as `—` if it is genuinely absent; do not invent one, and do not move
an asserted cause up into Observation to fill the gap. This command is the one
place the four categories are printed, because here the user asked for them.
