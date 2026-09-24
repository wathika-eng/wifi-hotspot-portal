#!/usr/bin/env bash
set -euo pipefail

ensure_filter_rule() {
  local chain=$1
  shift
  if ! iptables -C "$chain" "$@" 2>/dev/null; then
    iptables -I "$chain" "$@"
  fi
}

ensure_nat_rule() {
  local chain=$1
  shift
  if ! iptables -t nat -C "$chain" "$@" 2>/dev/null; then
    iptables -t nat -I "$chain" "$@"
  fi
}

ensure_filter_rule INPUT -i ap0 -p tcp --dport 2050 -j ACCEPT
ensure_filter_rule INPUT -i ap0 -p udp --dport 5353 -j ACCEPT
ensure_filter_rule INPUT -i ap0 -p tcp --dport 5353 -j ACCEPT
ensure_filter_rule INPUT -i ap0 -d 100.85.186.27 -p tcp --dport 443 -j ACCEPT
ensure_filter_rule FORWARD -i ap0 -o tailscale0 -d 100.85.186.27 -p tcp --dport 443 -j ACCEPT
ensure_nat_rule POSTROUTING -s 192.168.12.0/24 -d 100.85.186.27 -o tailscale0 -p tcp --dport 443 -j MASQUERADE
