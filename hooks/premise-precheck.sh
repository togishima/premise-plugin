#!/bin/sh
# PreToolUse hook on code-editing tools.
#
# The UserPromptSubmit gate under-fires on vague goals: at prompt time the model
# has not yet discovered that several different changes would satisfy the request,
# so "is this well-posed?" is abstract. By the first edit it has read the code and
# picked one — the evidence is concrete, and so is the question.
#
# Fires at most once per user prompt (keyed on prompt_id), and only on the first
# mutating tool call. Non-blocking: it injects the question, the model answers.
#
# PreToolUse stdout goes to the debug log only, so this must emit JSON with
# additionalContext rather than plain text.
input=$(cat)

sid=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
pid=$(printf '%s' "$input" | sed -n 's/.*"prompt_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$sid" ] || sid="nosession"
[ -n "$pid" ] || pid="noprompt"

marker="${TMPDIR:-/tmp}/premise-edit.$(id -u).${sid}.${pid}"

# Already asked for this prompt: stay out of the way.
[ -f "$marker" ] && exit 0

: > "$marker" 2>/dev/null || true
cat "${CLAUDE_PLUGIN_ROOT}/hooks/precheck.json"
