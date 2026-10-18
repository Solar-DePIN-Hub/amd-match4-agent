"""Resident server: loads the LLM once (container CMD), answers over a unix socket."""
from __future__ import annotations
import json, os, socket, socketserver, threading, time

SOCK = os.environ.get("AGENT_SOCK", "/tmp/agent.sock")
READY = SOCK + ".ready"


def ask(payload: dict, timeout: float) -> dict:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(SOCK)
    s.sendall(json.dumps(payload).encode() + b"\n")
    buf = b""
    while not buf.endswith(b"\n"):
        chunk = s.recv(65536)
        if not chunk:
            break
        buf += chunk
    s.close()
    return json.loads(buf)


STARTING = SOCK + ".starting"


def main():
    open(STARTING, "w").write(str(os.getpid()))
    from .agent import Agent
    from . import llm
    t = time.time()
    model = llm.make()
    agent = Agent(model)
    print(f"[server] llm={model.name} loaded in {time.time()-t:.1f}s", flush=True)

    class H(socketserver.StreamRequestHandler):
        def handle(self):
            try:
                req = json.loads(self.rfile.readline())
                res = agent.run(req["query"], req.get("url"), float(req.get("budget", 25)))
            except Exception as e:
                res = {"answer": "", "sources": [], "confidence": 0.0, "error": repr(e)}
            self.wfile.write(json.dumps(res).encode() + b"\n")

    class S(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
        daemon_threads = True

    for p in (SOCK, READY):
        if os.path.exists(p):
            os.unlink(p)
    srv = S(SOCK, H)
    open(READY, "w").write(model.name)
    print("[server] ready", flush=True)
    srv.serve_forever()
