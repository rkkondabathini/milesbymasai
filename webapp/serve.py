"""Local dev server: python3 webapp/serve.py [port]  (serves webapp/dist with caching disabled)"""
import http.server, sys
from functools import partial
from pathlib import Path


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        super().end_headers()


port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
handler = partial(NoCache, directory=str(Path(__file__).parent / "dist"))
http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
