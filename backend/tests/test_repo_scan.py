"""The repository scanner reads manifests, and only manifests.

These fixtures stand in for whole repositories. They are deliberately
realistic rather than minimal -- a real package.json carries fifty
dependencies of which three matter, and a scanner that only works on a
hand-picked five would not survive contact with an actual project.

The scanner must be able to say "I could not tell", so there are cases
with nothing to find as well as cases full of signal.
"""

from __future__ import annotations

from whichcloud.connections.repo_scan import scan_manifests, workload_type_hint


NEXT_APP = {
    "package.json": """
    {
      "name": "storefront",
      "dependencies": {
        "next": "15.0.0",
        "react": "^18.3.1",
        "react-dom": "^18.3.1",
        "tailwindcss": "^3.4.0",
        "prisma": "^5.20.0",
        "ioredis": "^5.4.1",
        "bullmq": "^5.13.0",
        "@sendgrid/mail": "^8.1.3",
        "zod": "^3.23.8"
      },
      "devDependencies": { "typescript": "^5.6.2", "eslint": "^9.0.0" }
    }
    """
}

PY_API = {
    "backend/requirements.txt": """
    # core
    fastapi>=0.115
    uvicorn[standard]>=0.32
    psycopg[binary]>=3.2
    celery==5.4.0
    elasticsearch>=8.15
    openai>=1.50
    pytest>=8.0  # dev only
    """
}

COMPOSE_STACK = {
    "docker-compose.yml": """
    services:
      api:
        build: ./api
        ports: ["8000:8000"]
      worker:
        build: ./api
        command: celery -A app worker
      db:
        image: postgres:16-alpine
      cache:
        image: redis:7-alpine
      search:
        image: elasticsearch:8.15.0
    """
}

STATIC_SITE = {
    "package.json": """
    {"name": "brochure", "dependencies": {"astro": "^4.0.0"}}
    """
}


def test_a_next_app_is_read_as_web_with_its_services():
    scan = scan_manifests(NEXT_APP)
    assert "JavaScript/TypeScript" in scan.languages
    assert "Next.js" in scan.frameworks
    assert workload_type_hint(scan) == "web"
    assert "queue" in scan.signals()      # bullmq
    assert "email" in scan.signals()      # @sendgrid/mail
    assert {"PostgreSQL", "Redis"} <= set(scan.datastores)  # prisma, ioredis


def test_a_python_api_is_read_as_api_with_search_and_ai():
    scan = scan_manifests(PY_API)
    assert "Python" in scan.languages
    assert "FastAPI" in scan.frameworks
    assert workload_type_hint(scan) == "api"
    assert {"queue", "search", "ai_language"} <= scan.signals()
    assert "PostgreSQL" in scan.datastores


def test_compose_images_are_stronger_evidence_than_client_libraries():
    """A `postgres:16` service IS a database; a client only talks to one."""
    scan = scan_manifests(COMPOSE_STACK)
    assert {"PostgreSQL", "Redis", "Elasticsearch"} <= set(scan.datastores)
    # api + worker are the application; the three stores are not counted
    assert scan.service_count == 2


def test_every_detection_names_the_file_it_came_from():
    """A detection that cannot cite its source does not belong in a bill."""
    scan = scan_manifests({**NEXT_APP, **PY_API})
    assert scan.detections
    for d in scan.detections:
        assert d.evidence, f"{d.signal} has no evidence"
        assert d.source in scan.files_read or d.source.endswith((".txt", ".json", ".toml"))


def test_a_plain_static_site_yields_no_infrastructure_signals():
    """Absence of signal is a real answer, not a reason to invent one."""
    scan = scan_manifests(STATIC_SITE)
    assert scan.datastores == []
    assert scan.signals() == set()


def test_an_empty_repository_is_not_guessed_at():
    scan = scan_manifests({})
    assert scan.languages == []
    assert scan.detections == []
    assert workload_type_hint(scan) is None


def test_a_substring_cannot_trigger_a_detection():
    """`redistribute` is not Redis; `openai-mock` is not OpenAI."""
    scan = scan_manifests(
        {"package.json": '{"dependencies": {"redistribute": "1.0.0", "my-openai-mock": "2.0.0"}}'}
    )
    assert scan.datastores == []
    assert scan.signals() == set()


def test_an_unparseable_manifest_is_reported_not_swallowed():
    """Silently skipping the file that names the database would understate
    the architecture, and the bill with it."""
    scan = scan_manifests({"package.json": "{ this is not json"})
    assert scan.unreadable == ["package.json"]
    assert "package.json" not in scan.files_read


def test_a_compose_image_outranks_a_client_library_as_evidence():
    """Found by scanning this repository: its compose file names
    `pgvector/pgvector:pg16` while backend/pyproject.toml declares
    `psycopg`. Sorting files alphabetically put pyproject first, so the
    client library was cited for a datastore the compose file names
    outright -- the opposite of what the code claimed to do."""
    scan = scan_manifests(
        {
            "backend/pyproject.toml": '[project]\ndependencies = ["psycopg[binary]>=3.2"]\n',
            "infra/docker-compose.yml": "services:\n  db:\n    image: pgvector/pgvector:pg16\n",
        }
    )
    assert "PostgreSQL" in scan.datastores
    evidence = [d.evidence for d in scan.detections if d.signal == "datastore"]
    assert any("pgvector" in e for e in evidence), evidence
    assert not any("psycopg" in e for e in evidence), evidence
