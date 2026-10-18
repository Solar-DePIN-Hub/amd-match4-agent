#!/usr/bin/env bash
# Run on the AMD notebook after `docker run -d --name m4 IMAGE`: measures startup, per-query time, VRAM.
set -euo pipefail
C=${1:-m4}
t=$(date +%s); until docker exec $C test -f /tmp/agent.sock.ready; do sleep 2; [ $(( $(date +%s)-t )) -gt 600 ] && { echo "STARTUP > 10 min"; exit 1; }; done
echo "startup: $(( $(date +%s)-t )) s"; docker exec $C cat /tmp/agent.sock.ready; echo
( while true; do (amd-smi metric --mem-usage 2>/dev/null || rocm-smi --showmeminfo vram) | grep -iE "used|vram" >> /tmp/vram.log; sleep 3; done ) & P=$!
docker cp tests/queries.json $C:/tmp/q.json
python3 - "$C" <<'PY'
import json,subprocess,sys,time
c=sys.argv[1]
for q in json.load(open("tests/queries.json"))[:10]:
    cmd=["docker","exec",c,"python3","/app/app.py","--query-id",q["id"],"--query",q["query"]]+(["--url",q["url"]] if q.get("url") else [])
    t=time.time(); subprocess.run(cmd,capture_output=True,timeout=35); dt=time.time()-t
    o=json.loads(subprocess.run(["docker","exec",c,"cat",f"/app/output/{q['id']}_output.json"],capture_output=True,text=True).stdout)
    print(f"{dt:5.1f}s {q['id']} got={o['answer']!r} exp={q['expected']!r} {o.get('trace',{}).get('steps')}")
PY
kill $P; echo "VRAM samples:"; tail -5 /tmp/vram.log
