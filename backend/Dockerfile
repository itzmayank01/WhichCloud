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

# Postgres client libraries for psycopg, plus unzip/curl to install the AWS
# CLI below. Removed from the layer afterwards so the build tools do not
# travel to production.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl unzip \
    && rm -rf /var/lib/apt/lists/*

# connections/aws_live.py shells out to the `aws` binary directly -- it is
# not a Python dependency pip can install. Without this, FinOps Live's
# live-AWS routes fail the moment they leave a machine that happens to have
# the CLI installed locally (get_aws_cli_path() falls back to a bare "aws"
# that resolves to nothing in this image). The official installer, not the
# Debian package, because slim's apt sources do not reliably carry a current
# awscli build. Credentials come from AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
# / AWS_DEFAULT_REGION at runtime (the CLI reads those directly) -- never
# baked into the image.
RUN curl -sS "https://awscli.amazonaws.com/awscli-exe-linux-$(dpkg --print-architecture | sed 's/amd64/x86_64/;s/arm64/aarch64/').zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/awscliv2.zip /tmp/aws

WORKDIR /app

# Built from the REPO ROOT as build context (not ./backend) -- see
# render.yaml. knowledge.py resolves the techniques knowledge base as
# `Path(__file__).resolve().parents[2] / "knowledge-base" / "techniques"`,
# which is /knowledge-base/techniques once this file lives at
# /app/whichcloud/knowledge.py. That directory sits beside backend/ in the
# repo, not inside it, so a build scoped to ./backend can never see it at
# all -- every route that touches recommendations (recommend, describe,
# compare, techniques, audit, plan) 500'd with "knowledge base not found"
# the moment this ran anywhere but a machine with the full repo checked out.

# Dependencies first, so a code change does not re-resolve the whole tree.
COPY backend/pyproject.toml ./
COPY backend/whichcloud/__init__.py whichcloud/
RUN pip install --no-cache-dir -e .

COPY backend/ .
COPY knowledge-base /knowledge-base

# Unbuffered, or nothing written to stdout appears in the platform's log
# viewer until the process exits -- which for a server is never.
ENV PYTHONUNBUFFERED=1

EXPOSE 8010

CMD uvicorn whichcloud.api:app --host 0.0.0.0 --port ${PORT:-8010}
