#!/usr/bin/env bash
# Bring the whole stack up, from whatever state it is in.
#
# Docker Desktop on this machine stops on its own. What the evidence says:
# the containers always exit with code 0, there are no crash reports in
# DiagnosticReports and no jetsam or memory kills in the system log -- so
# something asks it to shut down cleanly, it does not fall over. Resource
# Saver is enabled in its effective config and is the likeliest cause.
#
# What is certain is that nothing brings it back. Docker is not registered as
# a login item, and its own settings carry
#
#     AutoStartError = "option disabled because operation is not permitted
#                       when registering app service"
#
# so once it is down it stays down until someone opens it. That is why the
# database kept disappearing mid-session.
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
# Port 8010, because campus-connect-surrealdb-1 publishes 8000 with
# restart:always. Whichever process reached the port first kept it, so the
# API came up on some Docker restarts and not others.
# ~/.zshrc is sourced explicitly rather than relying on a login shell. The
# keys live in .zshrc, which zsh reads for interactive shells only, so
# `zsh -lc` starts a login shell that has never heard of them. Starting the
# service that way leaves
# /describe reporting "no language-model credentials found", which reads as a
# missing key rather than a missing environment -- that exact confusion has
# already cost an afternoon.
if ! curl -sf --max-time 5 http://127.0.0.1:8010/health >/dev/null 2>&1; then
  say "api" "not responding, restarting"
  lsof -ti:8010 | xargs kill 2>/dev/null
  sleep 1
  ( cd backend && zsh -c \
      'source ~/.zshrc >/dev/null 2>&1; source .venv/bin/activate && \
       nohup python3 -m uvicorn whichcloud.api:app \
       --host 127.0.0.1 --port 8010 >/tmp/wc-api.log 2>&1 &' )
  # Long enough for the first request to build a connection pool against a
  # database that has itself only just come up.
  for _ in $(seq 1 30); do
    curl -sf --max-time 3 http://127.0.0.1:8010/health >/dev/null 2>&1 && break
    sleep 2
  done
fi

prices=$(curl -s --max-time 5 http://127.0.0.1:8010/health 2>/dev/null \
  | python3 -c 'import json,sys; print(f"{json.load(sys.stdin).get(chr(112)+chr(114)+chr(105)+chr(99)+chr(101)+chr(115),0):,} prices")' 2>/dev/null)
say "api" "${prices:-unreachable}"

readers=$(cd backend && zsh -c 'source ~/.zshrc >/dev/null 2>&1; source .venv/bin/activate && python3 -c "
from whichcloud.intake import available_providers
print(\", \".join(available_providers()) or \"none — /describe will refuse\")
"' 2>/dev/null)
say "model readers" "${readers:-unknown}"

# ── web ──
if curl -sf --max-time 5 -o /dev/null http://localhost:3001/ 2>/dev/null; then
  say "web" "up on :3001"
else
  say "web" "not running — cd frontend && npm run dev -- -p 3001"
fi
