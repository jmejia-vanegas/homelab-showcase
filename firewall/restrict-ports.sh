#!/bin/bash
# Restricts Frigate's directly-published RTSP (8554) and WebRTC (8555 tcp/udp) ports
# to LAN + Tailscale only.
#
# Docker publishes these on 0.0.0.0 and inserts its own iptables/NAT rules ahead of
# UFW, so UFW alone cannot block them (see CLAUDE.md: "Docker bypasses UFW"). The
# DOCKER-USER chain is the one place Docker guarantees is consulted first for all
# container-forwarded traffic, so we manage the restriction there instead.
#
# Idempotent: safe to re-run (e.g. on every boot via systemd) — deletes any rules
# it previously added before re-inserting them.
set -e

CHAIN="DOCKER-USER"
LAN="192.168.1.0/24"
TAILSCALE="100.64.0.0/10"
COMMENT="frigate-restrict"

for spec in "tcp 8554" "tcp 8555" "udp 8555"; do
  proto="${spec% *}"
  port="${spec#* }"

  iptables -D "$CHAIN" -p "$proto" --dport "$port" -s "$LAN" -j ACCEPT -m comment --comment "$COMMENT" 2>/dev/null || true
  iptables -D "$CHAIN" -p "$proto" --dport "$port" -s "$TAILSCALE" -j ACCEPT -m comment --comment "$COMMENT" 2>/dev/null || true
  iptables -D "$CHAIN" -p "$proto" --dport "$port" -j DROP -m comment --comment "$COMMENT" 2>/dev/null || true

  iptables -I "$CHAIN" 1 -p "$proto" --dport "$port" -j DROP -m comment --comment "$COMMENT"
  iptables -I "$CHAIN" 1 -p "$proto" --dport "$port" -s "$TAILSCALE" -j ACCEPT -m comment --comment "$COMMENT"
  iptables -I "$CHAIN" 1 -p "$proto" --dport "$port" -s "$LAN" -j ACCEPT -m comment --comment "$COMMENT"
done
