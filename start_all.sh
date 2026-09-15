#!/usr/bin/env bash
set -e

# 1️⃣ Infra (Postgres + Redis)
docker compose -f infra/docker-compose.yml up -d

# 2️⃣ Backend
#
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

pushd backend > /dev/null
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -e .
nohup uvicorn whichcloud.api:app --reload --host 127.0.0.1 --port 8010 > backend.log 2>&1 &
popd > /dev/null

# 3️⃣ Frontend
pushd frontend > /dev/null
npm install
nohup npm run dev > frontend.log 2>&1 &
popd > /dev/null

# Summary
echo "✅ All services started:"
echo " • PostgreSQL  → localhost:5432"
echo " • Redis       → localhost:6379"
echo " • Backend API → http://127.0.0.1:8010/docs"
echo " • Frontend UI → http://localhost:3001 (or 3000 if free)"
