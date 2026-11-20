"""Read a repository's manifests and say what infrastructure it implies.

The existing GitHub integration prices Terraform you have already written.
This reads an ordinary application repository -- one with no IaC at all --
and works out what it would need to run: a database, a queue, a search
index, an AI provider, and so on.

Two rules shape the whole module.

**Deterministic, not inferred.** Every detection comes from a dependency
name or a service image in a manifest the repository actually contains. No
model is asked to guess. That keeps a re-scan of an unchanged repository
identical, costs nothing per scan, and cannot be exhausted by a quota --
which matters, because `STATUS.md` records the LLM classifier running out
of tokens part-way through an evaluation.

**Shape, never scale.** A repository can tell you it talks to Postgres and
runs Celery workers. It cannot tell you how many users you have, how much
egress you serve, or what you are willing to spend. Those have to be asked
for. Anything here that pretended otherwise would produce a confident and
fictional bill, which is the one thing this product must not do.

So a scan answers "what services does this need?" and the caller supplies
the traffic and budget before anything is priced.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

__all__ = ["Detection", "RepoScan", "scan_manifests", "MANIFESTS"]


#: The compose filenames, named once: they are matched in three places
#: (the manifest list, the two-pass ordering, and the dispatch below).
COMPOSE_FILENAMES: tuple[str, ...] = ("docker-compose.yml", "docker-compose.yaml")
SERVERLESS_FILENAMES: tuple[str, ...] = ("serverless.yml", "serverless.yaml", "vercel.json")

#: Manifests worth reading, in the order we would want them in a report.
#: Paths are matched against the repository's file list case-sensitively,
#: at the root and one level down (a monorepo usually puts them in
#: `backend/`, `api/`, `web/` rather than at the top).
MANIFESTS: tuple[str, ...] = (
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "go.mod",
    "Gemfile",
    "pom.xml",
    "composer.json",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "serverless.yml",
    "serverless.yaml",
    "vercel.json",
)


@dataclass(frozen=True)
class Detection:
    """One signal, and the exact thing in the repository that produced it.

    `evidence` exists so a report can say "queue: celery in
    backend/requirements.txt" rather than "queue: yes". The engine's cost
    reports already name the SKU behind every line item; a detection that
    cannot name its source does not belong in the same product.
    """

    signal: str
    evidence: str
    source: str


@dataclass
class RepoScan:
    """What a repository implies, and what could not be read."""

    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    datastores: list[str] = field(default_factory=list)
    detections: list[Detection] = field(default_factory=list)
    #: Long-running services declared in docker-compose, excluding the
    #: datastores, which are counted separately. A rough floor for how many
    #: things need to run, not a headcount of instances.
    service_count: int = 0
    files_read: list[str] = field(default_factory=list)
    #: Manifests that were found but could not be parsed. Reported rather
    #: than swallowed: a scan that silently skipped the one file naming the
    #: database would understate the architecture and the bill with it.
    unreadable: list[str] = field(default_factory=list)

    def signals(self) -> set[str]:
        return {d.signal for d in self.detections}


#: dependency-name pattern -> signal.
#:
#: Matched against the NAME of a declared dependency, not the whole file,
#: so a mention in a comment or a changelog cannot trigger one. Patterns
#: are deliberately narrow: "redis" means the redis client, and a package
#: merely containing the substring (say "redistribute") must not match,
#: hence the anchoring in `_match`.
_DEPENDENCY_SIGNALS: tuple[tuple[str, str], ...] = (
    # queues and background work
    (r"celery|bullmq?|sidekiq|rq|dramatiq|resque|bee-queue|agenda", "queue"),
    # event streaming, which is a different shape from a work queue
    (r"kafkajs?|kafka-go|sarama|confluent-kafka|aiokafka|pulsar-client|@aws-sdk/client-kinesis", "event_streaming"),
    # search
    (r"elasticsearch|@elastic/elasticsearch|opensearch-py|meilisearch|typesense|algoliasearch", "search"),
    # analytics / warehouse work, as opposed to ordinary CRUD
    (r"dbt-core|pyspark|clickhouse-driver|duckdb|snowflake-connector-python|apache-airflow", "analytics"),
    # transactional email
    (r"sendgrid|@sendgrid/mail|mailgun|nodemailer|postmark|resend|boto3-ses", "email"),
    # push / SMS, distinct from email
    (r"twilio|firebase-admin|onesignal|expo-server-sdk", "notifications"),
    # AI, split the way the Requirement splits it
    (r"openai|anthropic|@anthropic-ai/sdk|google-genai|cohere|litellm|langchain", "ai_language"),
    (r"opencv-python|ultralytics|torchvision|face-recognition|@tensorflow-models", "ai_vision"),
    (r"transformers|torch|tensorflow|scikit-learn|xgboost", "ai"),
    # serverless deployment targets
    (r"serverless|@vercel/node|aws-lambda|azure-functions|functions-framework", "serverless"),
)

#: dependency-name pattern -> datastore label. Kept apart from signals
#: because these name a thing to provision and price, not a capability.
_DATASTORE_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    (r"psycopg2?|psycopg|pg|postgres|postgresql|asyncpg|prisma|sequelize|typeorm", "PostgreSQL"),
    (r"mysqlclient|mysql2|pymysql|mariadb", "MySQL"),
    (r"redis|ioredis|aioredis", "Redis"),
    (r"pymongo|mongoose|mongodb|motor", "MongoDB"),
    (r"cassandra-driver|scylla", "Cassandra"),
    (r"boto3|@aws-sdk/client-dynamodb|aioboto3", "DynamoDB or S3"),
)

#: container image prefix -> datastore label, for docker-compose services.
#: An image is stronger evidence than a client library: a `postgres:16`
#: service IS a database, where `psycopg` only means something talks to one.
_IMAGE_DATASTORES: tuple[tuple[str, str], ...] = (
    (r"^postgres|^postgis|^pgvector", "PostgreSQL"),
    (r"^mysql|^mariadb", "MySQL"),
    (r"^redis|^valkey", "Redis"),
    (r"^mongo", "MongoDB"),
    (r"^elasticsearch|^opensearch", "Elasticsearch"),
    (r"^rabbitmq", "RabbitMQ"),
    (r"^(confluentinc/)?cp-kafka|^bitnami/kafka|^apache/kafka", "Kafka"),
    (r"^clickhouse", "ClickHouse"),
    (r"^minio", "S3-compatible storage"),
)

#: dependency-name pattern -> (framework label, workload_type hint).
#: The hint is the engine's own vocabulary, so the caller can map a scan
#: onto a Requirement without a second translation table.
_FRAMEWORKS: tuple[tuple[str, str, str], ...] = (
    (r"^next$|^nextjs$", "Next.js", "web"),
    (r"^nuxt$|^@nuxt/", "Nuxt", "web"),
    (r"^react$|^react-dom$", "React", "web"),
    (r"^vue$|^@vue/", "Vue", "web"),
    (r"^svelte|^@sveltejs/", "Svelte", "web"),
    (r"^django$", "Django", "web"),
    (r"^flask$", "Flask", "api"),
    (r"^fastapi$", "FastAPI", "api"),
    (r"^express$|^koa$|^fastify$|^@nestjs/core$", "Node HTTP service", "api"),
    (r"^rails$|^sinatra$", "Rails", "web"),
    (r"^gin-gonic/gin$|^labstack/echo", "Go HTTP service", "api"),
    (r"^apache-airflow$|^prefect$|^dagster$", "Airflow", "batch"),
    (r"^spring-boot", "Spring Boot", "api"),
)


def _match(pattern: str, name: str) -> bool:
    """Whole-name match, so `redis` does not fire on `redistribute`."""
    return re.fullmatch(pattern, name) is not None or any(
        re.fullmatch(p, name) is not None for p in pattern.split("|")
    )


def _normalise(name: str) -> str:
    """A dependency name without version, extras or scope noise."""
    name = name.strip().lower()
    name = re.split(r"[\[<>=!~;\s]", name, maxsplit=1)[0]
    return name.strip()


def _deps_from_package_json(text: str) -> list[str]:
    data = json.loads(text)
    names: list[str] = []
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        block = data.get(key)
        if isinstance(block, dict):
            names.extend(block)
    return names


def _deps_from_requirements(text: str) -> list[str]:
    names = []
    for line in text.splitlines():
        line = line.strip()
        # -r other.txt, -e ., --index-url ... are directives, not packages
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        names.append(line)
    return names


def _deps_from_pyproject(text: str) -> list[str]:
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
        return []
    data = tomllib.loads(text)
    project = data.get("project") or {}
    names = list(project.get("dependencies") or [])
    for extra in (project.get("optional-dependencies") or {}).values():
        names.extend(extra)
    # Poetry keeps its dependencies somewhere else entirely.
    poetry = ((data.get("tool") or {}).get("poetry") or {}).get("dependencies") or {}
    names.extend(poetry)
    return names


def _deps_from_go_mod(text: str) -> list[str]:
    r"""Module paths from require blocks and single-line requires.

    Split on whitespace rather than matched with a regex. The pattern this
    replaced -- `([a-z0-9\-./]+\.[a-z]{2,}/[^\s]+)\s+v` -- was ambiguous:
    its first class already contains `.` and `/`, so every one of those
    characters could be consumed by either the class or the literals that
    follow, and the engine backtracks through the combinations. That is
    super-linear on a long line, and this parses files from repositories we
    do not control, so it is a denial-of-service shape rather than a
    performance nit. Splitting is linear and reads better besides.
    """
    names = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue
        parts = line.split()
        if parts[0] == "require":
            parts = parts[1:]
        # `github.com/gin-gonic/gin v1.9.1` -- a path, then a v-prefixed
        # version. Anything else in a go.mod (module, go, toolchain, the
        # bare parentheses of a require block) fails one of these.
        if len(parts) < 2 or not parts[1].startswith("v"):
            continue
        module = parts[0]
        host, _, rest = module.partition("/")
        if "." not in host or not rest:
            continue
        names.extend(_go_candidates(module))
    return names


def _go_candidates(module: str) -> list[str]:
    """The names a Go module path might be recognised under.

    Go import paths do not put the package name in one predictable place.
    `github.com/gin-gonic/gin` ends with it, `gorm.io/driver/postgres`
    ends with it too, but `github.com/redis/go-redis/v9` ends with a major
    version suffix and carries the useful word one and two segments back.
    Taking only the last two segments -- which is what this did first --
    reduced that to "go-redis/v9" and matched nothing, so a Go service
    using Redis and Postgres reported neither.

    So offer several readings of the path and let the patterns decide.
    They are anchored whole-name matches, so an extra candidate can only
    match something it genuinely names.
    """
    segments = [s for s in module.split("/") if s]
    # a trailing major-version suffix is Go module notation, not a name
    if len(segments) > 1 and re.fullmatch(r"v[0-9]+", segments[-1]):
        segments = segments[:-1]
    if not segments:
        return []
    candidates = {"/".join(segments), segments[-1]}
    if len(segments) >= 2:
        candidates.add("/".join(segments[-2:]))
        candidates.add(segments[-2])
    return sorted(candidates)


def _compose_services(text: str) -> tuple[list[str], int]:
    """`(images, non-datastore service count)` from a docker-compose file."""
    try:
        import yaml
    except ModuleNotFoundError:  # pragma: no cover
        return [], 0
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return [], 0
    services = data.get("services")
    if not isinstance(services, dict):
        return [], 0
    images: list[str] = []
    app_services = 0
    for spec in services.values():
        if not isinstance(spec, dict):
            continue
        image = str(spec.get("image") or "").strip()
        if image:
            images.append(image)
            if not _image_datastore(image):
                app_services += 1
        else:
            # `build:` with no image is the repository's own code
            app_services += 1
    return images, app_services


def _image_datastore(image: str) -> str | None:
    bare = image.split("@", 1)[0].split(":", 1)[0].lower()
    for pattern, label in _IMAGE_DATASTORES:
        if re.search(pattern, bare):
            return label
    return None


#: filename -> (parser, language label). The language is what the manifest
#: proves is present, not a guess from file extensions.
_PARSERS = {
    "package.json": (_deps_from_package_json, "JavaScript/TypeScript"),
    "requirements.txt": (_deps_from_requirements, "Python"),
    "pyproject.toml": (_deps_from_pyproject, "Python"),
    "go.mod": (_deps_from_go_mod, "Go"),
}


def _read_compose(path: str, text: str, scan: RepoScan, datastores: dict[str, str]) -> None:
    try:
        images, app_services = _compose_services(text)
    except Exception:
        scan.unreadable.append(path)
        return
    scan.files_read.append(path)
    scan.service_count = max(scan.service_count, app_services)
    for image in images:
        label = _image_datastore(image)
        if label:
            datastores.setdefault(label, f"{image} in {path}")


def _read_dependencies(
    path: str,
    name: str,
    text: str,
    scan: RepoScan,
    datastores: dict[str, str],
    note,
) -> None:
    parser, language = _PARSERS[name]
    try:
        raw_names = parser(text)
    except Exception:
        # A manifest we recognise but cannot parse is reported, not
        # skipped -- see RepoScan.unreadable.
        scan.unreadable.append(path)
        return

    scan.files_read.append(path)
    if language not in scan.languages:
        scan.languages.append(language)

    for raw in raw_names:
        dep = _normalise(raw)
        if not dep:
            continue
        for pattern, signal in _DEPENDENCY_SIGNALS:
            if _match(pattern, dep):
                note(signal, f"{dep} in {path}", path)
        for pattern, label in _DATASTORE_DEPENDENCIES:
            if _match(pattern, dep):
                datastores.setdefault(label, f"{dep} in {path}")
        for pattern, label, _hint in _FRAMEWORKS:
            if re.fullmatch(pattern, dep) and label not in scan.frameworks:
                scan.frameworks.append(label)


def _ordered_for_evidence(files: dict[str, str]) -> list[tuple[str, str]]:
    """Compose files first, because an image outranks a client library.

    A `postgres:16` service IS a database; `psycopg` only proves something
    talks to one, possibly a managed instance that is not in this repo at
    all. First-wins over one alphabetical pass gave the opposite result:
    backend/pyproject.toml sorts before infra/docker-compose.yml, so
    "psycopg" was cited for a stack whose compose file names the image.
    """
    compose = {
        p: t for p, t in files.items()
        if p.rsplit("/", 1)[-1] in COMPOSE_FILENAMES
    }
    rest = {p: t for p, t in files.items() if p not in compose}
    return sorted(compose.items()) + sorted(rest.items())


def scan_manifests(files: dict[str, str]) -> RepoScan:
    """Turn `{path: contents}` into a RepoScan.

    Pure: no network, no clock, no environment. The fetching lives in
    `scan_repo`, so this can be exercised against fixtures that stand in
    for whole repositories.
    """
    scan = RepoScan()
    seen_signals: dict[str, Detection] = {}
    datastores: dict[str, str] = {}  # label -> evidence, first wins

    def note(signal: str, evidence: str, source: str) -> None:
        # One detection per signal: the first piece of evidence is enough
        # to justify provisioning the thing, and a report listing "queue"
        # four times reads as noise rather than confidence.
        seen_signals.setdefault(signal, Detection(signal, evidence, source))

    for path, text in _ordered_for_evidence(files):
        name = path.rsplit("/", 1)[-1]
        if name in COMPOSE_FILENAMES:
            _read_compose(path, text, scan, datastores)
        elif name in SERVERLESS_FILENAMES:
            scan.files_read.append(path)
            note("serverless", name, path)
        elif name == "Dockerfile":
            scan.files_read.append(path)
        elif name in _PARSERS:
            _read_dependencies(path, name, text, scan, datastores, note)

    scan.detections = sorted(seen_signals.values(), key=lambda d: d.signal)
    scan.datastores = sorted(datastores)
    for label, evidence in sorted(datastores.items()):
        scan.detections.append(Detection("datastore", evidence, evidence.split(" in ")[-1]))
    scan.detections.sort(key=lambda d: (d.signal, d.evidence))
    return scan


def workload_type_hint(scan: RepoScan) -> str | None:
    """The engine's workload_type this repository looks like, or None.

    None rather than a default on purpose: "we could not tell" is a real
    answer, and the caller should ask rather than be handed "web" as though
    it had been read off the code.
    """
    for _pattern, label, hint in _FRAMEWORKS:
        if label in scan.frameworks:
            return hint
    return None


def fetch_manifests(
    repo_url: str, branch: str = "main", token: str = "", max_depth: int = 2
) -> dict[str, str]:
    """`{path: contents}` for the manifests in a GitHub repository.

    Only the files in MANIFESTS are fetched, from the root and `max_depth`
    levels down -- a monorepo keeps them in `backend/`, `api/`, `web/`
    rather than at the top. Nothing else is read: a scan has no business
    downloading application source, and not doing so keeps this well
    inside GitHub's rate limits on a repository of any size.

    Raises ValueError with a reason a person can act on, matching how the
    rest of connections/ separates explainable failures from a generic
    "could not reach the provider".
    """
    import httpx

    from .github import _MAX_FILES, _TIMEOUT, _fetch_file, _list_dir, _owner_repo

    owner, repo = _owner_repo(repo_url)
    if not token.strip():
        raise ValueError("A GitHub token that can read this repository is required.")

    wanted = set(MANIFESTS)
    found: dict[str, str] = {}

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    with httpx.Client(timeout=_TIMEOUT, headers=headers) as client:

        def walk(dir_path: str, depth: int) -> None:
            if len(found) >= _MAX_FILES:
                return
            for entry in _list_dir(client, owner, repo, branch, dir_path):
                base = entry.path.rsplit("/", 1)[-1]
                if entry.kind == "dir":
                    # node_modules and vendor directories hold thousands of
                    # manifests belonging to dependencies, not to this
                    # project; reading them would describe the wrong thing.
                    if base in ("node_modules", "vendor", ".git", "dist", "build"):
                        continue
                    if depth < max_depth:
                        walk(entry.path, depth + 1)
                    continue
                if base in wanted:
                    found[entry.path] = _fetch_file(client, owner, repo, branch, entry.path)

        walk("", 0)

    if not found:
        raise ValueError(
            f"No recognisable manifests (package.json, requirements.txt, "
            f"pyproject.toml, go.mod, docker-compose.yml, ...) were found in "
            f"the top {max_depth} levels of {owner}/{repo} on branch {branch!r}."
        )
    return found


def scan_repo(repo_url: str, branch: str = "main", token: str = "") -> RepoScan:
    """Fetch a repository's manifests and report what they imply."""
    return scan_manifests(fetch_manifests(repo_url, branch=branch, token=token))
