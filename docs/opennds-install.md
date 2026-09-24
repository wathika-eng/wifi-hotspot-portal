# openNDS host installation

The reference gateway version is **openNDS v11.0.0**. The host install uses
the upstream source tag and the distribution packages for `libmicrohttpd` and
`nftables`.

On Arch/CachyOS:

```bash
pkexec pacman -S --needed libmicrohttpd nftables
git clone --depth 1 --branch v11.0.0 https://github.com/openNDS/openNDS.git /tmp/openNDS-v11
make -C /tmp/openNDS-v11
pkexec make -C /tmp/openNDS-v11 install
```

Verify before enabling anything:

```bash
opennds -v
ndsctl status
```

## Activation warning

Do not set `GatewayInterface` to the upstream managed Wi-Fi interface. It must
be the interface created by WiHotspot for clients, and it must have the
hotspot gateway address. Confirm it only while `create_ap` is running:

```bash
pkexec ip -br addr
pkexec iw dev
```

The current host configuration uses `wlan0` as the upstream interface and
gateway `192.168.12.1` when the hotspot is created. The active host currently
has `wlan0` in managed mode at `192.168.1.147`, so openNDS must remain stopped
until the AP interface exists.

On a generic Linux host, WiHotspot owns a private dnsmasq process for `ap0`.
Set `fwhook_enabled` to `0` in `/etc/config/opennds` so openNDS does not try to
reload the unrelated system `dnsmasq.service` during firewall updates.
Because this dnsmasq instance listens on port `5353` and WiHotspot redirects
client DNS from port `53`, allow both UDP and TCP `5353` in the openNDS
`users_to_router` rules.
The Funnel node and its public relay addresses must also be walled-gardened
before authentication; keep these addresses synchronized with public DNS.

## Firewall ownership

`create_ap` currently creates its own DHCP/DNS/NAT and iptables rules. The
generic-Linux openNDS helper also rejects wireless interfaces by default. This
repository carries `patches/opennds-allow-wifi-ap.patch` for the tested
WiHotspot NAT topology; it must be applied and rebuilt when reproducing the
install. Before enabling both services, prove that an unauthenticated client
cannot forward traffic and that restarting `create_ap` cannot insert a
first-in-chain bypass rule. Keep a rollback terminal available and do not
enable the service at boot until that test passes.

For modern phones, apply `patches/create-ap-dhcp-option-114.patch` to the
WiHotspot `create_ap` script as well. It advertises the portal URL via DHCP
option 114; HTTP interception remains enabled as a fallback for older clients.

The repository also includes `systemd/opennds.service`. It runs openNDS in the
foreground so systemd tracks the actual process and restarts do not leave a
stale background child:

```bash
sudo install -m 0644 systemd/opennds.service /etc/systemd/system/opennds.service
sudo systemctl daemon-reload
```

For Android's modern captive-portal API, use the trusted HTTPS Funnel landing
page. Install and start `systemd/portal-funnel.service`, configure Tailscale
Funnel to proxy `http://127.0.0.1:8080`, and set `CAPTIVE_PORTAL_URL` in the
WiHotspot environment to the resulting `https://<node>.ts.net/` URL.
