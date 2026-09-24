#!/usr/bin/env python3
"""Minimal HTTPS-Funnel landing page for the local openNDS gateway."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import parse_qs

GATEWAY_URL = os.environ.get("PORTAL_GATEWAY_URL", "http://192.168.12.1:2050/")
LISTEN_HOST = os.environ.get("PORTAL_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("PORTAL_LISTEN_PORT", "8080"))
LEASE_ROOT = Path(os.environ.get("PORTAL_LEASE_ROOT", "/tmp"))


def connected_client():
    leases = sorted(LEASE_ROOT.glob("create_ap.*/dnsmasq.leases"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not leases:
        return None
    rows = leases[0].read_text().splitlines()
    for row in rows:
        fields = row.split()
        if len(fields) >= 3:
            return fields[1], fields[2]
    return None

class PortalHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler API
        if self.path.startswith("/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return
        if self.path in ("/", "/capport"):
            origin = os.environ.get("PORTAL_PUBLIC_URL", "https://wathi.tail433a8c.ts.net")
            body = json.dumps({
                "captive": True,
                "user-portal-url": f"{origin}/portal",
                "venue-info-url": f"{origin}/portal",
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/captive+json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        body = f"""<!doctype html>
<html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wi-Fi sign in</title>
<style>body{{font:16px system-ui,sans-serif;max-width:34rem;margin:12vh auto;padding:1.5rem}}
button{{width:100%;padding:1rem;border:0;border-radius:.6rem;background:#146ef5;color:#fff;font-size:1rem}}
p{{line-height:1.5;color:#444}}</style>
<h1>Sign in to Wi-Fi</h1>
<p>Connect to this hotspot to continue. For this MVP, activation is simulated; M-Pesa checkout will be added next.</p>
<form method="post" action="/activate"><button type="submit">Activate Wi-Fi</button></form>
</html>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802 - stdlib handler API
        if self.path != "/activate":
            self.send_error(404)
            return
        client = connected_client()
        if not client:
            self.send_error(503, "No hotspot client lease found")
            return
        client_mac, client_ip = client
        result = subprocess.run(
            ["/usr/bin/ndsctl", "trust", client_mac],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            current = subprocess.run(
                ["/usr/bin/ndsctl", "json"], capture_output=True, text=True, check=False
            )
            if client_mac.lower() in current.stdout.lower():
                result = None
        if result is not None and result.returncode != 0:
            self.send_error(502, result.stderr.strip() or "openNDS authorization failed")
            return
        body = b"<!doctype html><meta name=viewport content=width=device-width><h1>Wi-Fi activated</h1><p>MVP access is enabled. Payment is not connected yet.</p>"
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
