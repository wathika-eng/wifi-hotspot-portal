#!/usr/bin/env bash
set -u

printf '%s\n' '== openNDS verification (read-only) =='
if command -v opennds >/dev/null 2>&1; then
  opennds -v
else
  printf '%s\n' 'opennds: missing'
fi

if command -v ndsctl >/dev/null 2>&1; then
  ndsctl status 2>&1 || true
else
  printf '%s\n' 'ndsctl: missing'
fi

printf '%s\n' '-- package versions --'
pacman -Q libmicrohttpd nftables 2>/dev/null || true

printf '%s\n' '-- gateway interfaces --'
ip -br addr 2>/dev/null || true
iw dev 2>/dev/null || true
