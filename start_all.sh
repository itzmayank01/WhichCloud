#!/usr/bin/env bash
set -e

# 1️⃣ Infra (Postgres + Redis)
docker compose -f infra/docker-compose.yml up -d

# 2️⃣ Backend
#
# backend/.env is gitignored -- nothing loads it automatically (no
# python-dotenv in this codebase), so a value set there was silent unless
# something sourced it first. WHICHCLOUD_FINOPS_OWNERS (see auth.py) has no
# safe way to auto-derive the way CLERK_JWKS_URL does below, so without this
# it would need a manual `export` on every fresh shell, which is exactly the
# kind of thing that gets forgotten and quietly leaves FinOps Live 403ing
# for everyone -- or, worse, someone "fixing" that by loosening the check.
if [ -f "backend/.env" ]; then
  set -a
  source backend/.env
  set +a
fi

# current_owner (backend/whichcloud/auth.py) verifies Clerk session tokens
# against CLERK_JWKS_URL. Its docstring says that host can be "derived from
# the publishable key's frontend API host" -- but nothing actually did that
# derivation, so every route that requires a signed-in caller (saved
# architectures, and now FinOps Live and the cloud connection endpoints)
# 401'd locally the moment CLERK_JWKS_URL wasn't set by hand. A Clerk
# publishable key is `pk_(test|live)_<base64 of "<frontend-api-host>$">` --
# it is public by construction (NEXT_PUBLIC_*, shipped in the browser
# bundle), so decoding it here to fill in the default is not exposing
# anything a browser devtools tab wouldn't already show.
if [ -z "$CLERK_JWKS_URL" ]; then
  pk=$(grep -m1 '^NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=' frontend/.env.local 2>/dev/null | cut -d= -f2-)
  if [ -n "$pk" ]; then
    host=$(echo "${pk#pk_test_}" | sed 's/^pk_live_//' | base64 -d 2>/dev/null | tr -d '$')
    if [ -n "$host" ]; then
      export CLERK_JWKS_URL="https://${host}/.well-known/jwks.json"
      echo "Derived CLERK_JWKS_URL=$CLERK_JWKS_URL from frontend/.env.local"
    fi
  fi
fi

# Re-running this script after a crash (or out of habit) used to spawn a
# second uvicorn/next process fighting the first one for the same port,
# leaving an orphan that has to be found and killed by hand. Skip a service
# whose port is already bound instead.
port_is_listening() {
  lsof -i ":$1" -sTCP:LISTEN >/dev/null 2>&1
}

pushd backend > /dev/null
if port_is_listening 8010; then
  echo "Backend already listening on :8010, leaving it running."
else
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi
  source .venv/bin/activate
  pip install -e .
  nohup uvicorn whichcloud.api:app --reload --host 127.0.0.1 --port 8010 > backend.log 2>&1 &
  disown
fi
popd > /dev/null

# 3️⃣ Frontend
pushd frontend > /dev/null
if port_is_listening 3000 || port_is_listening 3001; then
  echo "Frontend already listening on :3000/:3001, leaving it running."
else
  # package-lock.json newer than node_modules means a dependency changed
  # since the last install; otherwise `npm install` is a no-op that still
  # costs several seconds on every single run of this script.
  if [ ! -d "node_modules" ] || [ "package-lock.json" -nt "node_modules" ]; then
    npm install
  fi
  nohup npm run dev > frontend.log 2>&1 &
  disown
fi
popd > /dev/null

# Summary
echo "✅ All services started:"
echo " • PostgreSQL  → localhost:5432"
echo " • Redis       → localhost:6379"
echo " • Backend API → http://127.0.0.1:8010/docs"
echo " • Frontend UI → http://localhost:3001 (or 3000 if free)"
