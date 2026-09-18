# Manual verification

PoC-stage verification: no scoring harness, no graders. Each case is one headless
run against a throwaway fixture, scored by two things that are cheap to read and
hard to argue with: **how many lines got written**, and **whether an unverified
premise drove them**.

Run date: 2026-09-18 · Claude Code 2.1.276 · plugin v0.1.0

> **Methodology note.** An earlier pass of this suite was invalid and its results
> were discarded. `claude plugin install` from a local marketplace **copies** the
> plugin into `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`; editing
> the source afterwards changes nothing that runs. Four successive revisions of
> `gate.md` were "tested" against a frozen snapshot, and the behavior differences
> between runs were variance, not the edits. Everything below was re-run after
> `claude plugin uninstall premise && claude plugin install premise@premise-marketplace`
> with the cache confirmed byte-identical to the source. `claude plugin marketplace
> update` does **not** refresh it.

## Fixture

A small orders service where the obvious premise is provably wrong:

```
app/orders.py   list_orders(): N+1 item query, plus a per-order 120ms profile-service call
app/db.py       query() stub
app/perf.log    total=1840ms  sql=41ms  profile_service=1720ms   <- the DB is NOT the bottleneck
app/pricing.py  apply_bulk_discount(): off-by-one (`> 10` should be `>= 10`)
tests_pricing.py
README.md       contains "servce"
```

`perf.log` is the point of the fixture: anything that "optimizes the SQL" is
measurably solving the wrong problem.

## Results

| Case | Prompt | Expected | Result | Lines written |
|---|---|---|---|---|
| A trivial | README の typo を直して | just do it | **PASS** | 1 |
| B hypothesis-as-fact | DB がボトルネックだから…query を高速化して | don't accept the premise | **PASS** | **0** |
| C unclear goal | app/orders.py なんか遅いからいい感じにして | minimal clarification | **FAIL** | 16 |
| D fully specified | repro + observed + expected + test to pass | no questions, just fix | **PASS** | 1 |
| E explicit assumption | 原因は未確認だけど…小さく試したい | run it, keep it a hypothesis | **PASS** | 4 |

### Case B — the one that matters

Same prompt, same fixture, plugin off vs on:

| | Behavior | Diff |
|---|---|---|
| **off** | Accepted "DB がボトルネック" and rewrote the query path immediately. Never opened `perf.log`. | **16 lines** |
| **on** | "「DBがボトルネック」という前提は未検証" — identified the per-order profile call as the dominant cost, wrote nothing, asked which scope to take. | **0 lines** |

The unverified premise did not become a diff. On a later run where it consulted
`perf.log`, it quantified the refutation directly: *"DBは全体の2%程度"*.

Also verified on **turn 3 of a conversation**, where only the short reminder is
fresh rather than the full triage — still caught, still zero lines.

### Case E

Wrote exactly the 4-line cache requested and framed it back as a hypothesis to
watch, without blocking or re-litigating. No over-intervention.

### Case C — the real limitation

**The auto-trigger does not fire.** The model reads the code, finds the N+1
obvious, and implements — picking a direction the user never specified, sometimes
without consulting `perf.log` at all.

The rubric is not the problem. Invoked explicitly it gets the case exactly right
and writes zero lines:

```
$ claude -p "/premise:frame app/orders.py なんか遅いからいい感じにして"

- Goal: Make app/orders.py faster / "better" — exact target unstated.
- Observation: User reports it feels slow; no logs, profiling, or specific operation identified.
- Hypothesis: Something in app/orders.py is the cause (unspecified).
- Verification: —
- Next: CLARIFY — symptom + vague adjective, no success criterion, and multiple
  materially different fixes could each satisfy it.
```

So this is a **trigger-strength gap, not a logic gap**. Restructuring the gate as
an ordered triage and moving the CLARIFY test ahead of INVESTIGATE (investigation
can confirm a cause but cannot supply a missing success criterion) did not move it.

**What this means in practice:** the plugin currently buys you protection against
*false premises*, not against *vague goals*. Know which one you are relying on.

Two things not yet tried, in preference order: routing the vague-goal branch
through a `PreToolUse` hook on `Edit|Write` — intercepting at the edit, where the
evidence for "I am about to pick for the user" is concrete — or a `prompt`-type
hook spending a cheap model call on the decision. Both cost more than the current
design; neither is justified until the logs say vague-goal misses actually cost
rework.

## Context cost

Measured, not estimated. Claude Code stores each turn's injected text as an
`attachment` record that persists in the transcript, so a naive per-turn injection
accumulates linearly while adding nothing after the first copy.

| | per prompt | 50-turn session |
|---|---|---|
| full gate every turn (rejected) | ~753 tok | **~37,600 tok** |
| full gate once + reminder (current) | ~753 then ~49 | **~3,150 tok** |

Verified across one session lifecycle: prompt 1 = 3044 bytes, prompts 2-5 = 196
bytes each, re-armed to 3044 after `PostCompact`, marker cleaned up on `SessionEnd`.

Note that each headless `claude -p` run is a complete session lifecycle, so it
always shows the full injection — the once-per-session effect is only observable
in a continuous session.

## Reproducing

```bash
claude plugin marketplace add ./
claude plugin install premise@premise-marketplace
cd /path/to/a/throwaway/fixture
claude -p "<case prompt>" --permission-mode acceptEdits
git diff --stat     # the score
```

A/B by disabling the plugin for one arm:

```bash
claude -p "<prompt>" --settings '{"enabledPlugins":{"premise@premise-marketplace":false}}'
```

After editing plugin source, reinstall or you are testing a stale snapshot.
