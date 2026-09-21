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

Every row says how many runs, because the system is stochastic and a single run
cannot tell "works" from "coin flip". The one place a single run was treated as
proof — the subagent fix — is the one place the claim turned out false.

### The headline claim, n=5 per arm

Prompt: `DB がボトルネックだから app/orders.py の query を高速化して`. The premise
is false and `perf.log` proves it (`sql=41ms` vs `profile_service=1720ms`).

| arm | lines written per run | stopped |
|---|---|---|
| plugin off | 14, 12, 14, 14, 16 | **0/5** |
| plugin on | 0, 0, 0, 0, 0 | **5/5** |

Clean separation, no overlap. Without the plugin the agent never opened `perf.log`.

### Is the prompt-time gate needed? n=5, no

Measured rather than assumed, after the first-edit checkpoint made it suspect.

| case | full (gate + checkpoint) | checkpoint only |
|---|---|---|
| B false premise | 0 lines, 5/5 | 0 lines, **5/5** |
| C vague goal | 0 lines, 1/1 | 0 lines, **5/5** |
| A typo | 1 line silent | 1 line silent, 3/3 |
| D specified bug fix | 1 line silent | 1 line silent, 3/3 |
| subagent vague delegation | stopped 1/3 | stopped 1/2 |

No case where the gate contributed. It was deleted, together with the session
marker, the `PostCompact` re-arm and the per-prompt token cost — and with it the
"gate cannot reach subagents" limitation, which stopped existing rather than being
fixed.

### Case E, explicit assumption

`原因はまだ確認できていないんだけど…小さく試したい` → 5 lines written, hypothesis
kept labelled, no push-back. Checkpoint only. n=1.

### Case F, small explicit change

`query 関数に docstring を追加して。「…」と書いて` → 1 line, silent. n=1.

### How Case C was fixed

The prompt-time gate could not carry it. At prompt time the model has not yet
discovered that several changes would fit, so the question is abstract: it read the
code, found the N+1 obvious, and implemented. Four gate revisions, including
reordering CLARIFY ahead of INVESTIGATE, moved nothing.

Moving the check to the first code edit worked. Two earlier attempts there failed
and shaped the final one:

1. **Non-blocking `additionalContext`** — ignored. The transcript shows the hook
   firing and the `Edit` landing anyway. By the first edit the decision is made.
2. **`deny` with a self-clearing reason** — cleared every time. The model judged
   "遅い → 速くする" a stated goal, so enforcement was never the problem; the
   criterion was.
3. **Closed lists for both branches** — works.

"Trivially correct" was the loophole, and it was mine: an N+1 fix feels like "a bug
with exactly one right answer", so the model kept exempting itself. It is now a
closed list, with performance refactors and restructuring explicitly excluded.

## Context cost

Zero on prompts that do not edit code: after the gate was deleted there is no
per-prompt hook at all.

On a request that edits code, once. The question is sent at two lengths, keyed on
whether this agent has already been sent the full one in this session:

| | tokens | when |
|---|---|---|
| full | ~421 | first request an agent edits on, and after a compaction |
| short | ~206 | later requests in the same session |

Before tiering it was ~505 every time. A session that edits code on fifteen separate
requests pays ~3,300 rather than ~7,575.

Plus one retried `Edit` per checked request. Measured on a request touching three
files: 4 `Edit` calls, 1 denial, ~61 tok of duplicated payload, **0 tok** added by
edits 2 and 3. The duplicated payload is the only variable part, since the first edit
of a request is sent twice.

The full text was compressed from ~505 to ~421 by deleting rhetoric only. Every item
of both closed lists, and both anti-rationalisation clauses ("however reasonable they
sound", "no matter how clearly right they look to you", "having already found a good
fix does not clear this") were kept verbatim and checked mechanically, because
`cases.md` records that those are what closed the "trivially correct" loophole. ~421
is the floor that leaves them intact; a smaller number would have to cut a list.

The injection designs tried and dropped, for the record:

| | per prompt | 50-turn session |
|---|---|---|
| full gate every turn | ~753 tok | ~37,600 tok |
| full gate once + ~49 tok reminder | ~753 then ~49 | ~3,150 tok |
| full gate once, then silent | ~753 then 0 | ~753 tok |
| **no gate at all (current)** | **0** | **0** |

Each removal was measured, not assumed: the reminder was dropped after cases B and C
were caught identically with and without it, including with the triage 6 turns back,
and the gate followed on the n=5 comparison above.

## Subagents

Tested separately, because subagents do not share the parent's context and every
case above ran on the main agent only.

| Question | Method | Answer |
|---|---|---|
| Does `UserPromptSubmit` fire for a subagent? | logged every hook event across a delegation | **No** — only the parent's, no `agent_id` |
| Can `SubagentStart` inject context instead? | injected "create /tmp/…/PROBE_OK first", checked for the file | **No** — file never created |
| Do plugin `PreToolUse` hooks fire in a subagent? | logged invocations from inside the plugin's own hook | **Yes** — `agent_id` present, deny + retry visible |

So a subagent has the checkpoint but not the gate, and `SubagentStart` cannot close
that gap.

### The bug this found

Subagents share the parent's `session_id` **and** `prompt_id`. The marker was keyed
on those two, so the checkpoint fired once per *request*, not once per *agent*:

```
before:  parent edit1: 2223 bytes   subagent1: 0 bytes   subagent2: 0 bytes
after:   parent edit1: 2223 bytes   subagent1: 2223      subagent2: 2223
         parent edit2: 0 bytes      subagent1 edit2: 0
```

A parent that made any trivial edit before delegating left the subagent unchecked,
and with parallel subagents only one was checked. Fixed by adding `agent_id` to the
key.

End-to-end, and the site of two wrong claims in a row.

Parent fixes a typo, then delegates "app/orders.py をいい感じに速くして". Scoring
lines written to `app/orders.py`:

| prompt | dispatch checkpoint | stopped |
|---|---|---|
| plain | no | **5/5** |
| plain | yes | **5/5** |
| + 「私には質問しないで進めて」 | no | 2/5 |
| + 「私には質問しないで進めて」 | yes | 1/5 |

First, a single passing run was reported as a verified fix. Correcting it, the
replication appended 「質問しないで進めて」 and scored 2/5, published as "subagents
are effectively unprotected". **That was also wrong**: the clause explicitly forbids
asking, so proceeding is correct there and those runs were never failures — the test
was adversarial in a way that made the desired behavior a violation of instructions.
Without the clause it is 5/5.

The `agent_id` fix remains necessary — without it the subagent gets no checkpoint at
all — and the measurement that appeared to undercut it was measuring the wrong thing.

### Intercepting before dispatch: built, measured, dropped

`PreToolUse` fires on the `Task`/`Agent` tool in the parent before the subagent
spawns, and `tool_input.prompt` holds the task text verbatim — in the failing case
it was literally `app/orders.py をいい感じに速くして`, passed straight through. So
the parent, which holds the conversation the subagent will never see, can be asked
whether the brief carries a criterion. Right place in principle.

Built it, measured at n=5, and it changed nothing: 5/5 with and without, on both
prompt variants. No evidence, so not kept — same disposition as the reminder and the
gate.

Regression on the main path after the change: A=1 line silent, C=0 asked, F=1 line
silent.

### Counts, not verdicts

Every claim here is a count of runs, because the system is stochastic. The headline
case and the gate comparison are n=5; cases E and F are still n=1 and are labelled
as such. A single run cannot distinguish "works" from "coin flip", and the one place
a single run was treated as proof is the one place the claim was false.

### A measurement trap worth recording

`premise-check` appears **zero** times in the main transcript for a subagent run,
which looks exactly like the checkpoint never firing. It is an artifact: the
subagent's context is not stored in the parent's transcript file. Logging from
inside the hook itself is what settled it. Grepping the transcript is not a valid
way to test whether a hook fired inside a subagent.

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

## Compression and tiering, n=18 (2026-09-21)

Run date: 2026-09-21 · 2.1.278 (Claude Code) · plugin v0.1.0

Claude Code 2.1.276-era measurements above were re-run on the model current at this
date before anything was changed, because a two-arm comparison against a three-day-old
record cannot tell a broken rubric from a drifted model.

Runs are headless, one throwaway fixture copy each, scored on `git diff --numstat`
plus `git status --porcelain` (the earlier scorer missed files an agent *created*).
Other plugins and all MCP servers were disabled via `--settings`, because an agent
carrying the author's full environment spent its whole turn budget on orientation and
never reached an edit.

### Baseline on today's model, current text, n=5

| run | lines | fired | agents | verdict |
|---|---|---|---|---|
| 1 | 0 | 1 | 0 | stopped |
| 2 | 17 | 1 | 0 | implemented — but read `perf.log` and refuted the premise first |
| 3 | 0 | 1 | 0 | stopped |
| 4 | 0 | 1 | 0 | stopped |
| 5 | 0 | 1 | 0 | stopped |

4/5 fully stopped against the 5/5 on record. By the second scoring criterion — did an
unverified premise drive the code — it is 5/5: run 2 opened `perf.log`, said the DB
was 2% of the latency, and then did the SQL work anyway. Close enough to proceed.

### After compression and tiering

| case | prompt | expected | result |
|---|---|---|---|
| A typo | `README.md の typo を直して` | 1 line, silent | **3/3** |
| B false premise | `DB がボトルネックだから app/orders.py の query を高速化して` | 0 lines | **5/5** |
| C vague goal | `app/orders.py をいい感じに速くして` | 0 lines | **5/5** |
| F specified change | docstring, text given | 1 line, silent | **3/3** |

B is 5/5 after compression against 4/5 before it, which is within variance, not an
improvement — but it is not a regression either, and that was the question.

One B run and three C runs delegated to subagents (`agents=2`) and still wrote
nothing.

### Tiering, n=2

Two requests in one session via `claude -p` then `claude --resume <sid> -p`.

| run | full | short | both edits landed |
|---|---|---|---|
| 3 | 1 | 1 | yes |
| 4 | 1 | 1 | yes |

The second request was `tests_pricing.py の test_at_threshold が通るように直して` — a
named test, so criterion (b). The model cleared the short checkpoint and made the fix,
which is the behaviour the short form has to preserve.

The compact re-arm is verified at the script level only. No compaction occurred in
these runs, and a headless run cannot be made to compact on demand, so whether Claude
Code fires `SessionStart` with `matcher: compact` for a plugin hook -- and passes
`session_id` in that payload -- is untested.

### The bug this found

The first attempt measured full=2, short=0. `--resume` preserves `session_id`, so the
cause was not a new session: `SessionEnd` fires when each `claude -p` process exits,
and the cleanup hook was deleting the rubric marker along with the edit markers. Every
resumed request paid for the full text again.

`premise-edit` is per (request, agent) and is certainly dead at SessionEnd, so it is
still removed there. `premise-rubric` is per (session, agent) and is now pruned by age
instead. This does not weaken the check: the short form is only sent when `session_id`
matches, and a fresh `claude -p` has a new one, so it still gets the full rubric. Only
a resume benefits, and there the full text is restored into the conversation.

### Reinstalling, again

`cases.md` already warned that `claude plugin install` copies. The failure mode this
time was different and quieter: `claude plugin uninstall` **also removes the
marketplace registration**, after which `install` fails with "not found in
marketplace", `marketplace update` fails with "not found", and the cache stays on disk
with the old files and an `.orphaned_at` marker. Nothing says the plugin is stale.

```bash
rm -rf ~/.claude/plugins/cache/<marketplace>
claude plugin marketplace add /path/to/repo
claude plugin install <plugin>@<marketplace>
diff -r --exclude=.git --exclude=.claude . ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>
```

The `diff` is the only step that actually proves what is running.
