# Worked examples

Why each shape gets the verdict it gets. The table in SKILL.md is the lookup; this is
the reasoning behind it, for when a request does not obviously match a row.

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

