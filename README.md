# WiFi Hotspot Paid Captive Portal

Portable integration for a Linux WiFi Hotspot (`create_ap`/WiHotspot) with
openNDS and an external HTTPS payment/authentication service.

## Status

This repository is currently the design and integration baseline. It does not
modify the host firewall or enable a payment gateway by itself.

Target flow:

```text
client -> WiHotspot/create_ap -> openNDS -> HTTPS portal -> payment webhook
                                                        -> session grant
```

## Portability

The repository is intended to be cloned on another laptop. Machine-specific
values belong in an untracked `.env` file; secrets must never be committed.
The hotspot interface, gateway address, payment credentials, and FAS key are
configuration, not source code.

## Current host baseline

The development host is CachyOS with `linux-wifi-hotspot 5.0.0-1`,
`create_ap`, hostapd, dnsmasq, nftables and iptables. The current hotspot uses
gateway `192.168.12.1`. Treat these as detected facts, not portable defaults.

## Before implementation

Run the read-only host diagnostic:

```bash
./scripts/diagnose-host.sh
```

The result must be captured before installing openNDS. WiHotspot currently
creates its own DHCP/DNS/NAT and iptables rules, while openNDS v10+ uses
nftables. Firewall ownership and restart ordering must be tested before either
service is enabled together.

See [`docs/architecture.md`](docs/architecture.md) for the design boundary.
