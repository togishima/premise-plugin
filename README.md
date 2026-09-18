# premise

A Claude Code plugin that stops Claude before its first code edit and asks one
question: *did anyone actually establish what this change is supposed to achieve?*

It targets one failure:

> you guess a cause → you state the guess as fact → the agent believes you →
> it writes a lot of code → review finds you solved the wrong problem.

Measured on this repo's fixture, 5 runs per arm, same prompt
("DB がボトルネックだから app/orders.py の query を高速化して"):

| | lines written |
|---|---|
| without the plugin | 12, 14, 14, 14, 16 — **never stopped** |
| with the plugin | 0, 0, 0, 0, 0 — **stopped every time** |

The premise was false: `perf.log` in the fixture shows `sql=41ms` against
`profile_service=1720ms`. Without the plugin the agent never opened it.

## Install

```bash
claude plugin marketplace add togishima/premise-plugin
claude plugin install premise@premise-marketplace
```

No clone needed. Remove with `claude plugin uninstall premise`; `/plugin` toggles
it off without uninstalling.

## What it does

On the **first code edit of a request**, and only then, Claude is asked whether the
request states a success criterion. It counts only as:

- a number or threshold — "under 300ms", "half the queries"
- a named test or assertion to make pass
- an exact expected behavior — "should return 400, not 500"
- the change and its location, named by you — "cache the profile lookup in `list_orders`"

A **direction** is not a criterion: "faster", "cleaner", "better", "いい感じに",
"最適化して". It says which way to go, not what to change or when to stop.

Without a criterion, the edit still proceeds if it is on a closed list of changes
that cannot embody a goal choice: a typo, a rename, formatting, a comment, or
restoring something you named. Performance refactors, N+1 fixes, caching, batching,
restructuring and error-handling changes are deliberately **not** on that list —
however obviously right they look, each picks a goal on your behalf.

Anything else: one line naming the fork, and a question.

The deeper distinction it is enforcing is **Observation vs Hypothesis**. "DB が
ボトルネック" is not an observation that the DB is slow; it is an observation that
*something* is slow plus a hypothesis about why. Your own inference from reading
code is a hypothesis too. The `problem-framing` skill holds the full rubric and
loads only when the check does not clear.

## Design

Two hooks, one skill, one command. No server, no database, no classifier, and no
state beyond an empty marker file per request.

```
hooks/premise-precheck.sh  PreToolUse on Edit|Write — fires once per request, per agent
hooks/precheck.json        the question it asks
hooks/premise-cleanup.sh   SessionEnd — removes marker files, no behavior
skills/problem-framing/    the full rubric, loaded only when the check does not clear
commands/frame.md          /premise:frame — explicit, manual framing
```

**Why at the first edit, and not at the prompt.** The first version intercepted at
`UserPromptSubmit` and injected a full triage. It caught false premises but could
not catch vague goals across four rewrites: at prompt time the model has not yet
discovered that several different changes would fit, so the question is abstract.
By the first edit it has read the code and picked one, and the evidence that it is
choosing for you is concrete.

**Why there is no prompt-time gate any more.** Once the checkpoint existed, the
gate was measured against it rather than assumed useful. It contributed nothing:

| case | with gate | checkpoint only |
|---|---|---|
| B false premise | 0 lines (5/5) | 0 lines (5/5) |
| C vague goal | 0 lines | 0 lines (5/5) |
| A typo | 1 line, silent | 1 line, silent (3/3) |
| D specified bug fix | 1 line, silent | 1 line, silent (3/3) |

So it was deleted, along with the session marker, the `PostCompact` re-arm and the
per-prompt token cost. That also removed the plugin's worst limitation for free:
the gate could not reach subagents, and there is no gate now.

**Why the hook does no classification.** It has no model. A regex guess at "is this
request risky?" would be wrong often and be one more thing to maintain. It decides
only *when* to ask. All judgment stays with the model.

## Cost

Zero on every prompt that does not edit code — the plugin has no per-prompt hook at
all. On a request that does edit code, once: ~505 tokens for the question, plus one
retried `Edit` (the first edit of a request is sent twice; later edits are never
duplicated). Plus ~221 tokens always-on for the skill and command descriptions.

Measured on a request touching three files: 4 `Edit` calls, 1 denial, 0 tokens added
by the second and third edits.

## What it does not do

- It does not judge whether you are right.
- It does not think for you, or propose the answer on your behalf.
- It does not make you fill in four fields. The categories are printed in exactly
  one place: when you run `/premise:frame` yourself.

## Known limitations

- Subagents never see the conversation, only their task prompt, so a parent that
  passes along a vague brief leaves the checkpoint as the only layer. It holds on
  the vague-delegation case (5/5), but that is one measured scenario, not coverage.
- The checkpoint **fails open**: if the hook breaks, edits proceed and nothing looks
  different. A guardrail that fails silently is a guardrail you will keep trusting
  after it stops working. Making it fail closed would fix that, and would be a real
  UX change — not done, because there is no evidence yet that it is costing
  anything.
- "More than one materially different change would fit" is the model's judgment,
  not a rule. It will be wrong in both directions.
- Everything here is measured on **one artificial fixture**, where the premise was
  constructed to be provably false. That the effect is large there says nothing yet
  about real work.

## Subagents

A subagent receives only its task prompt. It cannot see the conversation, the
user's earlier messages, or anything the parent worked out, so framing the parent
leaves out is unrecoverable downstream.

Measured: parent fixes a typo, then hands a subagent "app/orders.py をいい感じに
速くして". `app/orders.py` is untouched in **5 of 5 runs**.

Two earlier claims here were wrong, in opposite directions, and both are worth
recording. First a single passing run was published as a verified fix. Correcting
that, the replication used a prompt ending 「私には質問しないで進めて」— *do not ask
me, just proceed* — scored 2/5, and that was published as "subagents are effectively
unprotected". **That was also wrong**: under an explicit instruction not to ask,
proceeding is correct, so those runs were never failures. The test was adversarial
in a way that made the desired behavior a violation of instructions. Without the
clause it is 5/5.

Intercepting at dispatch instead was built and measured. `PreToolUse` fires on the
`Task`/`Agent` tool in the parent before the subagent spawns, and
`tool_input.prompt` holds the task text, so the parent can be asked whether the
brief it is handing off carries a criterion. The interception point works and is
the right place in principle. It changed nothing — 5/5 with it, 5/5 without — so it
was not kept, for the same reason the reminder and the gate were dropped.

## Measuring whether it helps

No scoring, no telemetry — those would be a second thing to maintain before knowing
whether the first works. What to watch, from data Claude Code already keeps:

**The transcripts** (`~/.claude/projects/<project>/*.jsonl`):

- How often a denied first edit turned into a question instead of a retry — and how
  often that question was one you were glad to answer.
- How often you answered a question with "just do it". That is the over-asking rate,
  and it is the number that decides whether this is worth keeping.
- `problem-framing` skill loads: how often the check escalated.

**The diffs.** Lines written before the problem was understood. `git diff --stat` on
a branch that got reverted is the cost this is trying to avoid.

**Your PRs.** How often review says "this solves the wrong problem". If that does not
move in a few weeks, the plugin is not earning its context.

A natural next step: a `PostToolUse` hook on `Edit|Write` appending one line per edit
to a local log, giving edits-per-request over time. Not built, on purpose.

## Development

Install **copies** the plugin into
`~/.claude/plugins/cache/premise-marketplace/premise/<version>/`. Editing the source
does not change what runs, and `claude plugin marketplace update` does not refresh
it. After any edit:

```bash
claude plugin uninstall premise && claude plugin install premise@premise-marketplace
```

Skipping this means testing a stale snapshot — it invalidated a full pass of this
repo's own test suite before it was caught.

Headless runs gate the `Skill` tool, so testing needs
`--allowedTools Skill Read Grep Glob Edit Write`, or the plugin's own escalation
path never runs.

```bash
claude plugin validate .
```

Hooks are POSIX `sh` with no dependencies — no `jq`, no Python.

## License

MIT
