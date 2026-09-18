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
| C unclear goal | app/orders.py なんか遅いからいい感じにして | minimal clarification | **PASS** | **0** |
| D fully specified | repro + observed + expected + test to pass | no questions, just fix | **PASS** | 1 |
| E explicit assumption | 原因は未確認だけど…小さく試したい | run it, keep it a hypothesis | **PASS** | 4 |
| C2 generalization | app/orders.py をリファクタしてきれいにして | ask, don't pick | **PASS** | **0** |
| F small + explicit | query に docstring を追加して。「…」と書いて | just do it | **PASS** | 1 |

C2 and F were added after Case C was fixed, to check the fix generalizes to other
vague wording and does not over-fire on small explicit work.

> **Harness note.** Headless runs gate the `Skill` tool, so `--allowedTools Skill
> Read Grep Glob Edit Write` is required. Without it the model's attempts to load
> `problem-framing` are denied and the plugin's escalation path never runs — two
> such denials are visible in the transcripts of the earlier, invalid pass.

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

### Case C — fixed, and how

The `UserPromptSubmit` gate alone could not carry this. At prompt time the model
has not yet discovered that several different changes would satisfy the request,
so "is this well-posed?" is abstract. It read the code, found the N+1 obvious, and
implemented — across a triage rewrite and a reordering that put CLARIFY ahead of
INVESTIGATE. Four gate revisions, no movement.

What worked was a second checkpoint at a different moment: a `PreToolUse` hook on
the **first code edit of each request**, where the model has read the code and
picked one change, so the evidence that it is choosing for the user is concrete.

Getting there took three tries, and the first two failures were informative:

1. **Non-blocking `additionalContext`** — ignored. The transcript shows the hook
   firing and the `Edit` landing anyway. By the first edit the decision is made;
   a nudge does not reverse it.
2. **`permissionDecision: deny` with a self-clearing reason** — the model cleared
   it every time. It judged "遅い → 速くする" a stated goal, so the enforcement was
   never the problem; the criterion was.
3. **An explicit, closed definition of both branches** — works.

The criterion that finally held has two closed lists. A success criterion counts
only as a number/threshold, a named test, an exact expected behavior, or the user
naming both the change and where. A *direction* ("faster", "cleaner", "いい感じに")
explicitly does not — it says which way to go, not what to change or when to stop.

The second list mattered as much. "Trivially correct" was my own loophole: an N+1
fix feels like "a bug with exactly one right answer," so the model kept exempting
itself. It is now a closed list — typo, rename, formatting, comment, restoring
something the user named — with performance refactors, N+1 fixes, caching,
batching, restructuring and error-handling changes explicitly excluded, because
each embodies a choice about what the user wanted.

Result: Case C writes 0 lines and asks which fork. C2 confirms it is not overfit
to that phrasing. A, D, E and F confirm it does not over-fire, and no run mentions
the checkpoint to the user.

## Context cost

Measured, not estimated. Claude Code stores each turn's injected text as an
`attachment` record that persists in the transcript, so a naive per-turn injection
accumulates linearly while adding nothing after the first copy.

| | per prompt | 50-turn session |
|---|---|---|
| full gate every turn (rejected) | ~753 tok | **~37,600 tok** |
| full gate once + reminder (current) | ~753 then ~49 | **~3,150 tok** |

The `PreToolUse` checkpoint costs ~505 tokens plus one retried `Edit` call, at
most once per request, and only on requests that edit code. Requests that clear it
pay a round trip; that is the price of the intervention and it is not free.

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
