#!/bin/sh
# SessionEnd hook. Housekeeping only, no behavior.
#
# Two marker families, and they die at different times.
#
# premise-edit is per (request, agent) and is certainly dead once the session ends,
# so this removes this session's outright.
#
# premise-rubric is per (session, agent) and records that this agent has already
# been sent the full rubric. Deleting it here broke resumed sessions: every
# `claude -p` invocation ends, so a `--resume` of the same session_id found no
# marker and paid for the full text again. It is pruned by age instead. Leaving it
# does not weaken the check -- the short form is only sent when the session_id
# matches, and a fresh session has a new one, so a new `claude -p` still gets the
# full rubric. Only a resume benefits, and there the full text is restored into the
# conversation the short form refers back to.
input=$(cat)
session=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$session" ] || session="nosession"
tmp="${TMPDIR:-/tmp}"
uid=$(id -u)
rm -f "${tmp}/premise-edit.${uid}.${session}."* 2>/dev/null || true
find "$tmp" -maxdepth 1 -name "premise-rubric.${uid}.*" -mtime +1 -delete 2>/dev/null || true
