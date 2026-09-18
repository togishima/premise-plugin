#!/bin/sh
# UserPromptSubmit hook.
#
# Contract: on exit 0, plain-text stdout is appended to Claude's context for this
# turn. It is not shown to the user, so the gate stays invisible unless Claude
# acts on it.
#
# Emits the triage on the FIRST prompt of a session and nothing at all after that.
#
# Claude Code keeps each turn's injected text in the transcript as an attachment,
# so the first copy stays in context on its own for the rest of the session --
# re-injecting it buys recency and nothing else. Measured: with a per-prompt
# reminder and without it, the false-premise case and the vague-goal case were
# caught identically, including 6 turns after the triage was injected. So the
# reminder was removed. Prompts after the first now cost zero tokens, which
# matters because this hook has no matcher and fires on every prompt, including
# ones that have nothing to do with code.
#
# The PostCompact hook clears the marker: compaction can summarize the triage
# away, and with no reminder there would be nothing left to fall back on.
#
# Deliberately does no classification: it has no model, and a regex guess at
# "is this request risky?" would be both wrong and another thing to maintain.

input=$(cat)

session=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$session" ] || session="nosession"

marker="${TMPDIR:-/tmp}/premise-gate.$(id -u).${session}"

# Already injected for this session: add nothing.
[ -f "$marker" ] && exit 0

: > "$marker" 2>/dev/null || true
cat "${CLAUDE_PLUGIN_ROOT}/hooks/gate.md"
