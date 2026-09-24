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

## Firewall ownership

`create_ap` currently creates its own DHCP/DNS/NAT and iptables rules. The
generic-Linux openNDS helper also rejects wireless interfaces by default. This
repository carries `patches/opennds-allow-wifi-ap.patch` for the tested
WiHotspot NAT topology; it must be applied and rebuilt when reproducing the
install. Before enabling both services, prove that an unauthenticated client
cannot forward traffic and that restarting `create_ap` cannot insert a
first-in-chain bypass rule. Keep a rollback terminal available and do not
enable the service at boot until that test passes.
