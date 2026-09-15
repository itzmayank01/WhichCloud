#!/usr/bin/env bash
set -e

# 1️⃣ Infra (Postgres + Redis)
docker compose -f infra/docker-compose.yml up -d

# 2️⃣ Backend
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
