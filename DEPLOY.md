# Deploying WhichCloud

Frontend on Vercel, engine and data stores on Railway.

**Pushing to GitHub does not deploy anything on its own.** It hosts the source.
Vercel and Railway each have to be pointed at this repository once; after that
they redeploy on every push to `main`, and *then* a push updates the live site.

WhichCloud is four services, not a static site:

| Part | Host | Why it cannot be skipped |
|---|---|---|
| Next.js frontend | Vercel | the interface |
| FastAPI engine | Railway | every price, diagram and answer comes from it |
| Postgres + pgvector | Railway | holds the 36,761-row price catalog |
| Redis | Railway | caches price lookups; optional but the engine is slow without it |

Order matters: the frontend needs the engine's URL, and the engine needs the
frontend's origin. Do the backend first, then the frontend, then come back and
set `WHICHCLOUD_ALLOWED_ORIGINS`.

---

## 1 — Postgres and Redis

In a new Railway project: **New → Database → PostgreSQL**, then again for
**Redis**.

Postgres needs pgvector. Open the Postgres service's *Data* tab and run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Copy each service's connection string from its *Variables* tab. Railway calls
them `DATABASE_URL` and `REDIS_URL`; this app reads `WHICHCLOUD_DSN` and
`WHICHCLOUD_REDIS_URL`, so the names have to be mapped in step 2 — they are
not interchangeable and nothing warns you.

## 2 — The engine

**New → GitHub Repo →** this repo. Set **Root Directory** to `backend`, so
Railway builds `backend/Dockerfile` rather than looking for a project at the
repository root.

Variables:

```
WHICHCLOUD_DSN=${{Postgres.DATABASE_URL}}
WHICHCLOUD_REDIS_URL=${{Redis.REDIS_URL}}
GEMINI_API_KEY=<from aistudio.google.com/apikey>
```

The `${{Service.VAR}}` form is Railway's reference syntax — it keeps working
if a database is recreated, where a pasted literal silently points at the old
one.

Do not set `PORT`. Railway assigns it and the Dockerfile reads it; overriding
it is the usual cause of a container that starts, fails its health check and
is killed, which reads as a crash rather than a wrong port.

Then **Settings → Networking → Generate Domain**. That URL is the API base.

### Load the catalog

The image deliberately ships without prices — baking a ~300 MB EC2 catalog
into every layer would rebuild it on each deploy. Ingest once, against the
deployed database, from your own machine:

```bash
cd backend
WHICHCLOUD_DSN='<the Postgres connection string>' \
  .venv/bin/python scripts/ingest_prices.py --region india
```

Takes a few minutes the first time. Re-run it to add a region or refresh
prices; it is idempotent.

Check it worked:

```bash
curl https://<your-railway-domain>/health
```

Expect `"prices": 36761` (or more). `"prices": 0` means the ingest did not
reach this database — almost always the DSN pointing somewhere else.

## 3 — The frontend

On Vercel: **Add New → Project →** this repo, **Root Directory** `frontend`.

Environment variables:

```
NEXT_PUBLIC_API_URL=https://<your-railway-domain>
NEXT_PUBLIC_SITE_URL=https://<your-vercel-domain>
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
CLERK_SECRET_KEY=sk_live_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_SIGN_IN_FALLBACK_REDIRECT_URL=/dashboard
NEXT_PUBLIC_CLERK_SIGN_UP_FALLBACK_REDIRECT_URL=/dashboard
```

`NEXT_PUBLIC_API_URL` takes no trailing slash, and it is read at **build**
time as well as at runtime — changing it needs a redeploy, not a restart.

### Clerk needs a production instance

The local `.env.local` carries `pk_test`/`sk_test`. That is a *development*
instance: fine on localhost and previews, not meant to serve a real domain.
In the Clerk dashboard create a **production instance** for your Vercel
domain, add the DNS records it asks for, and use its `pk_live`/`sk_live`
pair. Test keys on a live domain will sign people in and then misbehave in
ways that look like application bugs.

## 4 — Let the engine answer the frontend

Back on Railway, add:

```
WHICHCLOUD_ALLOWED_ORIGINS=https://<your-vercel-domain>
```

and, to keep preview deployments working:

```
WHICHCLOUD_ALLOWED_ORIGIN_REGEX=^https://<project>-[a-z0-9-]+\.vercel\.app$
```

Skip this and the site loads, then every request fails. In the browser that
looks exactly like the engine being down; the actual cause is a CORS refusal,
visible only in the network tab.

---

## After this

Both hosts watch `main`. A push redeploys the changed side — Vercel rebuilds
when `frontend/` changes, Railway when `backend/` does.

## When something is wrong

| What you see | Where to look |
|---|---|
| Site loads, every number missing | CORS — step 4. Check the browser network tab, not the server logs |
| `"prices": 0` from `/health` | the ingest ran against a different database than the engine reads |
| Requests go to `127.0.0.1:8010` | `NEXT_PUBLIC_API_URL` unset at **build** time; set it and redeploy |
| Container starts then dies | `PORT` overridden, or Postgres unreachable from the engine |
| Sign-in loops back to sign-in | development Clerk keys on a production domain |
| Advisor says every model is out of capacity | no LLM key set, or the day's free quota is spent — add `GEMINI_API_KEY_2` |
