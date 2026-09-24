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


def normalize_phone(value):
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 10:
        digits = "254" + digits[1:]
    if len(digits) == 9 and digits.startswith(("7", "1")):
        digits = "254" + digits
    if len(digits) != 12 or not digits.startswith("254") or digits[3] not in "17":
        raise ValueError("Use a Kenyan mobile number such as 0712 345 678")
    return digits


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
        body = """<!doctype html>
<html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wi-Fi sign in</title>
<style>:root{{--ink:#10201f;--muted:#60706d;--paper:#f4f7f2;--card:#fff;--mint:#d7f3e6;--teal:#0e6b5b;--line:#d9e5df}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 85% 0,#d7f3e6 0,transparent 34%),var(--paper);color:var(--ink);font:16px/1.45 system-ui,-apple-system,sans-serif}}.shell{{max-width:680px;margin:auto;padding:26px 18px 30px}}.hero{{display:flex;gap:14px;align-items:flex-start;padding:10px 2px 24px}}.mark{{display:grid;place-items:center;width:42px;height:42px;border-radius:13px;background:var(--ink);color:#fff;font-weight:800;font-size:20px}}.kicker{{margin:0;color:var(--teal);font-weight:700}}h1{{font-size:clamp(2rem,8vw,3.5rem);line-height:1.02;letter-spacing:-.06em;margin:5px 0 10px;max-width:12ch}}.sub{{color:var(--muted);max-width:48ch;margin:0}}.panel{{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:20px;box-shadow:0 16px 40px #18372b12}}.section-head{{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:14px}}h2{{font-size:1.05rem;margin:0}}.secure{{color:var(--teal);font-size:.82rem;font-weight:700}}.plans{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:22px}}.plan{{text-align:left;width:100%;padding:14px 12px;border:1px solid var(--line);border-radius:15px;background:#fff;color:var(--ink);cursor:pointer;min-height:116px}}.plan.selected{{border:2px solid var(--teal);background:var(--mint);padding:13px 11px}}.plan span,.plan strong{{display:block}}.plan-time{{font-weight:700}}.plan strong{{font-size:1.35rem;margin:8px 0 4px}}.plan span:last-child{{font-size:.78rem;color:var(--muted)}}label{{font-weight:700;display:block;margin-bottom:7px}}.phone{{display:flex;border:1px solid var(--line);border-radius:12px;overflow:hidden;background:#fff}}.phone span{{padding:13px;color:var(--muted);background:#f4f7f2}}input{{font:inherit;border:0;outline:0;padding:13px;width:100%;background:transparent}}.phone:focus-within{{outline:3px solid #0e6b5b33}}.hint,.fine{{color:var(--muted);font-size:.82rem}}.cta{{width:100%;padding:15px;border:0;border-radius:12px;background:var(--teal);color:#fff;font-size:1rem;font-weight:800;cursor:pointer;margin-top:8px}}.cta:focus-visible,.plan:focus-visible{{outline:3px solid #10201f66;outline-offset:3px}}footer{{color:var(--muted);font-size:.8rem;text-align:center;padding:18px 0}}.dot{{display:inline-block;width:8px;height:8px;border-radius:50%;background:#2caa71;margin-right:5px}}@media(max-width:520px){{.plans{{grid-template-columns:1fr}}.plan{{min-height:0;display:grid;grid-template-columns:1fr auto;gap:2px 10px}.plan strong{{grid-column:2;grid-row:1/3;margin:0}.plan span:last-child{{grid-column:1}}}}</style>
<main class="shell"><header class="hero"><div class="mark">W</div><div><p class="kicker">MyAccessPoint</p><h1>Get online in one tap.</h1><p class="sub">Choose a pass, pay securely with M-Pesa, and your Wi-Fi starts when KCB confirms the payment.</p></div></header><section class="panel" aria-labelledby="passes"><div class="section-head"><h2 id="passes">Choose your pass</h2><span class="secure">KES · M-Pesa</span></div><div class="plans" role="radiogroup" aria-label="Wi-Fi passes"><button type="button" class="plan selected" data-minutes="30" data-amount="20" aria-pressed="true"><span class="plan-time">30 min</span><strong>KES 20</strong><span>Quick browse</span></button><button type="button" class="plan" data-minutes="60" data-amount="40" aria-pressed="false"><span class="plan-time">1 hour</span><strong>KES 40</strong><span>Best for a session</span></button><button type="button" class="plan" data-minutes="120" data-amount="70" aria-pressed="false"><span class="plan-time">2 hours</span><strong>KES 70</strong><span>Settle in</span></button></div><form method="post" action="/pay" id="pay-form"><input type="hidden" name="amount" id="amount" value="20"><input type="hidden" name="minutes" id="minutes" value="30"><label for="phone">M-Pesa number</label><div class="phone"><span>+254</span><input id="phone" name="phoneNumber" inputmode="tel" autocomplete="tel" placeholder="700 000 000" pattern="(254|0)?[17][0-9]{{8}}" required></div><p class="hint">You’ll receive a payment prompt on this phone.</p><button class="cta" type="submit">Pay KES <span id="price">20</span> and connect</button><p class="fine">By continuing, you agree to use this hotspot responsibly.</p></form></section><footer><span class="dot"></span> Fast connection · Secure checkout · No password needed</footer></main><script>const plans=[...document.querySelectorAll('.plan')],amount=document.querySelector('#amount'),minutes=document.querySelector('#minutes'),price=document.querySelector('#price');plans.forEach(plan=>plan.addEventListener('click',()=>{{plans.forEach(p=>{{p.classList.remove('selected');p.setAttribute('aria-pressed','false')}});plan.classList.add('selected');plan.setAttribute('aria-pressed','true');amount.value=plan.dataset.amount;minutes.value=plan.dataset.minutes;price.textContent=plan.dataset.amount}}));</script>
</html><style>body{{background:#f2f2f7;color:#1c1c1e;-webkit-font-smoothing:antialiased}}.mark{{background:#007aff}}.kicker,.secure{{color:#007aff}}.panel{{border-color:#d1d1d6;border-radius:20px;box-shadow:0 8px 24px #1c1c1e12}}.plan{{border-color:#d1d1d6}}.plan.selected{{border-color:#007aff;background:#e5f0ff}}.phone{{border-color:#d1d1d6}}.phone span{{background:#f2f2f7}}.cta{{background:#007aff}}.dot{{background:#34c759}}</style></html>""".replace("{{", "{").replace("}}", "}").encode()
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
            raw_phone = fields.get("phoneNumber", [""])[0].strip()
            amount = fields.get("amount", [""])[0].strip()
            try:
                phone = normalize_phone(raw_phone)
            except ValueError as exc:
                self.send_error(400, str(exc))
                return
            if not amount.isdigit() or int(amount) < 1:
                self.send_error(400, "Enter a valid amount")
                return
            invoice = f"{os.environ.get('KCB_BUNI_TILL_NUMBER', 'WIFI')}-{uuid4().hex[:12]}"
            callback = os.environ.get("KCB_BUNI_CALLBACK_URL", f"{PUBLIC_URL}/payment/kcb/callback")
            try:
                response = stk_push(phone, amount, invoice, callback)
            except KCBError as exc:
                detail = str(exc)
                body = f"""<!doctype html><meta name="viewport" content="width=device-width"><title>Payment unavailable</title><style>body{{font:16px system-ui,-apple-system,sans-serif;background:#f2f2f7;color:#1c1c1e;margin:0;padding:18vh 20px}}main{{max-width:420px;margin:auto;background:#fff;border-radius:20px;padding:24px;box-shadow:0 8px 24px #0001}}h1{{font-size:1.5rem}}p{{line-height:1.5;color:#6e6e73}}a{{display:block;text-align:center;background:#007aff;color:#fff;text-decoration:none;padding:13px;border-radius:12px;font-weight:700}}small{{display:block;margin-top:18px;color:#8e8e93}}</style><main><h1>Payment could not start</h1><p>KCB did not accept the checkout request. Your phone was not charged. Check the number and try again.</p><a href="/portal">Back to passes</a><small>Reference: {invoice}</small></main>""".encode()
                self.send_response(502)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                print(f"KCB payment failure invoice={invoice} phone_last4={phone[-4:]} detail={detail}", flush=True)
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
        if self.path in ("/ipn", "/payment/kcb/callback"):
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
