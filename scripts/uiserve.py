"""
uiserve.py — static file server for the Orbit UI.

Binds 127.0.0.1 only and sends Cache-Control: no-store so browsers can
never serve a stale index.html or backend.js.

Run: python scripts/uiserve.py <port> <directory>
"""

import functools
import http.server
import sys

PORT = int(sys.argv[1])
DIRECTORY = sys.argv[2]


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


if __name__ == "__main__":
    handler = functools.partial(Handler, directory=DIRECTORY)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    sys.stderr.write(f"Orbit UI serving {DIRECTORY} on http://127.0.0.1:{PORT}\n")
    server.serve_forever()
