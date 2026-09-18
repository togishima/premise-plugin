#!/bin/sh
# PostCompact / SessionEnd hook.
#
# Compaction can summarize away the full triage injected at the start of the
# session, leaving only the one-line reminder pointing at something that is no
# longer there. Clearing the marker makes the next prompt re-inject it in full.
# On SessionEnd the same removal is just cleanup.
input=$(cat)
session=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$session" ] || session="nosession"
rm -f "${TMPDIR:-/tmp}/premise-gate.$(id -u).${session}"
# also clear this session's per-prompt edit markers
rm -f "${TMPDIR:-/tmp}/premise-edit.$(id -u).${session}."* 2>/dev/null || true
