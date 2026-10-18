#!/usr/bin/python3
"""Local demo server: the HTML report plus a "Run live" button.

    /usr/bin/python3 app.py            # then open http://127.0.0.1:8765

Run live = build a fresh benchmark (seed / size you choose) -> official SKY130 DRC deck ->
triage (with or without GLM) -> rebuild the page. Standard library only; listens on localhost.
"""
import json
import os
import subprocess
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(ROOT, "out", "site")
PY = sys.executable
PORT = int(os.environ.get("PORT", "8765"))

STATE = {"running": False, "finished_ok": False, "steps": []}
LOCK = threading.Lock()


def plan(seed, max_per_type, use_llm):
    run_cmd = [PY, "run.py", "work/bench.lyrdb", "--out", "out/bench_live.md"] + ([] if use_llm else ["--no-llm"])
    return [
        ("Build test chip (SKY130 standard cells)", [PY, "tools/make_testchip.py"]),
        (f"Inject violations + legal controls (seed {seed})",
         [PY, "tools/inject_random.py", "--seed", str(seed), "--max-per-type", str(max_per_type),
          "--min-per-type", str(min(10, max_per_type))]),
        ("Run official SKY130 KLayout DRC deck", ["zsh", "tools/run_drc.sh", "work/bench.gds", "work/bench.lyrdb"]),
        ("Triage: group, measure, retrieve" + (", explain with GLM" if use_llm else " (model off)"), run_cmd),
        ("Render layout snapshots, score against ground truth, rebuild page",
         [PY, "-m", "drc_copilot.site", "--gds", "work/bench.gds", "--lyrdb", "work/bench.lyrdb",
          "--run", "out/bench_live.json", "--truth", "work/bench_truth.json", "--out", SITE]),
    ]


def worker(steps):
    ok = True
    for i, (name, cmd) in enumerate(steps):
        with LOCK:
            STATE["steps"][i]["state"] = "run"
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        last = (p.stdout.strip().splitlines() or [""])[-1].replace(ROOT + os.sep, "")[:160]
        with LOCK:
            STATE["steps"][i]["state"] = "done" if p.returncode == 0 else "fail"
            STATE["steps"][i]["note"] = last if p.returncode == 0 else (p.stderr.strip().splitlines() or ["failed"])[-1][:160]
        if p.returncode != 0:
            ok = False
            break
    with LOCK:
        STATE["running"] = False
        STATE["finished_ok"] = ok


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/status"):
            with LOCK:
                return self._json(STATE)
        return super().do_GET()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        if not self.path.startswith("/api/run"):
            return self._json({"error": "not found"}, 404)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
            seed = int(req.get("seed", 20261011))
            max_per = max(1, min(80, int(req.get("max_per_type", 35))))
            use_llm = bool(req.get("use_llm", True))
        except (ValueError, TypeError):
            return self._json({"error": "bad request"}, 400)
        with LOCK:
            if STATE["running"]:
                return self._json({"error": "already running"}, 409)
            steps = plan(seed, max_per, use_llm)
            STATE.update(running=True, finished_ok=False,
                         steps=[{"name": s[0], "state": "wait", "note": ""} for s in steps])
        threading.Thread(target=worker, args=(steps,), daemon=True).start()
        return self._json({"ok": True})


def main():
    if not os.path.exists(os.path.join(SITE, "index.html")):
        print("No report yet: building one from the existing benchmark ...")
        subprocess.run([PY, "-m", "drc_copilot.site", "--gds", "work/bench.gds", "--lyrdb", "work/bench.lyrdb",
                        "--run", "out/bench_glm.json", "--truth", "work/bench_truth.json", "--out", SITE],
                       cwd=ROOT, check=True)
    print(f"DRC Copilot demo: http://127.0.0.1:{PORT}  (Ctrl-C to stop)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
