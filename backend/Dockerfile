# The pricing engine, for a host that runs containers (Railway, Render, Fly).
#
# Two things here are not boilerplate and are the reasons this file exists:
#
#   1. $PORT is assigned by the platform at runtime, not chosen by us. Binding
#      a fixed 8010 makes the container start cleanly, pass no health check,
#      and get killed -- which reads as a crash rather than as the wrong port.
#      Hence the shell form of CMD, so $PORT is expanded when the container
#      starts rather than baked in when it is built.
#
#   2. The price catalog is NOT baked into the image. First run downloads a
#      ~300 MB EC2 catalog and ingests 36,761 rows into Postgres; doing that
#      at build time would put a stale copy in every layer and rebuild it on
#      every deploy. It is a one-off job against the database instead -- see
#      DEPLOY.md.

FROM python:3.12-slim

# Postgres client libraries for psycopg. Removed from the layer afterwards so
# the build tools do not travel to production.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so a code change does not re-resolve the whole tree.
COPY pyproject.toml ./
COPY whichcloud/__init__.py whichcloud/
RUN pip install --no-cache-dir -e .

COPY . .

# Unbuffered, or nothing written to stdout appears in the platform's log
# viewer until the process exits -- which for a server is never.
ENV PYTHONUNBUFFERED=1

EXPOSE 8010

CMD uvicorn whichcloud.api:app --host 0.0.0.0 --port ${PORT:-8010}
