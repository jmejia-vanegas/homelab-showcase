#!/usr/bin/env bash
# Ollama vision-model watchdog.
#
# The hass-ollama container has intermittently gotten its GPU/CUDA runtime
# stuck after memory pressure (seen after a genuine OOM, and again with no
# clean error at all) — symptoms are garbled token output (long runs of "?")
# and/or done:false on a non-streaming request. A container restart always
# clears it; this script detects that state and restarts automatically so
# SparkyFitness's label/meal-photo AI scans don't need a manual fix each time.
#
# Runs a small, cheap text-only chat request against the same model used for
# label scans (no image, minimal tokens) and checks the response is well-formed.
# Intended to run on a timer (see ollama-watchdog.timer) — not continuously.

set -euo pipefail

OLLAMA_CONTAINER="hass-ollama"
MODEL="qwen2.5vl-labelscan"
COMPOSE_DIR="$HOME/homelab/containers/homeassistant-voice"
LOG_DIR="$HOME/homelab/scripts/logs"
LOG_FILE="$LOG_DIR/ollama-watchdog.log"
# A cold model takes 30-40s to load after a container restart (measured 2026-10-14), so
# a 30s timeout false-flagged every freshly restarted Ollama as unhealthy and re-restarted it.
# Worst case per run: 90s probe + restart + 6s + 90s verify, comfortably under the 5-min timer.
TIMEOUT=90
MAX_LOG_LINES=2000

mkdir -p "$LOG_DIR"

log() {
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >>"$LOG_FILE"
  # Cheap rotation: keep the file from growing forever since this runs on a timer.
  if [ "$(wc -l <"$LOG_FILE")" -gt "$MAX_LOG_LINES" ]; then
    tail -n "$MAX_LOG_LINES" "$LOG_FILE" >"${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
  fi
}

payload=$(cat <<JSON
{
  "model": "${MODEL}",
  "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
  "stream": false,
  "options": {"num_ctx": 8192, "temperature": 0}
}
JSON
)

# The container's IP on the compose network changes whenever it is recreated, so
# look it up on every run instead of hardcoding it (a stale hardcoded IP made
# every probe "fail" and restart-loop Ollama every 5 minutes). Empty output means
# the container is stopped/missing, which the checks below treat as unhealthy.
ollama_url() {
  local ip
  ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' \
    "$OLLAMA_CONTAINER" 2>/dev/null | awk '{print $1}' || true)
  [ -n "$ip" ] && echo "http://${ip}:11434/api/chat"
  return 0
}

probe() {
  local url
  url=$(ollama_url)
  [ -n "$url" ] || return 0
  curl -s --max-time "$TIMEOUT" -H 'Content-Type: application/json' \
    -d "$payload" "$url" 2>/dev/null || true
}

response=$(probe)

restart_needed=false
reason=""

if [ -z "$response" ]; then
  restart_needed=true
  reason="no response (timeout or connection failure)"
elif ! echo "$response" | jq -e . >/dev/null 2>&1; then
  restart_needed=true
  reason="response was not valid JSON"
else
  done_flag=$(echo "$response" | jq -r '.done // false')
  content=$(echo "$response" | jq -r '.message.content // ""')
  # Corrupted runtime shows up as done:false or content that's just
  # replacement-character garbage (runs of "?" with no real words).
  if [ "$done_flag" != "true" ]; then
    restart_needed=true
    reason="done was not true (got: $done_flag)"
  elif [ -z "$content" ]; then
    restart_needed=true
    reason="empty content"
  elif echo "$content" | grep -qE '^[?[:space:]]{10,}$'; then
    restart_needed=true
    reason="content was garbled (repeated '?' characters)"
  fi
fi

if [ "$restart_needed" = true ]; then
  log "UNHEALTHY: $reason — restarting ollama"
  if (cd "$COMPOSE_DIR" && docker compose restart ollama >>"$LOG_FILE" 2>&1); then
    log "restart command completed, verifying recovery"
    sleep 6
    verify=$(probe)
    verify_content=$(echo "$verify" | jq -r '.message.content // ""' 2>/dev/null || true)
    verify_done=$(echo "$verify" | jq -r '.done // false' 2>/dev/null || true)
    if [ "$verify_done" = "true" ] && [ -n "$verify_content" ] && ! echo "$verify_content" | grep -qE '^[?[:space:]]{10,}$'; then
      log "RECOVERED: ollama healthy after restart"
    else
      log "STILL UNHEALTHY after restart — needs manual attention"
    fi
  else
    log "ERROR: docker compose restart failed"
  fi
else
  log "healthy"
fi
