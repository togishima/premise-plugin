#!/bin/sh
# SessionEnd hook. Housekeeping only, no behavior.
#
# The checkpoint drops one empty marker per (request, agent) under TMPDIR. This
# removes this session's, so they do not accumulate.
input=$(cat)
session=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$session" ] || session="nosession"
rm -f "${TMPDIR:-/tmp}/premise-edit.$(id -u).${session}."* 2>/dev/null || true
