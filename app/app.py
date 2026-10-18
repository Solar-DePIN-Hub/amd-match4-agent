#!/usr/bin/env python3
"""AMD AI League Match 4 web-retrieval agent (v0).

Accepted invocations (tolerant until the official Match 4 contract is confirmed):
  python3 /app/app.py --query-id q01 --query "Latest version of requests on PyPI?" [--url https://...]
  python3 /app/app.py --input tasks.json        # list of {"id"|"query_id", "query"|"question", "url"|"start_url"}
  python3 /app/app.py --serve                   # resident model server (container CMD)
  python3 /app/app.py --index ...               # accepted no-op (MC3-style startup hook)
Writes /app/output/<query-id>_output.json:
  {"answer": "<value or empty>", "sources": [url], "citations": [url], "source_url": url, "confidence": x}
"""
from __future__ import annotations
import argparse, json, os, sys, time

T0 = time.monotonic()
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT = os.environ.get("AGENT_OUTPUT", "/app/output")
BUDGET = float(os.environ.get("AGENT_BUDGET_S", "25"))   # hard per-query cap is 30 s


def write(qid: str, r: dict, extra: bool = True):
    os.makedirs(OUT, exist_ok=True)
    src = [s for s in (r.get("sources") or []) if s]
    o = {"answer": r.get("answer") or "", "sources": src, "citations": src,
         "source_url": src[0] if src else "", "confidence": r.get("confidence", 0.0)}
    if extra:
        for k in ("trace", "seconds", "error"):
            if k in r:
                o[k] = r[k]
    path = os.path.join(OUT, f"{qid}_output.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(o, f, ensure_ascii=False)
    os.replace(tmp, path)  # single atomic write
    return path


def _alive(pidfile: str) -> bool:
    try:
        os.kill(int(open(pidfile).read().strip() or 0), 0)
        return True
    except Exception:
        return False


def ensure_server() -> str:
    """Make sure the resident GPU server is running (robust to a harness that overrides the image CMD).
    Returns 'ready' | 'starting' | 'spawned' | 'off'."""
    from agent import server
    if os.path.exists(server.READY):
        return "ready"
    if os.path.exists(server.STARTING) and _alive(server.STARTING):
        return "starting"
    if os.environ.get("AGENT_LLM", "none").lower() == "none" or os.environ.get("AGENT_NO_SPAWN"):
        return "off"
    import subprocess
    log = open(os.environ.get("AGENT_SERVER_LOG", "/tmp/agent-server.log"), "ab")
    subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), "--serve"], stdout=log, stderr=log,
                     stdin=subprocess.DEVNULL, start_new_session=True, cwd=HERE)
    t = time.monotonic()
    while not os.path.exists(server.STARTING) and time.monotonic() - t < 3:
        time.sleep(0.05)
    return "spawned"


def wait_ready(limit_s: float) -> bool:
    from agent import server
    t = time.monotonic()
    while time.monotonic() - t < limit_s:
        if os.path.exists(server.READY):
            return True
        if not (os.path.exists(server.STARTING) and _alive(server.STARTING)):
            return False  # server died (see /tmp/agent-server.log)
        time.sleep(0.5)
    return os.path.exists(server.READY)


def answer(q: str, url: str | None) -> dict:
    from agent import server
    try:
        ensure_server()
    except Exception:
        pass
    left = BUDGET - (time.monotonic() - T0)
    wait_until = time.monotonic() + min(5.0, left / 3)
    while (os.path.exists(server.STARTING) and time.monotonic() < wait_until
           and not os.path.exists(server.READY)):
        time.sleep(0.2)
    if os.path.exists(server.READY):
        try:
            left = BUDGET - (time.monotonic() - T0)
            return server.ask({"query": q, "url": url, "budget": left - 1.0}, timeout=left)
        except Exception as e:
            err = repr(e)
        else:
            err = None
    # no server: rule-based in-process (never loads a model per query)
    from agent.agent import Agent
    from agent.llm import NoLLM
    left = BUDGET - (time.monotonic() - T0)
    return Agent(NoLLM()).run(q, url, max(1.0, left - 0.5))


def main(argv=None):
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("pos", nargs="?")
    ap.add_argument("--query", "--question", "--q", "--task", "--prompt", dest="query")
    ap.add_argument("--query-id", "--query_id", "--id", "--task-id", dest="qid")
    ap.add_argument("--url", "--start-url", "--start_url", "--website", "--site", dest="url")
    ap.add_argument("--input", "--input-file", "--tasks", dest="input")
    ap.add_argument("--output-dir", "--output", dest="out")
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--index", nargs="?", const="")
    ap.add_argument("--corpus")
    ap.add_argument("--warmup", "--wait-ready", action="store_true")
    a, _ = ap.parse_known_args(argv)
    if a.out:
        OUT = a.out
    if a.serve:
        from agent import server
        server.main()
        return
    tasks = []
    if a.input:
        d = json.load(open(a.input))
        items = d if isinstance(d, list) else d.get("tasks") or d.get("queries") or [d]
        for i, t in enumerate(items, 1):
            tasks.append((t.get("query_id") or t.get("id") or f"query_{i:02d}",
                          t.get("query") or t.get("question") or t.get("task") or "",
                          t.get("url") or t.get("start_url")))
    elif a.query or a.pos:
        tasks.append((a.qid or "query_01", a.query or a.pos, a.url))
    elif os.environ.get("AGENT_QUERY") or os.environ.get("QUERY"):
        tasks.append((os.environ.get("AGENT_QUERY_ID") or os.environ.get("QUERY_ID") or "query_01",
                      os.environ.get("AGENT_QUERY") or os.environ.get("QUERY"),
                      os.environ.get("AGENT_URL") or os.environ.get("START_URL") or os.environ.get("URL")))
    elif a.index is not None or a.warmup:
        # startup hook (MC3 style): bring the resident model up inside the startup budget, not a query's
        st = ensure_server()
        ok = st == "off" or wait_ready(float(os.environ.get("AGENT_INDEX_WAIT_S", "540")))
        print(json.dumps({"indexed": 0, "server": st, "ready": ok, "note": "live web agent; nothing to index"}))
        return
    for qid, q, url in tasks:
        write(qid, {"answer": "", "sources": [], "confidence": 0.0})  # valid file even if we get killed
        try:
            r = answer(q, url)
        except Exception as e:
            r = {"answer": "", "sources": [], "confidence": 0.0, "error": repr(e)}
        write(qid, r)
        print(json.dumps({"id": qid, "answer": r.get("answer"), "sources": r.get("sources")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
