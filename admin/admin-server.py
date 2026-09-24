#!/usr/bin/env python3
"""Private operator console for the WiHotspot/openNDS MVP."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import unquote

HOST = os.environ.get("ADMIN_LISTEN_HOST", "127.0.0.1")
PORT = int(os.environ.get("ADMIN_LISTEN_PORT", "9090"))
TOKEN = os.environ.get("ADMIN_TOKEN", "")
LEASE_ROOT = Path(os.environ.get("PORTAL_LEASE_ROOT", "/tmp"))


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout, result.stderr


def leases():
    files = sorted(LEASE_ROOT.glob("create_ap.*/dnsmasq.leases"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return {}
    result = {}
    for row in files[0].read_text().splitlines():
        fields = row.split()
        if len(fields) >= 5:
            result[fields[1].lower()] = {"mac": fields[1], "ip": fields[2], "hostname": fields[3], "expires": fields[0]}
    return result


def clients():
    _, raw, _ = command("/usr/bin/ndsctl", "json")
    try:
        nds = json.loads(raw)
    except json.JSONDecodeError:
        nds = {"clients": {}, "client_list_length": "0", "trusted": []}
    current_leases = leases()
    rows = []
    for key, value in nds.get("clients", {}).items():
        item = value if isinstance(value, dict) else {"id": key}
        mac = str(item.get("mac", key)).lower()
        rows.append({**item, **current_leases.get(mac, {}), "state": "authenticated"})
    trusted = {str(mac).lower() for mac in nds.get("trusted", [])}
    for mac in trusted:
        if not any(row.get("mac", "").lower() == mac for row in rows):
            rows.append({**current_leases.get(mac, {"mac": mac}), "state": "trusted"})
    return rows


class AdminHandler(BaseHTTPRequestHandler):
    def authorized(self):
        return not TOKEN or self.headers.get("Authorization") == f"Bearer {TOKEN}"

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - stdlib handler API
        if self.path == "/healthz":
            self.send_json({"ok": True})
            return
        if self.path == "/api/clients":
            if not self.authorized():
                self.send_json({"error": "unauthorized"}, 401)
                return
            self.send_json({"clients": clients()})
            return
        body = DASHBOARD.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802 - stdlib handler API
        if not self.authorized():
            self.send_json({"error": "unauthorized"}, 401)
            return
        parts = self.path.split("/")
        if len(parts) != 5 or parts[:3] != ["", "api", "clients"]:
            self.send_json({"error": "not found"}, 404)
            return
        mac = unquote(parts[3])
        action = parts[4]
        if action not in {"trust", "untrust"}:
            self.send_json({"error": "unsupported action"}, 400)
            return
        code, stdout, stderr = command("/usr/bin/ndsctl", action, mac)
        if code != 0 and action == "trust":
            _, current, _ = command("/usr/bin/ndsctl", "json")
            if mac.lower() in current.lower():
                code = 0
        if code != 0:
            self.send_json({"error": stderr.strip() or stdout.strip() or "openNDS action failed"}, 502)
            return
        self.send_json({"ok": True, "mac": mac, "action": action})

    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)


DASHBOARD = r'''<!doctype html>
<html lang="en"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>WiHotspot console</title>
<style>
:root{color-scheme:dark;--ink:#0e1116;--panel:#171c24;--line:#29313e;--text:#e8edf4;--muted:#9aa7b8;--blue:#61a8ff;--amber:#f3b64b}
*{box-sizing:border-box}body{margin:0;background:var(--ink);color:var(--text);font:15px/1.5 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:36px 22px}.top{display:flex;justify-content:space-between;gap:20px;align-items:end;border-bottom:1px solid var(--line);padding-bottom:24px}
h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1;margin:0;letter-spacing:-.05em}.eyebrow{color:var(--blue);font-weight:650;margin:0 0 8px}.note{color:var(--muted);max-width:52ch}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:24px 0}.stat,.table-wrap{background:var(--panel);border:1px solid var(--line);border-radius:14px}.stat{padding:18px}.stat b{display:block;font-size:2rem}.stat span{color:var(--muted)}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}input,button{font:inherit;border-radius:9px;border:1px solid var(--line);padding:10px 13px}input{background:#0b0e13;color:var(--text);min-width:220px}button{background:var(--blue);color:#07101c;border:0;font-weight:700;cursor:pointer}button.secondary{background:transparent;color:var(--text);border:1px solid var(--line)}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:14px 16px;border-bottom:1px solid var(--line)}th{color:var(--muted);font-size:.78rem;font-weight:650}td small{display:block;color:var(--muted)}.badge{display:inline-block;padding:3px 8px;border-radius:99px;background:#203148;color:var(--blue)}.badge.warn{background:#3a2d16;color:var(--amber)}
.empty{padding:28px;color:var(--muted)}@media(max-width:700px){.top{display:block}.stats{grid-template-columns:1fr}table{min-width:700px}.table-wrap{overflow:auto}}
</style>
<main><section class="top"><div><p class="eyebrow">OPERATOR CONSOLE</p><h1>Who is on your Wi-Fi?</h1><p class="note">Live view of the hotspot leases and openNDS access state. This console is for the operator, not hotspot guests.</p></div><button class="secondary" onclick="load()">Refresh</button></section>
<section class="stats"><div class="stat"><b id="total">—</b><span>visible clients</span></div><div class="stat"><b id="auth">—</b><span>authenticated</span></div><div class="stat"><b id="trusted">—</b><span>trusted devices</span></div></section>
<div class="toolbar"><input id="token" type="password" placeholder="Admin token (if configured)" autocomplete="current-password"><button onclick="load()">Load clients</button></div>
<div class="table-wrap"><table><thead><tr><th>Device</th><th>Address</th><th>State</th><th>Session</th><th>Action</th></tr></thead><tbody id="rows"><tr><td colspan="5" class="empty">Enter the admin token and load the console.</td></tr></tbody></table></div>
<p class="note">MVP note: trusted-device access is currently persistent. Payment-backed session expiry will replace this with time-limited openNDS authorization.</p></main>
<script>
async function load(){const token=document.querySelector('#token').value;const r=await fetch('/api/clients',{headers:token?{Authorization:'Bearer '+token}:{}});const data=await r.json();if(!r.ok){document.querySelector('#rows').innerHTML='<tr><td colspan="5" class="empty">'+(data.error||'Unable to load clients')+'</td></tr>';return}const list=data.clients||[];document.querySelector('#total').textContent=list.length;document.querySelector('#auth').textContent=list.filter(x=>x.state==='authenticated').length;document.querySelector('#trusted').textContent=list.filter(x=>x.state==='trusted').length;document.querySelector('#rows').innerHTML=list.length?list.map(x=>`<tr><td>${x.hostname||'Unknown'}<small>${x.mac||''}</small></td><td>${x.ip||'—'}</td><td><span class="badge ${x.state==='trusted'?'warn':''}">${x.state}</span></td><td>${x.sessiontimeout||'—'}</td><td><button class="secondary" onclick="act('${x.mac}','${x.state==='trusted'?'untrust':'trust'}')">${x.state==='trusted'?'Revoke':'Trust'}</button></td></tr>`).join(''):'<tr><td colspan="5" class="empty">No clients yet.</td></tr>'}
async function act(mac,action){const token=document.querySelector('#token').value;await fetch('/api/clients/'+encodeURIComponent(mac)+'/'+action,{method:'POST',headers:token?{Authorization:'Bearer '+token}:{}});load()} 
</script></html>'''


if __name__ == "__main__":
    ThreadingHTTPServer((HOST, PORT), AdminHandler).serve_forever()
