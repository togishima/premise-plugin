#!/bin/sh
# SessionStart hook, compact only. Re-arms the full rubric.
#
# The short checkpoint text assumes the full one is still readable earlier in the
# conversation. Compaction can summarise it away, and a short reminder pointing at
# text that is no longer there is worse than no reminder. Dropping the rubric marker
# makes the next firing send the full text again. The per-request edit markers are
# left alone: compaction does not start a new request.
input=$(cat)
session=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$session" ] || session="nosession"
rm -f "${TMPDIR:-/tmp}/premise-rubric.$(id -u).${session}."* 2>/dev/null || true
