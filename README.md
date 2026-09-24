# WiHotspot paid captive portal

This repository connects a Linux WiHotspot (`create_ap`) access point to
openNDS and a small HTTPS-compatible portal. It is designed to be cloned onto
another Linux laptop and configured with local environment values.

## What works today

- WiHotspot creates the `MyAccessPoint` network and provides DHCP, DNS and NAT.
- openNDS intercepts unauthenticated clients on `ap0`.
- Android captive-portal detection receives an RFC 8908 response and opens the
  portal in the system captive-login window.
- The portal can activate a client by calling `ndsctl trust` (MVP/mock access).
- Tailscale Funnel publishes only the guest portal.
- A private operator console shows leases and openNDS state and can trust or
  revoke a device.

This is not yet a production payment system. Activation currently grants
persistent openNDS trust; KCB payment initiation, callback verification,
durations and automatic expiry are the next implementation slice.

## Architecture

```text
phone --Wi-Fi--> create_ap/ap0 --intercept--> openNDS:2050
  |                                         |
  +-- RFC 8908 --> Tailscale Funnel --> portal:8080
                                             |
                                      ndsctl trust/revoke

operator --> Tailscale Serve (tailnet only) --> admin:9090
```

The guest hostname must be reachable through Tailscale Funnel. The admin
console must not be exposed through Funnel; publish it with Tailscale Serve or
keep it on `127.0.0.1` and use an SSH tunnel.

## Prerequisites

On the hotspot laptop install or already have:

- CachyOS/Arch Linux (other systemd Linux distributions can work with path
  adjustments)
- WiHotspot / `linux-wifi-hotspot`, `create_ap`, hostapd and dnsmasq
- openNDS 11.x (the current host uses a local build)
- Python 3.10+
- Tailscale, authenticated to the tailnet
- `git`, `curl`, `openssl`; `adb` is optional but useful for Android testing

The service units assume `/usr/bin/ndsctl`, `/usr/bin/opennds`,
`/usr/bin/python3`, and this checkout at `/home/wathi/wifi-hotspot-portal`.
Change those paths in the units if your layout differs.

## First-time setup on a laptop

```bash
git clone https://github.com/wathika-eng/wifi-hotspot-portal.git
cd wifi-hotspot-portal
cp .env.example .env
chmod 600 .env
```

Edit `.env` before installing services. At minimum set:

```dotenv
PORTAL_PUBLIC_URL=https://YOUR-TAILSCALE-NODE.tailnet.ts.net
PORTAL_GATEWAY_URL=http://192.168.12.1:2050/
WIFI_UPSTREAM_INTERFACE=wlan0
WIFI_AP_SSID=MyAccessPoint
OPENNDS_GATEWAY_INTERFACE=ap0
```

`PORTAL_PUBLIC_URL` is the Funnel hostname, without a trailing path. The
hostname in `/etc/create_ap.conf` (`CAPTIVE_PORTAL_URL`) must match it exactly.
The gateway address and interface are machine-specific; discover them with
`./scripts/diagnose-host.sh` before changing the example values.

Run the read-only checks first:

```bash
./scripts/diagnose-host.sh
python3 -m py_compile portal/portal-server.py admin/admin-server.py
```

## Install and start the services

The following commands install the repository's systemd units and the two
small server entrypoints. They require root privileges:

```bash
sudo install -m 0755 admin/admin-server.py /usr/local/bin/wifi-hotspot-admin.py
sudo install -m 0644 systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now create_ap.service
sudo systemctl enable --now hotspot-firewall.service
sudo systemctl enable --now opennds.service
sudo systemctl enable --now portal-funnel.service
sudo systemctl enable --now wifi-hotspot-admin.service
```

Check the complete chain:

```bash
systemctl --no-pager --full status create_ap opennds portal-funnel wifi-hotspot-admin hotspot-firewall
curl -fsS http://127.0.0.1:8080/capport
curl -fsS http://127.0.0.1:9090/healthz
```

If the admin service is intentionally token-protected, set a random
`ADMIN_TOKEN` in `.env` (for example `openssl rand -hex 32`) and send it as
`Authorization: Bearer ...`. Otherwise keep the admin listener on loopback and
reach it through Tailscale Serve or an SSH tunnel.

## Tailscale Funnel and private admin access

On the deployment laptop, authenticate Tailscale and enable Funnel for the
guest portal:

```bash
tailscale up
tailscale funnel --bg 8080
tailscale funnel status
```

Copy the HTTPS hostname shown by `tailscale funnel status` into `.env` as
`PORTAL_PUBLIC_URL`, then restart the portal service. Funnel is public, so the
portal must never display secrets or expose the admin API.

For a private operator console, use Serve (tailnet access only) rather than
Funnel. Confirm the installed CLI syntax with `tailscale serve --help`, then
proxy the local admin port:

```bash
tailscale serve --https=443 http://127.0.0.1:9090
tailscale serve status
```

The exact Serve syntax can vary by Tailscale release; the status output is the
source of truth. An SSH alternative is:

```bash
ssh -L 9090:127.0.0.1:9090 user@hotspot-laptop
```

Then open `http://127.0.0.1:9090` on the operator machine.

## Android test checklist

1. Restart `create_ap`, `opennds`, and `portal-funnel`.
2. Forget the hotspot on the phone, then reconnect.
3. The Android captive-login window should open the Funnel URL automatically.
4. Select **Activate Wi-Fi**. The MVP trusts the latest DHCP lease and then
   redirects Android to its connectivity check so the network can revalidate.
5. Close the captive-login window and browse normally.

Useful evidence commands:

```bash
adb shell dumpsys connectivity | rg -i 'CAPTIVE|validated|portal'
adb logcat -c
adb logcat -v brief | rg -i 'CaptivePortal|NetworkMonitor|ConnectivityService'
```

## KCB Buni M-Pesa Express

The selected provider is KCB Buni's M-Pesa Express/STK Push API. The supplied
specification and Postman collection describe:

- OAuth client-credentials token: `POST https://uat.buni.kcbgroup.com/token?grant_type=client_credentials`
- STK Push: `POST https://uat.buni.kcbgroup.com/mm/api/request/1.0.0/stkpush`
- Basic authentication for the token request using the Buni consumer key and
  consumer secret.
- STK headers including `routeCode: 207`, `operation: STKPush`, a unique
  `messageId`, and `Authorization: Bearer <token>`.
- Payload fields `phoneNumber`, `amount`, `invoiceNumber`, `sharedShortCode`,
  `callbackUrl`, and an optional transaction description.
- An asynchronous callback containing `MerchantRequestID`,
  `CheckoutRequestID`, `ResultCode`, and callback metadata such as the M-Pesa
  receipt number.

Fill the KCB variables in the untracked `.env` only:

```dotenv
PAYMENT_PROVIDER=kcb-buni
KCB_BUNI_API_BASE_URL=https://uat.buni.kcbgroup.com
KCB_BUNI_CONSUMER_KEY=...
KCB_BUNI_CONSUMER_SECRET=...
KCB_BUNI_API_KEY=...
KCB_BUNI_TILL_NUMBER=...
KCB_BUNI_CALLBACK_URL=https://YOUR-PORTAL-HOST/payment/kcb/callback
KCB_BUNI_WEBHOOK_SECRET=...
```

Do not paste consumer secrets, bearer tokens, certificates, or the Postman
collection's sample token into GitHub or chat. The collection/specification
contain example credentials and must be treated as sensitive; rotate any
credential that has been used outside the KCB portal. Sandbox onboarding is at
`https://sandbox.buni.kcbgroup.com/devportal/apis`. Production access requires
the Buni onboarding/request-letter process described by KCB.

The repository currently does not call KCB. Payment code should be added only
after deciding the product price and session duration, then implement this
transaction boundary:

```text
portal phone/plan -> create local pending payment
                 -> KCB token + STK Push
                 -> verify callback and amount/reference
                 -> grant openNDS trust for a bounded duration
                 -> expire/revoke the session
```

Never grant access solely from a browser redirect; trust must follow a verified
server-to-server callback with an idempotent payment reference.

## Admin console

The first dashboard slice is available at the admin service's private URL. It
combines the current dnsmasq lease file with `ndsctl json` and supports:

- viewing visible devices, IP/MAC/hostname and access state;
- trusting a device for a manual test; and
- revoking a trusted device.

Time limits, payment records, historical sessions and reporting are not yet
implemented. They require persistent storage and a session-expiry worker;
`ndsctl trust` is deliberately only an MVP bridge.

## Portability notes

The following are host integration steps and are not fully portable source
files: WiHotspot's `/usr/bin/create_ap` patch for DHCP option 114, the local
`address=/.../100.85.186.27` DNS override, openNDS package installation, and
firewall rules. Reapply them on a new laptop using the scripts and patches in
this repository, substituting that laptop's Tailscale IP and hostname. Never
copy `/etc/create_ap.conf`, `.env`, private keys, or `/etc/opennds` blindly
between machines.

## Troubleshooting

**The phone sees Wi-Fi but says no internet:** verify that the captive-login
window was completed, then check `adb shell dumpsys connectivity`. A network in
`CAPTIVE_PORTAL` is expected until activation and Android revalidation finish.

**The portal shows 502:** check `systemctl status portal-funnel` and
`curl http://127.0.0.1:8080/capport`; the Funnel target must be the local portal
on port 8080.

**The portal never opens:** verify DHCP option 114, DNS redirection to the
WiHotspot dnsmasq port (5353 on the current host), openNDS port 2050, and the
`ap0` firewall rules. Use `./scripts/verify-opennds.sh`.

**KCB returns 401/403:** confirm the UAT base URL, consumer key/secret, token
request, and that the bearer token is fresh. A callback URL must be HTTPS and
reachable by KCB; Funnel is suitable for a temporary UAT callback, not an
unreviewed production design.

## GitHub workflow

```bash
git status
git add .
git commit -m "describe the change"
git push origin main
```

`.env`, certificates, bearer tokens, caches and Python bytecode are ignored by
Git. Review `git diff --cached` before every push.
