# Troubleshooting stories

Short write-ups of problems I hit in the lab, in the form problem, investigation, fix, lesson. They are intentionally generic.

## 1. Network-wide slowdowns and drops

**Problem.** The whole home network repeatedly slowed to a crawl and then dropped.

**Investigation.** I compared wired and Wi-Fi speed tests, suspected the mesh Wi-Fi first, and added a nightly reboot of it as a workaround. That barely helped. I then looked at the old standalone device that served DNS and DHCP.

**Fix.** I moved DNS and DHCP to a Pi-hole container on the server. The drops stopped, and I turned the reboot workaround off again.

**Lesson.** Test one variable at a time, and do not assume the first suspect is the cause.

## 2. Camera live view stuck on "connecting" inside the LAN

**Problem.** Live video and two-way audio hung at "connecting" for devices inside the home network.

**Investigation.** The video service advertised only its public address for WebRTC. From inside the LAN that address is often unreachable because the router does not do NAT hairpinning, so the connection never completed.

**Fix.** I explicitly listed the server's LAN and VPN addresses as connection candidates.

**Lesson.** The same service can behave differently for inside and outside users, so test from both.

## 3. A firewall that was not blocking what I thought

**Problem.** The host firewall was not blocking everything I assumed it was.

**Investigation.** During a security review I found that two firewall rules were open to far more than intended, and learned that Docker-published ports bypass the host firewall.

**Fix.** I tightened the rules and added dedicated iptables rules (`DOCKER-USER`) for the camera service's published ports (see [../firewall/README.md](../firewall/README.md)).

**Lesson.** Verify what is actually reachable instead of trusting that a rule exists.

## 4. A self-healing script that caused the problem

**Problem.** The local AI service sometimes corrupted its GPU state, so I wrote a systemd timer that restarts it when a health check fails. Later the check failed every time and the service was restarted every 5 minutes.

**Investigation.** The script had a hard-coded container IP address. After the container was recreated with a new address, every probe "failed".

**Fix.** The script now looks up the address from the container name on every run, and its timeout is longer, because a freshly started model takes 30 to 40 seconds to load. See [../scripts/](../scripts/).

**Lesson.** Automation needs monitoring too, and nothing environment-specific should be hard-coded.

## 5. Documentation that had drifted from reality

**Problem.** My documentation described a setup from months earlier.

**Investigation.** I audited every document against the live server and its configuration files.

**Fix.** I corrected the documents to match the live system and recorded the unknowns instead of guessing. Along the way I found and removed an unauthenticated management endpoint.

**Lesson.** Review the real system periodically, not just the notes about it.
