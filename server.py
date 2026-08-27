#!/usr/bin/env python3
"""Proto server: static files + POST /log -> runs/<runId>.jsonl (telemetry)."""
import json, os, re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(ROOT, "runs")
os.makedirs(RUNS, exist_ok=True)

class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        # minimal Range support so <audio> streaming works
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if rng and os.path.isfile(path):
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m and (m.group(1) or m.group(2)):
                size = os.path.getsize(path)
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                else:  # suffix range: last N bytes
                    start = max(0, size - int(m.group(2)))
                    end = size - 1
                end = min(end, size - 1)
                if start <= end:
                    f = open(path, "rb"); f.seek(start)
                    self.send_response(206)
                    self.send_header("Content-Type", self.guess_type(path))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                    self.send_header("Content-Length", str(end - start + 1))
                    self.end_headers()
                    self._range_span = end - start + 1
                    return f
                # unsatisfiable (suffix -0, start past EOF, start > end)
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
        return super().send_head()

    def copyfile(self, source, outputfile):
        span = getattr(self, "_range_span", None)
        if span is None:
            return super().copyfile(source, outputfile)
        self._range_span = None
        remaining = span
        while remaining > 0:
            chunk = source.read(min(65536, remaining))
            if not chunk: break
            outputfile.write(chunk)
            remaining -= len(chunk)

    def do_POST(self):
        if self.path.startswith("/analysis"):
            # whole-song band data flat file -> analysis/<name>
            try:
                from urllib.parse import urlparse, parse_qs
                q = parse_qs(urlparse(self.path).query)
                name = re.sub(r"[^A-Za-z0-9._-]", "_", q.get("name", ["analysis.csv"])[0])[:120]
                n = int(self.headers.get("Content-Length", 0))
                data = self.rfile.read(n)
                adir = os.path.join(ROOT, "analysis")
                os.makedirs(adir, exist_ok=True)
                with open(os.path.join(adir, name), "wb") as f:
                    f.write(data)
                self.send_response(204); self.end_headers()
            except Exception as e:
                self.send_error(400, str(e))
            return
        if self.path != "/log":
            self.send_error(404); return
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n))
            run_id = re.sub(r"[^A-Za-z0-9._-]", "_", str(payload.get("runId", "run")))[:80]
            with open(os.path.join(RUNS, run_id + ".jsonl"), "a") as f:
                f.write(json.dumps(payload) + "\n")
            self.send_response(204); self.end_headers()
        except Exception as e:
            self.send_error(400, str(e))
    def log_message(self, fmt, *a):
        import sys; print(self.command, self.path, self.headers.get('Range'), fmt % a, file=sys.stderr)

if __name__ == "__main__":
    os.chdir(ROOT)
    ThreadingHTTPServer(("127.0.0.1", 8100), Handler).serve_forever()
