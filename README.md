# premise

A Claude Code plugin that runs one silent problem-framing check before
implementation, so an unverified premise does not get amplified into code.

It is not a reviewer of your reasoning, and not a replacement for it. It exists to
catch one specific failure:

> you guess a cause → you state the guess as fact → the agent believes you →
> it writes a lot of code → review finds you solved the wrong problem.

Measured on this repo's fixture, that exact request produces **16 lines of
confident, wrong-target code** without the plugin and **0 lines plus one question**
with it. A vague request ("なんか遅いからいい感じにして") likewise goes from 16 lines
of unasked-for refactor to one question. Typos, renames and fully specified bug
fixes are untouched. See [`tests/cases.md`](tests/cases.md).

## Install

```bash
claude plugin marketplace add togishima/premise-plugin
claude plugin install premise@premise-marketplace
```

No clone needed — `marketplace add` takes a GitHub `owner/repo`, a git URL, or a
local path, and clones it for you. Clone only if you intend to edit the plugin
(see [Development](#development)).

Verify:

```bash
claude plugin details premise
```

Remove it with `claude plugin uninstall premise`. If it ever gets in your way,
`/plugin` toggles it off without uninstalling.

## What it does

Before writing or editing code, Claude sorts the request into four parts:

- **Goal** — the outcome wanted
- **Observation** — what is actually verified: symptoms, logs, test output,
  measurements, code that has been read
- **Hypothesis** — what is only guessed, above all any claimed *cause* or *fix*
- **Verification** — how we will know it worked

Only one distinction really matters: **Observation vs Hypothesis**. "DB がボトル
ネックだからこの SQL を高速化して" is not an observation that the DB is slow. It is
an observation that *something* is slow, plus a hypothesis about why. The plugin's
whole job is to stop that hypothesis from silently becoming the design of a diff.

Your own inference counts too. Reading code and concluding "this N+1 is the
problem" is a hypothesis, not a measurement.

Then it takes the first branch that fires:

| | when | what happens |
|---|---|---|
| **PROCEED_WITH_ASSUMPTIONS** | you already called your premise a guess | runs your experiment, keeps it labelled a guess |
| **CLARIFY** | no success criterion, and several different changes would fit | one or two questions, then stops |
| **INVESTIGATE** | an unmeasured cause would drive the change | checks logs/tests/code first, no edits yet |
| **READY** | everything else | does the work, silently |

READY is the fall-through, and it is where most requests land. Typos, renames, a
named file with an unambiguous expected result, a repro plus expected behavior, a
test to make pass — none of these get questioned.

## Design

Three pieces, all stock Claude Code mechanisms. No server, no database, no
classifier, no state beyond one empty marker file in `/tmp`.

```
hooks/gate.md              the triage, injected as context
hooks/premise-gate.sh      UserPromptSubmit — full triage once per session, then silent
hooks/precheck.json        the first-edit checkpoint
hooks/premise-precheck.sh  PreToolUse on Edit|Write — fires once per request
hooks/premise-rearm.sh     PostCompact / SessionEnd — re-arm and clean up
skills/problem-framing/    the full rubric, loaded only when the gate does not say READY
commands/frame.md          /premise:frame — explicit, manual framing
```

**Two checkpoints, at different moments.** The prompt-time gate catches false
premises: "DB がボトルネックだから" is refutable before any code is read. It does
*not* catch vague goals, because at prompt time the model has not yet discovered
that several different changes would fit — the question is still abstract.

So the second checkpoint sits at the **first code edit of each request**, where
the model has read the code, picked one change, and the evidence that it is
choosing the goal for the user is concrete. It fires at most once per request and
only on requests that edit code.

**Why a hook and not just a skill.** Skills fire when their description matches the
conversation. But a dangerous request *looks exactly like a normal request* — "この
SQL を高速化して" reads as ordinary implementation work. The skill would fail to
fire precisely when it is needed. The hook guarantees the question gets asked; the
model answers it.

**Why the hook does no classification.** It has no model. A regex guess at "is this
request risky?" would be wrong often and would be one more thing to maintain. It
decides only *how loudly* to ask. All judgment stays with the model, which is good
at this.

**Why the gate is injected once per session, not per turn.** Claude Code keeps each
turn's injected context as a transcript `attachment` that persists. Re-injecting
750 tokens every turn would accumulate to ~37k over 50 turns while adding no
information after the first copy — the first copy is still there.

An earlier version kept a ~49-token reminder on later prompts for recency. It was
removed after measuring it: with the reminder and without it, both the false-premise
case and the vague-goal case were caught identically, including one run where the
triage sat 6 turns back. It was not earning its keep, so prompts after the first
now cost **zero**. That matters because this hook has no matcher and fires on every
prompt — including "thanks" and questions that never touch code.

A `PostCompact` hook re-arms the full injection, which matters more now that
nothing else would remain if compaction summarized the original away.

| | per prompt | 50-turn session |
|---|---|---|
| naive per-turn injection | ~753 tok | ~37,600 tok |
| reminder version | ~753 then ~49 | ~3,150 tok |
| **this design** | ~753 then **0** | **~753 tok** |

Plus ~221 tokens always-on for the skill and command descriptions.

The gate hook itself runs on every prompt, but after the first it writes nothing,
so it adds no tokens.

**The first-edit checkpoint fires once per request, not once per edit.** It is
keyed on `prompt_id`, so the second and later edits of the same request run the
hook, produce no output, and add nothing to context. Measured on a request that
touched three files:

| | |
|---|---|
| `Edit` calls | 4 (3 edits + 1 retry of the denied one) |
| denials delivered | **1** |
| deny reason | ~541 tok |
| duplicated payload (the denied edit, re-sent) | ~61 tok |
| context added by edits 2 and 3 | **0 tok** |
| **total, once** | **~600 tok** |

The one variable cost is that duplicated payload: the *first* edit of a request is
sent twice. Here that was 61 tokens; for a first edit that writes a large new file
it is however big that file is. Later edits in the same request are never
duplicated.

## What it does not do

- It does not judge whether you are right.
- It does not think for you, or propose the answer on your behalf.
- It does not make you fill in four fields. The four categories are printed in
  exactly one place: when you run `/premise:frame` yourself.
- It does not re-open a framing already settled in the conversation, and it does
  not ask twice. Asking twice is this check failing, not working.

## What counts as a stated goal

The first-edit checkpoint turns on one distinction, kept deliberately explicit
because the vaguer version did not work. A success criterion counts only if it is:

- a number or threshold — "under 300ms", "half the queries"
- a named test or assertion to make pass
- an exact expected behavior — "should return 400, not 500"
- the change and its location, named by you — "cache the profile lookup in `list_orders`"

A **direction** is not a criterion: "faster", "cleaner", "better", "いい感じに",
"最適化して". It says which way to go, not what to change or when to stop.

Without a criterion, the edit proceeds anyway if it is on a closed list of changes
that cannot embody a goal choice: a typo, a rename, formatting, a comment, or
restoring something you named. Performance refactors, N+1 fixes, caching, batching,
restructuring and error-handling changes are deliberately **not** on that list —
however obviously right they look, each one picks a goal on your behalf.

Anything else: one line naming the fork, and a question.

## Subagents

Claude Code delegates work to subagents that do not share the parent's context, so
this was tested separately. Two things are true, both measured:

**The gate does not reach subagents.** `UserPromptSubmit` fires only for the parent
— no subagent event carries an `agent_id`. `SubagentStart` cannot stand in for it
either: its `additionalContext` was probed with an observable side effect and does
not reach the subagent. So a subagent sees its task prompt and nothing else.

**The first-edit checkpoint does reach them.** Plugin `PreToolUse` hooks fire on
subagent tool calls, carrying the subagent's `agent_id`.

That leaves one layer of protection inside a subagent instead of two, which is
mostly fine: the parent saw the gate and does the framing before delegating. The
residual risk is a parent that passes an unverified premise into the task prompt,
and there the checkpoint is what catches it.

It only catches it because of a fix this testing forced. Subagents share the
parent's `session_id` **and** `prompt_id`, so keying the once-per-request marker on
those alone let whoever edited first consume the checkpoint for everyone: a parent
making one trivial edit before delegating left the subagent completely unchecked,
and with parallel subagents only one was ever checked. The marker is now keyed on
`agent_id` too, so the parent and each subagent each get exactly one.

**This is not reliable, and the earlier claim here was wrong.** Parent fixes a typo,
then hands a subagent "app/orders.py をいい感じに速くして": the subagent stops and
asks in roughly **2 of 5 runs** and implements unasked in the rest. An earlier
version of this section reported a single passing run as a verified fix. It does
not replicate, and removing the gate entirely does not change the rate (1/2 vs
1/3), so the `agent_id` fix was necessary but is not sufficient.

Treat the subagent path as **unprotected** until this is measured properly and
raised.

## Known limitations

- The checkpoint costs ~600 tokens once per request that touches code. Not free.
- "More than one materially different change would fit" is the model's judgment,
  not a rule. It will sometimes be wrong in both directions.
- A subagent gets the checkpoint but never the gate, and the vague-goal case is
  caught there only ~2 of 5 runs (see [Subagents](#subagents)).
- **Every result in this repo is a small-n count, not a rate.** The behavior is
  stochastic, so a single passing run means very little — one such run was
  published here as a verified fix and did not replicate.
- Verified against one fixture and a handful of cases. That is a PoC, not evidence
  that it holds across real work — which is what the next section is for.

## Measuring whether it helps

Deliberately no scoring and no telemetry — those would be a second thing to
maintain before knowing whether the first thing works. What to watch instead, all
from data Claude Code already keeps:

**The transcripts.** `~/.claude/projects/<project>/*.jsonl` holds every turn.
Useful counts:

- How often a `<premise-gate>` turn was followed by a question instead of an edit
  (interventions), and how often that question was one you were glad to answer.
- How often you answered a clarification with "just do it" — the over-asking rate,
  the number that decides whether this plugin is worth keeping.
- Turns where the first tool call was `Read`/`Grep` rather than `Edit`/`Write` on a
  request that asserted a cause — investigations that would otherwise have been
  edits.
- `problem-framing` skill loads: how often the gate escalated past READY.

**The diffs.** The honest measure is lines written before the problem was
understood. `git diff --stat` on a branch that got reverted is the cost this
plugin is trying to avoid.

**Your PRs.** The outcome that matters is how often review says "this solves the
wrong problem." If that number does not move after a few weeks, the plugin is not
earning its context.

A natural next step, if the PoC survives contact: a `PostToolUse` hook on
`Edit|Write` appending one line per edit to a local log, giving edits-per-request
over time. Not built, on purpose.

## Development

To work on the plugin, clone it and add the marketplace from the local path
instead of from GitHub:

```bash
git clone https://github.com/togishima/premise-plugin
cd premise-plugin
claude plugin marketplace add ./
claude plugin install premise@premise-marketplace
```

The install **copies** the plugin into
`~/.claude/plugins/cache/premise-marketplace/premise/<version>/`. Editing the source
does not change what runs, and `claude plugin marketplace update` does not refresh
it. After any edit:

```bash
claude plugin uninstall premise && claude plugin install premise@premise-marketplace
```

Skipping this means testing a stale snapshot — it invalidated a full pass of this
repo's own test suite before it was caught.

```bash
claude plugin validate .        # manifest check
```

The hooks are POSIX `sh` with no dependencies — no `jq`, no Python.

## License

MIT
