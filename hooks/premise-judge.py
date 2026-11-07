#!/usr/bin/env python3
"""PreToolUse hook on code-editing tools: an independent judge for the first edit.

The previous version denied the first edit once and let the editing model decide
for itself whether the request had a success criterion. Measured on real sessions,
it retried straight through 67 of 80 denials and asked the user 0 times: the model
that already chose the implementation is the wrong one to judge whether a goal was
set. This version hands that judgement to a separate model that sees only the
conversation and the pending edit, not the editor's reasoning.

Per (session, request) for the main agent:
  - no verdict yet -> run the judge once and cache the verdict
  - verdict "ok"  -> allow every edit in this request
  - verdict "ask" -> deny every edit in this request; retrying does not clear it.
                     The next user message is a new request and is judged afresh.
Subagents are not judged: their brief comes from the parent, which already was.
Any failure of the judge itself (no `claude` CLI, timeout, bad output) allows the
edit -- a broken guard must not block work.
"""
import json
import os
import subprocess
import sys
import tempfile

MODEL = os.environ.get("PREMISE_JUDGE_MODEL", "sonnet")
TIMEOUT = int(os.environ.get("PREMISE_JUDGE_TIMEOUT", "80"))
MAX_CONTEXT = 6000
MAX_EDIT = 1500

RUBRIC = """You judge one thing: before this code edit, did the USER establish what the change
is supposed to achieve? You are not the one editing. Be strict; the editor is biased
toward proceeding.

A success criterion counts ONLY as one of:
  (a) a number or threshold ("under 300ms", "half the queries")
  (b) a named test or assertion to make pass
  (c) an exact expected behavior or output ("should return 400, not 500")
  (d) the change and where it goes, named by the user -- or proposed concretely by the
      assistant earlier in the conversation and then approved by the user ("ok", "進めて",
      "それでお願い" right after a concrete proposal counts)
These do NOT count: a direction with no target ("faster", "cleaner", "いい感じに",
"最適化して"), or a symptom with no target ("it's slow", "なんか遅い").

If there is no criterion, the edit may still be fine if it is on this CLOSED list:
a typo or spelling fix, a rename, formatting or whitespace, a comment, restoring
something the user explicitly named, or writing to a scratch/temp/memory/notes file
that is not product code. Performance refactors, N+1 fixes, caching, restructuring,
error-handling changes and API changes are NOT on the list.

Answer ok=true if a criterion is present or the edit is on the closed list.
Otherwise ok=false, and in `fork` write ONE short question for the user, in the
user's language, that names the concrete choice the editor would otherwise make
for them."""

SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "reason": {"type": "string"},
        "fork": {"type": "string"},
    },
    "required": ["ok", "reason"],
}


def allow():
    sys.exit(0)


def deny(fork, reason):
    msg = (
        "premise: an independent reviewer found no success criterion for this request "
        f"({reason}). Do not retry this edit and do not work around it with another tool; "
        "retrying will be denied again. Ask the user this, in one line, and wait:\n"
        f"{fork}\n"
        "Their reply starts a new request and is reviewed again."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": msg,
    }}))
    sys.exit(0)


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


def conversation(path):
    """Last turns of user and assistant prose, oldest first, newest kept."""
    turns = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("isMeta") or d.get("isSidechain"):
                    continue
                role = d.get("type")
                if role not in ("user", "assistant"):
                    continue
                t = text_of((d.get("message") or {}).get("content")).strip()
                if t:
                    turns.append(f"[{role}] {t}")
    except OSError:
        return ""
    out, size = [], 0
    for t in reversed(turns):
        t = t[:2000]
        if size + len(t) > MAX_CONTEXT:
            break
        out.append(t)
        size += len(t)
    return "\n\n".join(reversed(out))


def pending_edit(tool_name, tool_input):
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or "?"
    body = (tool_input.get("new_string") or tool_input.get("content")
            or tool_input.get("new_source") or json.dumps(tool_input.get("edits", ""))[:MAX_EDIT])
    return f"{tool_name} {path}\n{str(body)[:MAX_EDIT]}"


def judge(convo, edit):
    prompt = (f"{RUBRIC}\n\n=== Conversation (most recent last) ===\n{convo}\n\n"
              f"=== Pending edit ===\n{edit}\n")
    args = ["claude", "-p", prompt, "--output-format", "json",
            "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
            "--tools", "", "--no-session-persistence", "--max-turns", "3",
            "--model", MODEL, "--json-schema", json.dumps(SCHEMA)]
    env = dict(os.environ, PREMISE_JUDGE="1", CLAUDE_CODE_SKIP_PROMPT_HISTORY="1")
    r = subprocess.run(args, capture_output=True, text=True, timeout=TIMEOUT, env=env)
    out = json.loads(r.stdout)
    msgs = out if isinstance(out, list) else [out]
    result = next(m for m in reversed(msgs) if isinstance(m, dict) and m.get("type") == "result")
    verdict = result.get("structured_output")
    if not isinstance(verdict, dict) or "ok" not in verdict:
        raise ValueError(f"no structured verdict: {str(result.get('result'))[:200]}")
    return verdict


def main():
    if os.environ.get("PREMISE_JUDGE"):
        allow()
    try:
        data = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        allow()
    if data.get("agent_id"):
        allow()

    sid = data.get("session_id") or "nosession"
    pid = data.get("prompt_id") or "noprompt"
    cache = os.path.join(tempfile.gettempdir(), f"premise-verdict.{os.getuid()}.{sid}.{pid}")

    try:
        with open(cache, encoding="utf-8") as f:
            v = json.load(f)
        if v.get("ok"):
            allow()
        deny(v.get("fork", ""), v.get("reason", ""))
    except (OSError, ValueError):
        pass

    try:
        v = judge(conversation(data.get("transcript_path", "")),
                  pending_edit(data.get("tool_name", ""), data.get("tool_input") or {}))
    except Exception as e:  # noqa: BLE001 -- any judge failure fails open
        sys.stderr.write(f"premise: judge unavailable, allowing edit ({type(e).__name__}: {e})\n")
        v = {"ok": True, "reason": "judge unavailable"}

    try:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(v, f, ensure_ascii=False)
    except OSError:
        pass
    if v.get("ok"):
        allow()
    deny(v.get("fork") or "What exactly should this change achieve?", v.get("reason", ""))


if __name__ == "__main__":
    main()
