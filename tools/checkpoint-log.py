#!/usr/bin/env python3
"""Extract every premise checkpoint from Claude Code transcripts.

The checkpoint already leaves a full record in the transcript, so nothing needs to
be instrumented and the plugin carries no telemetry. This reads what is there.

Per firing it reports whether the model cleared the check and wrote code anyway,
or stopped, plus the request that triggered it and what you said next -- which is
the part that tells you whether the question was wanted. Judging that is yours;
this script only finds them, because a classifier here would be one more thing to
maintain and to be wrong.

  python3 tools/checkpoint-log.py                # all projects
  python3 tools/checkpoint-log.py --project foo  # substring match on project dir
  python3 tools/checkpoint-log.py --asked-only   # only the ones that asked you

Two limits, both measured rather than assumed:

1. Firings inside a subagent are invisible. A subagent's context is not stored in
   the parent's transcript, so a checkpoint that fires there leaves nothing to
   read here -- verified by logging from inside the hook while the parent
   transcript showed zero hits.

2. It only sees requests where an edit was actually attempted. If the model
   settles the framing before reaching for Edit, the hook never fires and there
   is no record. On this repo's own test transcripts that was 12 of 48 requests.

Neither limit affects the over-asking rate, which is by definition about firings.
Both matter if you try to use this to count how often the plugin stopped you.
"""
import argparse, json, glob, os, sys
from collections import defaultdict

def load(path):
    out = []
    with open(path, errors="replace") as f:
        for line in f:
            line = line.strip()
            if line:
                try: out.append(json.loads(line))
                except ValueError: pass
    return out

def user_text(rec):
    """The text the human typed, or None for tool results and meta records."""
    if rec.get("type") != "user" or rec.get("isMeta"):
        return None
    c = rec.get("message", {}).get("content")
    if isinstance(c, str):
        return c.strip() or None
    if isinstance(c, list):
        parts = [b.get("text", "") for b in c
                 if isinstance(b, dict) and b.get("type") == "text"]
        return ("".join(parts).strip() or None)
    return None

def scan(path):
    recs = load(path)
    prompts = {}          # promptId -> what the user typed
    order = []            # promptIds in order
    fired = set()         # promptIds where the checkpoint fired
    wrote = set()         # promptIds with a successful Edit/Write after firing
    for i, r in enumerate(recs):
        pid = r.get("promptId")
        t = user_text(r)
        if t and pid and pid not in prompts:
            prompts[pid] = t
            order.append(pid)
        if r.get("type") != "user":
            continue
        c = r.get("message", {}).get("content")
        if not isinstance(c, list):
            continue
        for b in c:
            if not isinstance(b, dict) or b.get("type") != "tool_result":
                continue
            body = json.dumps(b.get("content"), ensure_ascii=False)
            if b.get("is_error") and "premise-check" in body:
                fired.add(pid)
            elif pid in fired and not b.get("is_error") and "has been updated" in body:
                wrote.add(pid)
    return prompts, order, fired, wrote

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="")
    ap.add_argument("--asked-only", action="store_true")
    ap.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
    a = ap.parse_args()

    rows, n_fired = [], 0
    for path in sorted(glob.glob(os.path.join(a.root, "*", "*.jsonl"))):
        proj = os.path.basename(os.path.dirname(path))
        if a.project and a.project not in proj:
            continue
        prompts, order, fired, wrote = scan(path)
        for n, pid in enumerate(order):
            if pid not in fired:
                continue
            n_fired += 1
            stopped = pid not in wrote
            if a.asked_only and not stopped:
                continue
            nxt = prompts.get(order[n + 1]) if n + 1 < len(order) else None
            rows.append((proj, "STOPPED" if stopped else "proceeded",
                         prompts.get(pid, "?"), nxt))

    for proj, outcome, req, nxt in rows:
        print(f"\n[{outcome}] {proj[-40:]}")
        print(f"  asked on : {req[:160]}")
        print(f"  you said : {nxt[:160] if nxt else '(nothing after)'}")

    stopped = sum(1 for r in rows if r[1] == "STOPPED")
    print(f"\n{'='*60}\nfired {n_fired} times")
    if n_fired:
        print(f"  stopped and asked : {stopped}")
        print(f"  cleared, wrote code: {n_fired - stopped}")
    print("\nOver-asking rate = of the STOPPED rows, how many 'you said' lines are")
    print("some form of 'just do it'. Read them; do not automate the judgement.")

if __name__ == "__main__":
    main()
