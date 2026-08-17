#!/usr/bin/env bash
# Bring the whole stack up, from whatever state it is in.
#
# Docker Desktop on this machine stops on its own. The containers always exit
# with code 0, there are no crash reports and no memory kills, so something
# asks it to shut down cleanly rather than it falling over. What is certain is
# that nothing brings it back: Docker is not registered as a login item and
# its own settings carry AutoStartError, so once down it stays down.
#
# Recovery is therefore scripted rather than remembered. Safe to run at any
# time; every step is a no-op if that piece is already healthy.
#
#     ./scripts/up.sh

set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

say() { printf "  %-22s %s\n" "$1" "$2"; }

# ── Docker daemon ──
if ! docker info >/dev/null 2>&1; then
  say "docker" "not running, starting Docker Desktop"
  open -a Docker
  for _ in $(seq 1 40); do
    docker info >/dev/null 2>&1 && break
    sleep 5
  done
fi
docker info >/dev/null 2>&1 || { say "docker" "FAILED to start"; exit 1; }
say "docker" "up"

# ── containers ──
docker start whichcloud-db whichcloud-cache >/dev/null 2>&1
for _ in $(seq 1 20); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' whichcloud-db 2>/dev/null)" = "healthy" ] && break
  sleep 2
done
say "postgres" "$(docker inspect -f '{{.State.Health.Status}}' whichcloud-db 2>/dev/null || echo missing)"
say "redis" "$(docker inspect -f '{{.State.Health.Status}}' whichcloud-cache 2>/dev/null || echo missing)"

# ── api ──
# Always restarted rather than left alone if it answers. A running server holds
# the Python it started with, so an edit to the layout or the renderer is
# invisible: the page looks unchanged, nothing errors, and the obvious
# conclusion is that the change did not work. --reload makes later edits take
# effect without this.
#
# Port 8010, because campus-connect-surrealdb-1 publishes 8000 with
# restart:always and whichever process reaches the port first keeps it.
#
# ~/.zshrc is sourced explicitly rather than relying on a login shell: the keys
# live there and zsh reads it for interactive shells only, so `zsh -lc` starts
# a shell that has never heard of them and /describe reports "no
# language-model credentials found" -- which reads as a missing key rather than
# a missing environment.
lsof -ti:8010 | xargs kill 2>/dev/null
sleep 1
( cd backend && zsh -c \
    'source ~/.zshrc >/dev/null 2>&1; source .venv/bin/activate && \
     nohup python3 -m uvicorn whichcloud.api:app \
     --host 127.0.0.1 --port 8010 --reload >/tmp/wc-api.log 2>&1 &' )
for _ in $(seq 1 30); do
  curl -sf --max-time 3 http://127.0.0.1:8010/health >/dev/null 2>&1 && break
  sleep 2
done

prices=$(curl -s --max-time 5 http://127.0.0.1:8010/health 2>/dev/null \
  | python3 -c 'import json,sys; print(f"{json.load(sys.stdin).get(chr(112)+chr(114)+chr(105)+chr(99)+chr(101)+chr(115),0):,} prices")' 2>/dev/null)
say "api" "${prices:-unreachable}"

readers=$(cd backend && zsh -c 'source ~/.zshrc >/dev/null 2>&1; source .venv/bin/activate && python3 -c "
from whichcloud.architecture.readers import configured
c = configured()
print(\", \".join(f\"{k} x{v}\" for k, v in c.items()) or \"none\")
"' 2>/dev/null)
say "model keys" "${readers:-unknown}"

# ── web ──
if curl -sf --max-time 5 -o /dev/null http://localhost:3001/ 2>/dev/null; then
  say "web" "up on :3001"
else
  say "web" "not running — cd frontend && npm run dev -- -p 3001"
fi
