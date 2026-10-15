# Security practices

The practices I follow in this lab and why. This is a description of approach, not an inventory of the lab's exposure. For firewall examples see [../firewall/README.md](../firewall/README.md).

## Principles

- Keep the attack surface small: expose only what a service needs, and restrict administration to the LAN and the VPN.
- Prefer defaults that fail closed (default-deny firewall, key-only SSH, proxy access rules).
- Keep everything reproducible: configuration in Git, secrets out of it.
- Assume rules can drift, and check the real system rather than the notes.

## Remote access

- **Key-only SSH plus fail2ban.** Password logins are off, so brute-forcing a password does not work, and fail2ban bans sources that keep failing.
- **A VPN for administration.** Tailscale gives remote access without publishing admin interfaces. Administration happens from the LAN or over the VPN.

## Network

- **Default-deny host firewall.** UFW denies inbound traffic unless a rule allows it, and rules name explicit source ranges (the LAN, the VPN) instead of "anywhere".
- **Docker needs its own rules.** Docker-published ports bypass UFW, so the camera service's published ports are restricted with `DOCKER-USER` rules. See [../firewall/README.md](../firewall/README.md) and [stories.md](stories.md).
- **Verify what is actually reachable.** After any firewall change, test from another machine instead of trusting the rule list.
- **Authentication on management endpoints.** Anything that can control a service should require a login. An unauthenticated management endpoint turned up during a documentation audit and was removed.

## HTTPS

- **HTTPS for every web service.** One reverse proxy (Traefik) terminates TLS on 443 with a wildcard Let's Encrypt certificate.
- **Access-rule middleware.** Traefik applies access rules to the web services through a middleware.

## Updates

- **Automatic OS security updates** (unattended upgrades).
- **Nightly container updates** with Watchtower. Stacks that need a manual, tested upgrade opt out with a label instead of being updated unattended.
- **Rollback archives before upgrades**, so a bad upgrade can be reverted.

## Backups and change control

- **Snapshots before change.** I take a Timeshift system snapshot before major changes.
- **Scheduled backups.** Game servers are backed up daily, and every service's configuration is in Git so the lab can be rebuilt.

## Secrets

- **Never in Git.** Real secrets live in untracked `.env` files. Stacks that use environment variables ship a `.env.example` that lists the variable names with placeholder values, and `.gitignore` excludes `.env`, keys and certificates.
- **Placeholders in this repository.** Placeholders replace real values everywhere in this repository.
