# Home Lab

> This is a sanitized snapshot of a private repository. Domains, addresses, e-mail, keys and coordinates are placeholders (e.g. lab.example.com).

## The 30-second version

A 24/7 self-hosted home lab, built on a repurposed gaming PC running Ubuntu Linux. It runs about 24 containers across 10 Docker Compose stacks and provides DNS and DHCP for my home network, photo backup, an AI-powered security-camera system, smart-home and voice-assistant experiments, and game servers. I built it to learn real system, network and security administration hands-on: I install, secure, monitor, troubleshoot and document it myself.

This is a hobby and learning project. It is a home lab, not an enterprise or production environment.

## Purpose and who uses it

**Why it exists**
- Learn IT fundamentals (networking, Linux, security, troubleshooting) by running real services instead of reading about them.
- Replace cloud subscriptions with self-hosted alternatives (photo backup, camera recording, a private local voice assistant).
- Make the home network more reliable (the DNS/DHCP server runs here).

**Who uses it**
- Every device on the home network gets its address and DNS from this server.
- A small group of friends have remote access over a VPN, and friends play on the game servers I host.
- I am the only administrator: patching, monitoring, backups, user access and support.

## At a glance

| | |
|---|---|
| Running since | March 2026 |
| Hardware | Repurposed PC: AMD Ryzen 5 3600 (6 cores / 12 threads), 46 GB RAM, NVIDIA RTX 2060 Super GPU |
| OS | Ubuntu 24.04 LTS (Desktop edition) |
| Containers | About 24 running, 10 Docker Compose stacks |
| Remote access | Tailscale VPN, SSH (key-only) |
| Version control | All configuration in Git |

## How it's set up

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
        ├─ Traefik  ← reverse proxy: HTTPS for every web service, wildcard Let's Encrypt
        │             certificate, access rules
        ├─ Pi-hole  ← DNS + DHCP for the whole network (with address reservations)
        └─ Apps: Frigate · Immich · Home Assistant (+ voice stack) · Open WebUI ·
                 SparkyFitness · Pterodactyl · light-automation · Watchtower
```

**Design choices worth mentioning**
- **One front door:** Traefik is the single entry point for the web services and applies HTTPS and access rules.
- **Least exposure:** firewall rules are scoped to explicit source ranges, and I audited them and tightened rules that had drifted open.
- **Everything as code:** each service is described by a Compose file and committed to Git, so the whole lab can be rebuilt and every change is traceable.
- **Automation:** nightly container updates, daily game-server backups, automatic OS security patches, and a health-check timer that repairs a failing service on its own.
- **Documented:** the documentation was audited against the live system so it reflects what is actually running.

More detail: [docs/architecture.md](docs/architecture.md).

## Services

| Area | Service | What it does |
|------|---------|--------------|
| **Network** | Pi-hole | Network-wide DNS (with ad/tracker blocking) and DHCP with address reservations |
| | Traefik | Reverse proxy, automatic HTTPS certificates, access control |
| | Tailscale | VPN for secure remote access |
| **Security / cameras** | Frigate | Network video recorder for PoE IP cameras; AI object detection (people, cars, pets) on the GPU; email alerts |
| | light-automation | Small Python service that turns on a camera's floodlight when a person/vehicle is detected at night |
| **Data** | Immich | Self-hosted photo/video backup (Google-Photos style) |
| **Smart home / AI** | Home Assistant + voice stack | Smart-home hub plus an experimental local voice assistant (wake word → speech-to-text → local AI model → text-to-speech) |
| | Ollama, Open WebUI | Local AI model server and chat interface |
| | SparkyFitness | Self-hosted nutrition tracker that uses the local AI model to read food labels |
| **Hosting** | Pterodactyl panel + Wings | Web panel that manages Minecraft and Palworld game servers |
| **Operations** | Watchtower | Updates containers automatically every night |
| | Custom health-check script (systemd timer) | Checks the AI service every 5 minutes and restarts it if it fails |

## Skills demonstrated

| Skill area | Where it shows up in the lab |
|------------|-------------------------------|
| **Troubleshooting methodology** | Isolating a network-wide problem step by step (see [stories](docs/stories.md)); reading logs; reproducing and fixing failures |
| **TCP/IP, DNS, DHCP** | Running the DNS and DHCP servers, address reservations, split DNS for VPN users, NAT |
| **Network hardware** | Mesh Wi-Fi, a managed PoE switch, IP cameras; speed tests on wired vs. Wi-Fi |
| **Linux administration** | Ubuntu, Bash, systemd services and timers, package updates, disk/storage monitoring, SSH |
| **Security basics** | Firewall (UFW/iptables), key-only SSH, fail2ban, VPN, TLS certificates, least-privilege network exposure, patching, backups (see [security practices](docs/security-practices.md)) |
| **Remote support** | SSH and a VPN for connecting to the server and helping other users connect |
| **End-user support** | Walking non-technical users through VPN setup and connection problems |
| **Documentation** | Runbooks and a documentation audit |
| **Version control** | Git for all configuration changes |
| **Backup & recovery** | System snapshots before major changes (Timeshift), scheduled daily backups, pre-upgrade rollback archives |

## Repository layout

| Path | Contents |
|------|----------|
| [`docs/`](docs/) | [Architecture](docs/architecture.md), [troubleshooting stories](docs/stories.md), [security practices](docs/security-practices.md) |
| [`firewall/`](firewall/README.md) | Example UFW rule patterns and the `DOCKER-USER` iptables script |
| `stacks/<service>/` | Sanitized Docker Compose files and configuration, plus an `.env.example` for stacks that use environment variables |
| [`scripts/`](scripts/) | The AI-service health-check script and systemd units |

## About the configuration files

The files under `stacks/` are real, working configuration with sensitive values replaced by placeholders. Compose port mappings are kept because they are part of how a stack is configured; they say nothing about what is reachable from outside the home network. Real `.env` files are never included; for stacks that use environment variables, use the stack's `.env.example` as a template.

## Skills keywords

Ubuntu/Linux administration · Docker & Docker Compose · TCP/IP · DNS · DHCP · NAT · Firewalls (UFW/iptables) · VPN (Tailscale) · SSH · TLS/HTTPS & reverse proxies · Git · Bash · systemd · IP cameras & PoE · Home Assistant · Troubleshooting · Technical documentation

---

© jmejia-vanegas — MIT licensed.
