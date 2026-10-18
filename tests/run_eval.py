#!/usr/bin/env python3
"""Local CPU harness: runs app.py as a NEW PROCESS per query (like the grader), 30 s hard kill,
scores with the official normalisation (UPPERCASE, strip spaces and - . · _), writes results.md/json."""
import json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "app", "app.py")
OUT = os.environ.get("EVAL_OUT", "/tmp/m4-eval-out")


def norm(s):
    return re.sub(r"[\s\-.·_]", "", (s or "").upper())


def main():
    qs = json.load(open(os.path.join(HERE, "queries.json")))
    only = sys.argv[1:]
    rows, t_all = [], time.time()
    for q in qs:
        if only and q["id"] not in only:
            continue
        cmd = [sys.executable, APP, "--query-id", q["id"], "--query", q["query"]]
        if q.get("url"):
            cmd += ["--url", q["url"]]
        t = time.time()
        try:
            subprocess.run(cmd, timeout=30, capture_output=True, env=dict(os.environ, AGENT_OUTPUT=OUT))
            timeout = False
        except subprocess.TimeoutExpired:
            timeout = True
        dt = time.time() - t
        try:
            o = json.load(open(os.path.join(OUT, f"{q['id']}_output.json")))
        except Exception:
            o = {"answer": "<no file>", "sources": []}
        ok = (not timeout) and dt <= 30 and norm(o.get("answer")) == norm(q["expected"])
        rows.append(dict(set=q.get("set", "dev"), id=q["id"], query=q["query"], url=q.get("url"), expected=q["expected"],
                         got=o.get("answer"), source=(o.get("sources") or [""])[0], ok=ok, sec=round(dt, 1),
                         via=" ".join(o.get("trace", {}).get("steps", [])[-1:])))
        print(f"{'PASS' if ok else 'FAIL'} {q['id']} {dt:5.1f}s got={o.get('answer')!r} exp={q['expected']!r}", flush=True)
    n, k = len(rows), sum(r["ok"] for r in rows)
    secs = sorted(r["sec"] for r in rows)
    summ = dict(passed=k, total=n, accuracy=round(k / max(1, n), 3), p50=secs[n // 2] if n else 0,
                max=secs[-1] if n else 0, total_sec=round(time.time() - t_all, 1),
                llm=os.environ.get("AGENT_LLM", "none"), date=time.strftime("%Y-%m-%d %H:%M %Z"))
    for st in ("dev", "holdout"):
        rr = [r for r in rows if r["set"] == st]
        summ[st] = f"{sum(r['ok'] for r in rr)}/{len(rr)}"
    json.dump(dict(summary=summ, rows=rows), open(os.path.join(HERE, "results.json"), "w"), indent=1, ensure_ascii=False)
    with open(os.path.join(HERE, "results.md"), "w") as f:
        f.write(f"# Local eval ({summ['date']}, LLM={summ['llm']}, CPU box)\n\n"
                f"**{k}/{n} = {summ['accuracy']*100:.0f}%**, p50 {summ['p50']} s, max {summ['max']} s, "
                f"whole run {summ['total_sec']} s (dev {summ['dev']}, holdout {summ['holdout']})\n\n| set | id | ok | sec | expected | got | source | last step |\n|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            f.write(f"| {r['set']} | {r['id']} | {'✅' if r['ok'] else '❌'} | {r['sec']} | {r['expected']} | {r['got']} | {r['source']} | {r['via']} |\n")
    print(json.dumps(summ))


if __name__ == "__main__":
    main()
