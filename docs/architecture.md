# Architecture

A single Ubuntu server runs everything. The layers below are listed from the network edge inward.

```
Internet
   │
[ Router ] ── [ Mesh Wi-Fi (AP mode) ] ── home devices
   │
[ Managed PoE switch ] ── PoE IP cameras
   │
[ Homeserver — Ubuntu Linux ]
   ├─ Host services:  UFW firewall · SSH (keys only) + fail2ban · Tailscale VPN ·
   │                  Pterodactyl Wings · unattended security updates · systemd timers
   └─ Docker (10 Compose stacks)
        ├─ Traefik  ← reverse proxy: HTTPS, wildcard certificate, access rules
        ├─ Pi-hole  ← DNS + DHCP for the whole network
        └─ Apps: Frigate · Immich · Home Assistant (+ voice stack) · Open WebUI ·
                 SparkyFitness · Pterodactyl · light-automation · Watchtower
```

## Network

A router, a mesh Wi-Fi system in access-point mode and a managed PoE switch carry the traffic. The server itself is on wired Ethernet. Pi-hole runs on the server and provides DNS (with ad/tracker blocking) and DHCP with address reservations. Internal names resolve through Pi-hole, so the same hostnames work on the LAN and, via split DNS, over the VPN. Tailscale provides remote access.

## Host

The host is Ubuntu 24.04 LTS (Desktop edition). It is hardened with key-only SSH plus fail2ban, a default-deny UFW firewall, and unattended security updates. Pterodactyl Wings, the daemon that runs the game servers, is installed on the host. Recurring jobs use systemd timers. See [security-practices.md](security-practices.md) and [../firewall/README.md](../firewall/README.md).

## Docker and Traefik

Each service is a Docker Compose stack. Traefik is the single reverse proxy: it terminates HTTPS for every web service using a wildcard Let's Encrypt certificate and applies access rules through a middleware. Stacks join a shared proxy network so Traefik can reach them. Watchtower updates containers every night.

## Apps

Frigate records the camera streams and runs object detection on the GPU; a small Python service (light-automation) reacts to detections. Immich handles photo backup. Home Assistant is the smart-home hub, with an experimental local voice stack and Ollama. Open WebUI is the chat front end for Ollama, and SparkyFitness uses the same local model to read food labels. Pterodactyl runs the game servers.

## Design choices

- **One front door:** every web service goes through one reverse proxy.
- **Least exposure:** firewall rules are scoped to explicit source ranges.
- **Everything as code:** each service is a Compose file in Git, so the lab can be rebuilt and every change is traceable.
- **Automation:** nightly updates, daily game-server backups, automatic OS security patches and a health-check timer (see [stories.md](stories.md) for a lesson about automation).
- **Documented against reality:** documentation was audited against the running system.

## Stacks

| Stack | What it does |
|-------|--------------|
| [traefik](../stacks/traefik/) | Reverse proxy, HTTPS certificates, access-rule middleware |
| [pihole](../stacks/pihole/) | DNS and DHCP (trimmed configuration excerpt) |
| [immich](../stacks/immich/) | Photo and video backup |
| [frigate](../stacks/frigate/) | Network video recorder with GPU object detection |
| [homeassistant-voice](../stacks/homeassistant-voice/) | Home Assistant plus the local voice stack and Ollama |
| [open-webui](../stacks/open-webui/) | Chat interface for the local AI model |
| [sparkyfitness](../stacks/sparkyfitness/) | Nutrition tracker using the local AI model |
| [light-automation](../stacks/light-automation/) | Floodlight automation driven by detections |
| [pterodactyl](../stacks/pterodactyl/) | Game-server management panel |
| [watchtower](../stacks/watchtower/) | Nightly container updates |

Helper scripts and systemd units are in [../scripts/](../scripts/).
