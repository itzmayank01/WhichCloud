"""Sign in with GitHub, and see only the repos you chose to share.

A GitHub App, not a GitHub OAuth App. The difference is who decides which
repositories WhichCloud can read: an OAuth App inherits the scopes of
whatever personal access token the user hands over; a GitHub App is
installed onto a hand-picked set of repositories (or explicitly "all"),
reads Contents and Metadata and nothing else -- least privilege by
construction, not by us remembering to ask for a narrow scope.

Nothing long-lived is stored here except the mapping from a WhichCloud
owner to the installations they administer (kept in
`pricing.store.save_github_installation`). The user's own GitHub OAuth
token is used once, inline, at the install callback -- to learn their
login and confirm they really do administer the installation -- and then
discarded. Same rule this project already applies to the Terraform-scan
PAT in `connections/github.py`: a token that touches this server is used
for the one call it was needed for and never written anywhere. Every call
afterwards -- listing repos, and in a later phase reading files -- runs on
a fresh installation access token minted from this App's own private key,
which GitHub expires within the hour regardless of what we do.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import threading
import time
from urllib.parse import quote

import httpx
import jwt

APP_ID = os.getenv("GITHUB_APP_ID", "")
APP_SLUG = os.getenv("GITHUB_APP_SLUG", "")
CLIENT_ID = os.getenv("GITHUB_APP_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GITHUB_APP_CLIENT_SECRET", "")
PRIVATE_KEY = os.getenv("GITHUB_APP_PRIVATE_KEY", "")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")

_API = "https://api.github.com"
_TIMEOUT = httpx.Timeout(15.0)

#: How long a `state` value is good for. Generous enough to survive someone
#: reading GitHub's install-confirmation screen slowly; short enough that a
#: leaked or logged callback URL (proxies and browsers both log query
#: strings) cannot be replayed hours later.
STATE_TTL_S = 600


class GitHubAppError(ValueError):
    """A configuration or GitHub-side failure, with a message safe to show."""


def _require_configured() -> None:
    missing = [
        name
        for name, value in (
            ("GITHUB_APP_ID", APP_ID),
            ("GITHUB_APP_SLUG", APP_SLUG),
            ("GITHUB_APP_CLIENT_ID", CLIENT_ID),
            ("GITHUB_APP_CLIENT_SECRET", CLIENT_SECRET),
            ("GITHUB_APP_PRIVATE_KEY", PRIVATE_KEY),
        )
        if not value
    ]
    if missing:
        raise GitHubAppError(
            "GitHub sign-in is not configured on this server (missing "
            + ", ".join(missing) + ")."
        )


def _raise_for_status(resp: httpx.Response, what: str) -> None:
    if resp.status_code == 401 or resp.status_code == 403:
        raise GitHubAppError(f"GitHub refused this request while {what} (check App credentials).")
    if resp.status_code == 404:
        raise GitHubAppError(f"GitHub returned not-found while {what}.")
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise GitHubAppError(f"GitHub error while {what}: {exc.response.status_code}") from exc


# ── state: bind a GitHub redirect back to the WhichCloud owner who started it ──
#
# GitHub's callback is a plain browser navigation, so no Authorization
# header survives it. `state` is the only channel back to "which signed-in
# owner clicked Connect", and it has to prove it was not tampered with or
# replayed. HMAC'd with the App's own client secret rather than
# WHICHCLOUD_SECRETS_KEY: that key is optional today (only Azure needs it),
# and this is not a stored credential, so tying GitHub connect to Azure's
# key would be a needless coupling.


def sign_state(owner: str) -> str:
    _require_configured()
    payload = f"{int(time.time())}.{os.urandom(9).hex()}.{owner}"
    sig = hmac.new(CLIENT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_state(state: str) -> str:
    """The owner id this state was signed for, or raises GitHubAppError."""
    try:
        ts_s, nonce, owner, sig = state.split(".", 3)
    except ValueError as exc:
        raise GitHubAppError("Malformed GitHub redirect (bad state).") from exc
    payload = f"{ts_s}.{nonce}.{owner}"
    expected = hmac.new(CLIENT_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise GitHubAppError("GitHub redirect failed verification (bad state signature).")
    if time.time() - int(ts_s) > STATE_TTL_S:
        raise GitHubAppError("That GitHub connection attempt expired -- please try again.")
    return owner


def install_url(owner: str) -> str:
    """Where to send the browser to install the App and authorize as this owner."""
    _require_configured()
    return f"https://github.com/apps/{APP_SLUG}/installations/new?state={quote(sign_state(owner))}"


# ── the one-time OAuth exchange, at the callback ──


def exchange_code_for_user(code: str) -> dict:
    """The authorizing user's own GitHub identity.

    The user access token this mints is used for exactly the one call below
    and then goes out of scope -- it is never returned, stored, or logged.
    """
    _require_configured()
    with httpx.Client(timeout=_TIMEOUT) as client:
        token_resp = client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, "code": code},
        )
        _raise_for_status(token_resp, "exchanging the authorization code")
        body = token_resp.json()
        user_token = body.get("access_token")
        if not user_token:
            raise GitHubAppError(
                body.get("error_description") or "GitHub did not return an access token."
            )
        user_resp = client.get(
            f"{_API}/user",
            headers={
                "Authorization": f"Bearer {user_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        _raise_for_status(user_resp, "reading the authorizing user")
        return user_resp.json()


# ── app-level auth: a short-lived App JWT, then a short-lived installation token ──


def _app_jwt() -> str:
    _require_configured()
    now = int(time.time())
    # iat backdated 60s for clock skew with GitHub's servers; exp capped at
    # GitHub's own 10-minute ceiling for App JWTs.
    payload = {"iat": now - 60, "exp": now + 540, "iss": APP_ID}
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")


_token_lock = threading.Lock()
#: installation_id -> (token, expires_at). Process-local is fine: a token
#: minted on one server instance works identically from another, so a cache
#: miss after a redeploy just costs one extra mint, never a wrong answer.
_token_cache: dict[int, tuple[str, float]] = {}


def installation_token(installation_id: int) -> str:
    """A fresh installation access token, reused until it is 5 minutes from expiry."""
    with _token_lock:
        cached = _token_cache.get(installation_id)
        if cached and cached[1] > time.time():
            return cached[0]
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{_API}/app/installations/{installation_id}/access_tokens",
            headers={"Authorization": f"Bearer {_app_jwt()}", "Accept": "application/vnd.github+json"},
        )
    if resp.status_code == 404:
        raise GitHubAppError("This installation no longer exists -- was it uninstalled?")
    _raise_for_status(resp, "minting an installation token")
    body = resp.json()
    token = body["token"]
    with _token_lock:
        _token_cache[installation_id] = (token, time.time() + 55 * 60)
    return token


def installation_account(installation_id: int) -> dict:
    """Whose account this installation lives under -- a user or an organization."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(
            f"{_API}/app/installations/{installation_id}",
            headers={"Authorization": f"Bearer {_app_jwt()}", "Accept": "application/vnd.github+json"},
        )
    _raise_for_status(resp, "reading the installation")
    account = resp.json().get("account") or {}
    return {"login": account.get("login", ""), "type": account.get("type", "")}


def list_installation_repos(installation_id: int) -> list[dict]:
    """Exactly the repos this installation was granted -- nothing more."""
    token = installation_token(installation_id)
    repos: list[dict] = []
    with httpx.Client(timeout=_TIMEOUT) as client:
        for page in range(1, 11):  # 1,000 repos is already well past what this UI lists
            resp = client.get(
                f"{_API}/installation/repositories",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                params={"per_page": 100, "page": page},
            )
            _raise_for_status(resp, "listing installation repositories")
            batch = resp.json().get("repositories", [])
            repos.extend(batch)
            if len(batch) < 100:
                break
    return repos


def list_public_repos(username: str) -> list[dict]:
    """The unauthenticated fallback: this user's public repos, install or not."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(
            f"{_API}/users/{username}/repos",
            headers={"Accept": "application/vnd.github+json"},
            params={"per_page": 100, "type": "owner", "sort": "pushed"},
        )
    if resp.status_code == 404:
        return []
    _raise_for_status(resp, "listing public repositories")
    return resp.json()


# ── webhooks: installation / installation_repositories ──


def verify_webhook_signature(raw_body: bytes, signature_header: str | None) -> None:
    if not WEBHOOK_SECRET:
        raise GitHubAppError("GITHUB_WEBHOOK_SECRET is not set on this server.")
    if not signature_header or not signature_header.startswith("sha256="):
        raise GitHubAppError("Missing or malformed X-Hub-Signature-256.")
    expected = hmac.new(WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    given = signature_header.split("=", 1)[1]
    if not hmac.compare_digest(expected, given):
        raise GitHubAppError("Webhook signature did not verify.")
