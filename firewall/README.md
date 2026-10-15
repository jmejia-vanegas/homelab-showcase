# Firewall examples

Two layers protect the server. Rule patterns below are **examples** using standard ports and generic ranges — they are not an inventory of this lab's exposure.

## 1. Host firewall (UFW), default-deny

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Administration only from the LAN and over the VPN interface
sudo ufw allow from 192.168.1.0/24 to any port 22 proto tcp comment 'SSH via LAN'
sudo ufw allow in on tailscale0 to any port 22 proto tcp comment 'SSH via VPN'

# DNS server for the LAN and VPN clients only
sudo ufw allow from 192.168.1.0/24 to any port 53 comment 'DNS LAN'
sudo ufw allow from 100.64.0.0/10  to any port 53 comment 'DNS VPN'

sudo ufw enable
sudo ufw status numbered
```

## 2. Docker bypasses UFW — restrict published ports with `DOCKER-USER`

Docker publishes container ports by inserting its own iptables rules *ahead of* UFW, so a rule that "allows" or "denies" a port in UFW can have no effect on a published container port. The `DOCKER-USER` chain is the one place Docker guarantees is consulted first. `restrict-ports.sh` (in this directory) inserts ACCEPT rules for the LAN and VPN ranges and a DROP for everything else, is idempotent, and is re-applied at boot by `frigate-restrict-ports.service`.

Lesson learned: always test what is *actually* reachable (from another machine) instead of trusting that a rule exists.
