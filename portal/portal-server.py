#!/usr/bin/env python3
"""Minimal HTTPS-Funnel landing page for the local openNDS gateway."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os

GATEWAY_URL = os.environ.get("PORTAL_GATEWAY_URL", "http://192.168.12.1:2050/")
LISTEN_HOST = os.environ.get("PORTAL_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("PORTAL_LISTEN_PORT", "8080"))

class PortalHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler API
        if self.path.startswith("/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return
        body = f"""<!doctype html>
<html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wi-Fi sign in</title>
<style>body{{font:16px system-ui,sans-serif;max-width:34rem;margin:12vh auto;padding:1.5rem}}
button{{width:100%;padding:1rem;border:0;border-radius:.6rem;background:#146ef5;color:#fff;font-size:1rem}}
p{{line-height:1.5;color:#444}}</style>
<h1>Sign in to Wi-Fi</h1>
<p>Connect to this hotspot to continue. Payment and access activation will happen on the next screen.</p>
<p><a href="{GATEWAY_URL}"><button type="button">Continue to hotspot sign-in</button></a></p>
</html>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)

if __name__ == "__main__":
    ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), PortalHandler).serve_forever()
