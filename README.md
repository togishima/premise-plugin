# premise

A Claude Code plugin that runs one silent problem-framing check before
implementation, so an unverified premise does not get amplified into code.

It is not a reviewer of your reasoning, and not a replacement for it. It exists to
catch one specific failure:

> you guess a cause → you state the guess as fact → the agent believes you →
> it writes a lot of code → review finds you solved the wrong problem.

Measured on this repo's fixture, that exact request produces **16 lines of
confident, wrong-target code** without the plugin and **0 lines plus one question**
with it. See [`tests/cases.md`](tests/cases.md).

## Install

```bash
git clone https://github.com/togishima/premise-plugin
cd premise-plugin
claude plugin marketplace add ./
claude plugin install premise@premise-marketplace
```

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
hooks/premise-gate.sh      UserPromptSubmit — decides full triage vs short reminder
hooks/premise-rearm.sh     PostCompact / SessionEnd — re-arm and clean up
skills/problem-framing/    the full rubric, loaded only when the gate does not say READY
commands/frame.md          /premise:frame — explicit, manual framing
```

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
information after the first copy. The first copy stays in context by itself, so
subsequent prompts get a ~49-token reminder purely for recency. A `PostCompact`
hook re-arms the full injection, because compaction can drop the original and
leave the reminder pointing at nothing.

| | per prompt | 50-turn session |
|---|---|---|
| naive per-turn injection | ~753 tok | ~37,600 tok |
| **this design** | ~753 then ~49 | **~3,150 tok** |

Plus ~221 tokens always-on for the skill and command descriptions.

## What it does not do

- It does not judge whether you are right.
- It does not think for you, or propose the answer on your behalf.
- It does not make you fill in four fields. The four categories are printed in
  exactly one place: when you run `/premise:frame` yourself.
- It does not re-open a framing already settled in the conversation, and it does
  not ask twice. Asking twice is this check failing, not working.

## Known limitation

**It protects against false premises, not vague goals.** Case B (asserted cause)
is caught reliably. Case C ("なんか遅いからいい感じにして") is not — the model finds
a plausible fix and implements it rather than asking. The rubric itself gets that
case right when invoked explicitly via `/premise:frame`; the auto-trigger is what
under-fires. Restructuring the gate did not close it. Details and the two
candidate fixes are in [`tests/cases.md`](tests/cases.md).

Until that is closed, `/premise:frame` is the reliable path for "I am not sure this
request is well-posed."

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
