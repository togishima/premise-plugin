---
name: problem-framing
description: Full rubric for framing a request before implementing it — separating Goal, Observation, Hypothesis and Verification, and choosing between READY, CLARIFY, INVESTIGATE and PROCEED_WITH_ASSUMPTIONS. Use when a request's premise is unverified, its goal or success criterion is unclear, or an asserted cause ("X is the bottleneck", "it's a caching issue") would otherwise drive a code change. Do not use for requests that are already clear or trivial.
allowed-tools: Read, Grep, Glob, Bash
---

# Problem framing

You are here because the premise check did not come back READY. Your job is to
stop an unverified premise from being amplified into code — not to decide whether
the user is right, and not to solve the problem on their behalf.

## Separating the four

The only distinction that matters is **Observation vs Hypothesis**. The other two
are usually easy.

| | Is | Is not |
|---|---|---|
| **Goal** | The outcome the user wants, at the level they care about ("p95 under 300ms", "the flaky test stops failing") | The change they proposed |
| **Observation** | Something verified: a symptom the user saw, a log line, a failing test, a measurement, code you have read | Anything inferred from those |
| **Hypothesis** | A claimed cause, a claimed fix, a claimed mechanism — regardless of how confidently it was stated | Ruled out or confirmed |
| **Verification** | The check that closes the loop: a test, a metric, a repro that stops reproducing | "looks better" |

A request usually arrives with the Hypothesis in the imperative mood. "Speed up
this SQL" is a proposed fix; the Observation behind it may only be "the page feels
slow". Write down what was actually seen, separately from what it was attributed to.

Three things that are **not** Observations, however stated:
- A cause with no measurement behind it.
- A conclusion from a tool the user did not run in this situation.
- Your own reasoning from a previous turn. Inference does not become evidence by
  being repeated.

If Observation is empty and Hypothesis is full, that is the dangerous shape. That
is INVESTIGATE.

## Choosing the verdict

Work down this list and take the first that fits:

**CLARIFY** — Goal or Verification is missing, and different readings lead to
materially different work. Ask the smallest set of questions that closes the gap
(usually one or two), then stop. Never ask for all four. Never ask for something
you could find yourself in the codebase — that is INVESTIGATE, not CLARIFY.

**INVESTIGATE** — a Hypothesis about cause would shape the change, and the
codebase, logs or tests can confirm or kill it. Say in one line what you are
checking and why, then check it. Read, grep, run the test, measure. Report what
you found, and what it implies for the original request. Do not edit
implementation code during this step; if the investigation confirms the premise,
continue into the work in the same turn.

**PROCEED_WITH_ASSUMPTIONS** — the premise is unconfirmed but the change is small,
reversible, and cheap to undo, or the user has said they want to try it anyway.
State the assumption in one line, keep it labelled as an assumption in your summary,
and do the work. Do not argue the user out of an experiment they chose.

**READY** — everything needed is present. Work, silently.

When two fit, sort by what is missing, not by what is cheap. A missing *cause* is
INVESTIGATE — the repo can answer it, and reading code beats a round trip through
the user. A missing *goal or success criterion* is CLARIFY, and no amount of
investigation will supply it: finding the real cause still does not tell you which
outcome was wanted or when to stop. So check for a missing criterion first.

## Output shape

Keep it short. No headers, no tables, no restating the request.

- CLARIFY: the questions, and nothing else. Two sentences of context at most.
- INVESTIGATE: one line on what you are verifying, then the work, then what you
  found and what it changes.
- PROCEED_WITH_ASSUMPTIONS: one line naming the assumption, then the work.

Never print the four categories as a checklist. Never print the verdict name.
Never explain this skill to the user, and never tell them their reasoning was
flawed — if the premise is wrong, the evidence you found says so by itself.

## Worked examples

**"The DB is the bottleneck, optimize this query"** — Observation: something is
slow, scope unstated. Hypothesis: the DB, and this query specifically.
Verification: absent. → INVESTIGATE. Look for timing data, existing traces or
metrics, the query's actual shape and indexes, and what else sits on that path.
Optimizing the query first would produce a real diff that may fix nothing.

**"This code is slow, make it nicer"** — Goal ambiguous (latency? readability?),
Verification absent, no Observation at all. → CLARIFY. Ask which one, and what
"fast enough" means. Two questions, then stop.

**"Fix the typo in the README"** — Goal, Observation and Verification are all
trivially present. → READY. Do it.

**"Users get a 500 on POST /orders when the cart is empty; expected a 400; see
`test_empty_cart`"** — repro, observed behavior, expected behavior, and a test to
verify against. → READY. Do not ask anything.

**"I haven't confirmed the cause but I think it's the retry loop — try removing it
and let's see"** — the user has already labelled the Hypothesis as a Hypothesis and
chosen a small experiment. → PROCEED_WITH_ASSUMPTIONS. The framing work is done;
doing it again is the failure mode this plugin exists to avoid.

## What this is not

Not a judge of whether the user is right. Not a replacement for their thinking.
Not a place to teach them about causal reasoning. One intervention, at the moment
it is cheapest, and then out of the way.
