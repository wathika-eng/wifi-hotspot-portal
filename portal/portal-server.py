#!/usr/bin/env python3
"""Minimal HTTPS-Funnel landing page for the local openNDS gateway."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import parse_qs
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from payment.kcb_buni import KCBError, stk_push

GATEWAY_URL = os.environ.get("PORTAL_GATEWAY_URL", "http://192.168.12.1:2050/")
LISTEN_HOST = os.environ.get("PORTAL_LISTEN_HOST", "127.0.0.1")
LISTEN_PORT = int(os.environ.get("PORTAL_LISTEN_PORT", "8080"))
LEASE_ROOT = Path(os.environ.get("PORTAL_LEASE_ROOT", "/tmp"))
PUBLIC_URL = os.environ.get("PORTAL_PUBLIC_URL", "https://wathi.tail433a8c.ts.net").rstrip("/")
PAYMENTS = {}


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


def captive_for_connected_clients():
    """Return false once every current DHCP lease is trusted by openNDS.

    Funnel does not preserve the phone's hotspot IP, so the CAPPORT endpoint
    cannot make a per-device decision. For this MVP, the safe useful behavior
    is captive while any current lease is untrusted and non-captive when all
    current leases are trusted.
    """
    leases = sorted(LEASE_ROOT.glob("create_ap.*/dnsmasq.leases"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not leases:
        return True
    macs = set()
    for row in leases[0].read_text().splitlines():
        fields = row.split()
        if len(fields) >= 3:
            macs.add(fields[1].lower())
    if not macs:
        return True
    result = subprocess.run(["/usr/bin/ndsctl", "json"], capture_output=True, text=True, check=False)
    try:
        trusted = {str(mac).lower() for mac in json.loads(result.stdout).get("trusted", [])}
    except json.JSONDecodeError:
        return True
    return not macs.issubset(trusted)

class PortalHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - stdlib handler API
        if self.path.startswith("/healthz"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok\n")
            return
        if self.path in ("/", "/capport"):
            body = json.dumps({
                "captive": captive_for_connected_clients(),
                "user-portal-url": f"{PUBLIC_URL}/portal",
                "venue-info-url": f"{PUBLIC_URL}/portal",
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/captive+json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/payment/kcb/status?"):
            invoice = parse_qs(self.path.split("?", 1)[1]).get("invoice", [""])[0]
            payment = PAYMENTS.get(invoice, {"status": "unknown"})
            body = json.dumps({"invoice": invoice, **payment}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
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
<p>Choose access, enter the M-Pesa number, and approve the KCB prompt on your phone.</p>
<form method="post" action="/pay"><label>M-Pesa number<br><input name="phoneNumber" inputmode="tel" placeholder="254700000000" required></label><br><label>Amount (KES)<br><input name="amount" inputmode="decimal" value="10" required></label><br><button type="submit">Pay and activate Wi-Fi</button></form>
</html>""".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802 - stdlib handler API
        if self.path == "/pay":
            length = int(self.headers.get("Content-Length", "0"))
            fields = parse_qs(self.rfile.read(length).decode())
            phone = fields.get("phoneNumber", [""])[0].strip()
            amount = fields.get("amount", [""])[0].strip()
            if not phone or not amount.isdigit() or int(amount) < 1:
                self.send_error(400, "Enter a valid phone number and amount")
                return
            invoice = f"{os.environ.get('KCB_BUNI_TILL_NUMBER', 'WIFI')}-{uuid4().hex[:12]}"
            callback = os.environ.get("KCB_BUNI_CALLBACK_URL", f"{PUBLIC_URL}/payment/kcb/callback")
            try:
                response = stk_push(phone, amount, invoice, callback)
            except KCBError as exc:
                self.send_error(502, str(exc))
                return
            PAYMENTS[invoice] = {"status": "pending", "phone": phone[-4:], "amount": amount, "response": response}
            provider_ref = response.get("response", {}).get("MerchantRequestID") if isinstance(response, dict) else None
            if provider_ref:
                PAYMENTS[provider_ref] = PAYMENTS[invoice]
            body = f"""<!doctype html><meta name="viewport" content="width=device-width"><title>Approve payment</title><style>body{{font:16px system-ui;max-width:34rem;margin:12vh auto;padding:1.5rem}}.box{{padding:1rem;background:#eef6ff;border-radius:.6rem}}p{{line-height:1.5}}</style><h1>Approve the M-Pesa prompt</h1><div class="box">A payment prompt was sent to the number ending in <b>{phone[-4:]}</b>.</div><p>Approve it on your phone. This page will update after KCB confirms the callback.</p><p id="status">Waiting for payment confirmation…</p><script>async function poll(){{const r=await fetch('/payment/kcb/status?invoice={invoice}');const d=await r.json();document.querySelector('#status').textContent='Payment status: '+d.status;if(d.status==='paid')location.href='/activated';else setTimeout(poll,3000)}}poll()</script>""".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/payment/kcb/callback":
            length = int(self.headers.get("Content-Length", "0"))
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                callback = payload["Body"]["stkCallback"]
                invoice = callback.get("MerchantRequestID") or callback.get("CheckoutRequestID")
                success = int(callback.get("ResultCode", 1)) == 0
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                self.send_error(400, "Invalid KCB callback")
                return
            if invoice in PAYMENTS:
                PAYMENTS[invoice]["status"] = "paid" if success else "failed"
                PAYMENTS[invoice]["callback"] = payload
                if success:
                    client = connected_client()
                    if client:
                        subprocess.run(["/usr/bin/ndsctl", "auth", client[0], "60", "512", "2048", "0", "0", invoice], check=False)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"received":true}')
            return
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
        body = b"Wi-Fi activated"
        self.send_response(302)
        self.send_header("Location", "http://connectivitycheck.gstatic.com/generate_204")
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)

if __name__ == "__main__":
    ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), PortalHandler).serve_forever()
