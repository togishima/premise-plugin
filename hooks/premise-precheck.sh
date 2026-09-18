#!/bin/sh
# PreToolUse hook on code-editing tools. The plugin's only behavioral component.
#
# Asks at the first code edit of a request, rather than when the prompt arrives.
# An earlier version injected the question at UserPromptSubmit and could not catch
# vague goals across four rewrites: at prompt time the model has not yet discovered
# that several different changes would fit, so "is this well-posed?" is abstract.
# By the first edit it has read the code and picked one, and the evidence that it
# is choosing the goal for the user is concrete. That gate was later measured
# against this checkpoint, found to contribute nothing, and deleted.
#
# Denies once, then gets out of the way. The denial is a checkpoint the model
# clears itself by retrying -- not a veto -- so the cost of a cleared check is one
# retried Edit. A non-blocking additionalContext was tried first and was ignored:
# by the first edit the decision is already made, and a nudge does not reverse it.
#
# Fires at most once per (request, agent): subagents share the parent's session_id
# AND prompt_id, so agent_id is part of the key. Without it, whichever agent edited
# first consumed the check for everyone.
#
# PreToolUse stdout goes to the debug log only, so this emits JSON.
input=$(cat)

sid=$(printf '%s' "$input" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
pid=$(printf '%s' "$input" | sed -n 's/.*"prompt_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$sid" ] || sid="nosession"
[ -n "$pid" ] || pid="noprompt"

# Subagents share the parent's session_id AND prompt_id, so keying on those alone
# lets whoever edits first consume the checkpoint for everyone: a parent that makes
# one trivial edit and then delegates the real implementation leaves the subagent
# unchecked, and with parallel subagents only one is checked. Key on agent_id too,
# so the parent and each subagent each get exactly one.
aid=$(printf '%s' "$input" | sed -n 's/.*"agent_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -n "$aid" ] || aid="main"

marker="${TMPDIR:-/tmp}/premise-edit.$(id -u).${sid}.${pid}.${aid}"

# Already asked for this prompt: stay out of the way.
[ -f "$marker" ] && exit 0

: > "$marker" 2>/dev/null || true
cat "${CLAUDE_PLUGIN_ROOT}/hooks/precheck.json"
