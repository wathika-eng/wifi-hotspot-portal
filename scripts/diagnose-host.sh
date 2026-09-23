#!/usr/bin/env bash
set -u

printf '%s\n' '== WiFi Hotspot / captive portal host diagnostics (read-only) =='
printf '%s\n' '-- OS --'
cat /etc/os-release 2>/dev/null || true

printf '%s\n' '-- interfaces --'
ip -br link 2>/dev/null || true
iw dev 2>/dev/null || true

printf '%s\n' '-- installed tools --'
for command_name in create_ap hostapd dnsmasq nft iptables systemctl; do
  if command -v "$command_name" >/dev/null 2>&1; then
    printf '%-12s %s\n' "$command_name" "$(command -v "$command_name")"
  else
    printf '%-12s %s\n' "$command_name" 'missing'
  fi
done

printf '%s\n' '-- versions --'
create_ap --version 2>/dev/null || true
hostapd -v 2>/dev/null | head -1 || true
dnsmasq --version 2>/dev/null | head -1 || true
nft --version 2>/dev/null || true
iptables --version 2>/dev/null || true

printf '%s\n' '-- service state --'
systemctl --no-pager --full status NetworkManager create_ap hostapd dnsmasq 2>/dev/null || true

printf '%s\n' '-- firewall snapshots --'
nft list ruleset 2>/dev/null || true
iptables -S 2>/dev/null || true
iptables -t nat -S 2>/dev/null || true

printf '%s\n' '-- create_ap configuration path --'
if [ -r /etc/create_ap.conf ]; then
  sed -E 's/(PASSPHRASE=).*/\1<redacted>/; s/(WPA_PASSPHRASE=).*/\1<redacted>/' /etc/create_ap.conf
else
  printf '%s\n' '/etc/create_ap.conf not readable or absent'
fi
