#!/bin/sh
# UserPromptSubmit hook.
#
# Contract: on exit 0, plain-text stdout is appended to Claude's context for this
# turn. It is not shown to the user, so the gate stays invisible unless Claude
# acts on it.
#
# Cost note: Claude Code keeps each turn's injected text in the transcript, so a
# copy per turn would accumulate linearly (~750 tok x N turns) while adding no
# information after the first. The first copy stays in context on its own, so we
# emit the full triage once per session and a one-line reminder afterwards, purely
# for recency. A PostCompact hook clears the marker, because compaction can drop
# the original and the reminder alone means nothing.
#
# Deliberately does no classification: it has no model, and a regex guess at
# "is this request risky?" would be both wrong and another thing to maintain.
# It only decides how loudly to ask. The model answers.

input=$(cat)

session=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$session" ] || session="nosession"

marker="${TMPDIR:-/tmp}/premise-gate.$(id -u).${session}"

if [ -f "$marker" ]; then
  printf '%s\n' '<premise-gate>Premise check still applies: keep what is observed apart from what is assumed, and do not let an unverified cause drive a change. Full triage earlier in this session.</premise-gate>'
else
  cat "${CLAUDE_PLUGIN_ROOT}/hooks/gate.md"
  : > "$marker" 2>/dev/null || true
fi
