#!/bin/sh
# SessionEnd hook. Housekeeping only, no behavior.
#
# Removes this session's cached premise verdicts.
input=$(cat)
session=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$session" ] || session="nosession"
tmp=$(python3 -c "import tempfile;print(tempfile.gettempdir())" 2>/dev/null || echo "${TMPDIR:-/tmp}")
rm -f "$tmp/premise-verdict.$(id -u).${session}."* 2>/dev/null || true
