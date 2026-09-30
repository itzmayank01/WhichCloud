"""GitHub App sign-in: state signing, webhook verification, and the routes.

No test here makes a real call to GitHub -- `github_app`'s network functions
(`exchange_code_for_user`, `installation_account`, `list_installation_repos`,
`list_public_repos`) are monkeypatched at the route level, the same pattern
`test_connections_github.py` uses for the unrelated PAT-based scanner. What
IS tested for real: state HMAC signing/verification (tamper, expiry,
malformed), webhook HMAC verification, and that every route wires its
inputs and outputs the way the picker page expects.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from whichcloud import github_app
from whichcloud.api import app
from whichcloud.auth import current_owner


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def _as(owner: str):
    app.dependency_overrides[current_owner] = lambda: owner


def _anonymous():
    app.dependency_overrides.clear()


@pytest.fixture()
def configured(monkeypatch):
    """A GitHub App that looks fully configured, without touching real env."""
    monkeypatch.setattr(github_app, "APP_ID", "123456")
    monkeypatch.setattr(github_app, "APP_SLUG", "whichcloud-test")
    monkeypatch.setattr(github_app, "CLIENT_ID", "Iv1.testclientid")
    monkeypatch.setattr(github_app, "CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(github_app, "PRIVATE_KEY", "test-private-key")
    monkeypatch.setattr(github_app, "WEBHOOK_SECRET", "test-webhook-secret")
    return github_app


# ── state: sign / verify ──────────────────────────────────────────────────


def test_state_round_trips_the_owner(configured):
    state = github_app.sign_state("user_abc123")
    assert github_app.verify_state(state) == "user_abc123"


def test_state_rejects_a_tampered_signature(configured):
    state = github_app.sign_state("user_abc123")
    payload, sig = state.rsplit(".", 1)
    forged = f"{payload}.{'0' * len(sig)}"
    with pytest.raises(github_app.GitHubAppError, match="verification"):
        github_app.verify_state(forged)


def test_state_rejects_a_different_owner_spliced_in(configured):
    """Changing the owner without re-signing must fail, not silently verify as the new owner."""
    state = github_app.sign_state("user_abc123")
    ts, nonce, _owner, sig = state.split(".", 3)
    forged = f"{ts}.{nonce}.user_attacker.{sig}"
    with pytest.raises(github_app.GitHubAppError, match="verification"):
        github_app.verify_state(forged)


def test_state_rejects_malformed_input(configured):
    with pytest.raises(github_app.GitHubAppError, match="[Mm]alformed"):
        github_app.verify_state("not-a-valid-state")


def test_state_rejects_expired(configured, monkeypatch):
    state = github_app.sign_state("user_abc123")
    future = time.time() + github_app.STATE_TTL_S + 1
    monkeypatch.setattr(time, "time", lambda: future)
    with pytest.raises(github_app.GitHubAppError, match="expired"):
        github_app.verify_state(state)


def test_install_url_requires_configuration(monkeypatch):
    monkeypatch.setattr(github_app, "APP_ID", "")
    monkeypatch.setattr(github_app, "APP_SLUG", "")
    monkeypatch.setattr(github_app, "CLIENT_ID", "")
    monkeypatch.setattr(github_app, "CLIENT_SECRET", "")
    monkeypatch.setattr(github_app, "PRIVATE_KEY", "")
    with pytest.raises(github_app.GitHubAppError, match="not configured"):
        github_app.install_url("user_abc123")


def test_install_url_embeds_a_verifiable_state(configured):
    url = github_app.install_url("user_abc123")
    assert url.startswith("https://github.com/apps/whichcloud-test/installations/new?state=")
    state = url.split("state=", 1)[1]
    from urllib.parse import unquote

    assert github_app.verify_state(unquote(state)) == "user_abc123"


# ── webhook signature ──────────────────────────────────────────────────────


def test_webhook_signature_accepts_a_correctly_signed_body(configured):
    body = b'{"action": "deleted"}'
    sig = "sha256=" + hmac.new(b"test-webhook-secret", body, hashlib.sha256).hexdigest()
    github_app.verify_webhook_signature(body, sig)  # does not raise


def test_webhook_signature_rejects_wrong_secret(configured):
    body = b'{"action": "deleted"}'
    sig = "sha256=" + hmac.new(b"wrong-secret", body, hashlib.sha256).hexdigest()
    with pytest.raises(github_app.GitHubAppError, match="did not verify"):
        github_app.verify_webhook_signature(body, sig)


def test_webhook_signature_rejects_missing_header(configured):
    with pytest.raises(github_app.GitHubAppError, match="Missing"):
        github_app.verify_webhook_signature(b"{}", None)


def test_webhook_signature_requires_secret_configured(monkeypatch):
    monkeypatch.setattr(github_app, "WEBHOOK_SECRET", "")
    with pytest.raises(github_app.GitHubAppError, match="not set"):
        github_app.verify_webhook_signature(b"{}", "sha256=whatever")


# ── routes ──────────────────────────────────────────────────────────────


def test_connect_route_requires_auth(client):
    _anonymous()
    resp = client.get("/api/github/connect")
    assert resp.status_code == 401


def test_connect_route_returns_an_authorize_url(client, configured):
    _as("user_abc123")
    resp = client.get("/api/github/connect")
    assert resp.status_code == 200
    assert resp.json()["authorize_url"].startswith("https://github.com/apps/whichcloud-test/")
    _anonymous()


def test_connect_route_503s_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(github_app, "APP_ID", "")
    _as("user_abc123")
    resp = client.get("/api/github/connect")
    assert resp.status_code == 503
    _anonymous()


def test_callback_without_state_redirects_with_error(client):
    resp = client.get("/api/github/oauth/callback", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "error=" in resp.headers["location"]


def test_callback_with_bad_state_redirects_with_error(client, configured):
    resp = client.get(
        "/api/github/oauth/callback",
        params={"state": "garbage", "code": "x", "installation_id": 1, "setup_action": "install"},
        follow_redirects=False,
    )
    assert "error=" in resp.headers["location"]


def test_callback_success_saves_the_installation_and_redirects_connected(
    client, configured, monkeypatch
):
    saved = {}

    def fake_exchange(code):
        assert code == "the-code"
        return {"login": "octocat"}

    def fake_account(installation_id):
        assert installation_id == 999
        return {"login": "octocat", "type": "User"}

    def fake_save(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr(github_app, "exchange_code_for_user", fake_exchange)
    monkeypatch.setattr(github_app, "installation_account", fake_account)
    monkeypatch.setattr("whichcloud.api.store.save_github_installation", fake_save)

    state = github_app.sign_state("user_abc123")
    resp = client.get(
        "/api/github/oauth/callback",
        params={
            "state": state,
            "code": "the-code",
            "installation_id": 999,
            "setup_action": "install",
        },
        follow_redirects=False,
    )
    assert "connected=1" in resp.headers["location"]
    assert saved == {
        "owner": "user_abc123",
        "installation_id": 999,
        "account_login": "octocat",
        "account_type": "User",
        "github_login": "octocat",
    }


def test_callback_incomplete_setup_redirects_with_error(client, configured):
    state = github_app.sign_state("user_abc123")
    resp = client.get(
        "/api/github/oauth/callback",
        params={"state": state},  # no code / installation_id
        follow_redirects=False,
    )
    assert "error=" in resp.headers["location"]


def test_repos_route_merges_installed_and_public_repos(client, monkeypatch):
    monkeypatch.setattr(
        "whichcloud.api.store.list_github_installations",
        lambda owner: [
            {
                "installation_id": 999,
                "account_login": "octocat",
                "account_type": "User",
                "github_login": "octocat",
            }
        ],
    )
    monkeypatch.setattr(
        github_app,
        "list_installation_repos",
        lambda installation_id: [
            {
                "full_name": "octocat/private-repo",
                "private": True,
                "language": "Python",
                "pushed_at": "2026-01-01T00:00:00Z",
                "html_url": "https://github.com/octocat/private-repo",
                "default_branch": "main",
            }
        ],
    )
    monkeypatch.setattr(
        github_app,
        "list_public_repos",
        lambda username: [
            {
                "full_name": "octocat/public-repo",
                "private": False,
                "language": "TypeScript",
                "pushed_at": "2025-01-01T00:00:00Z",
                "html_url": "https://github.com/octocat/public-repo",
                "default_branch": "main",
            }
        ],
    )
    _as("user_abc123")
    resp = client.get("/api/github/repos")
    assert resp.status_code == 200
    body = resp.json()
    assert body["installed"] is True
    assert body["github_login"] == "octocat"
    names = [r["full_name"] for r in body["repos"]]
    assert "octocat/private-repo" in names
    assert "octocat/public-repo" in names
    # newest pushed_at first
    assert names[0] == "octocat/private-repo"
    _anonymous()


def test_repos_route_with_no_installation_is_empty_not_an_error(client, monkeypatch):
    monkeypatch.setattr("whichcloud.api.store.list_github_installations", lambda owner: [])
    _as("user_abc123")
    resp = client.get("/api/github/repos")
    assert resp.status_code == 200
    assert resp.json() == {
        "installed": False,
        "github_login": "",
        "repos": [],
        "errors": [],
    }
    _anonymous()


def test_webhook_requires_a_valid_signature(client, configured):
    resp = client.post(
        "/api/github/webhook",
        content=b'{"action": "deleted"}',
        headers={"X-Hub-Signature-256": "sha256=deadbeef"},
    )
    assert resp.status_code == 401


def test_webhook_deletes_installation_on_installation_deleted(client, configured, monkeypatch):
    deleted = {}
    monkeypatch.setattr(
        "whichcloud.api.store.delete_github_installations_by_installation_id",
        lambda installation_id: deleted.setdefault("id", installation_id) or 1,
    )
    body = json.dumps({"action": "deleted", "installation": {"id": 999}}).encode()
    sig = "sha256=" + hmac.new(b"test-webhook-secret", body, hashlib.sha256).hexdigest()
    resp = client.post(
        "/api/github/webhook",
        content=body,
        headers={"X-Hub-Signature-256": sig, "X-GitHub-Event": "installation"},
    )
    assert resp.status_code == 200
    assert deleted == {"id": 999}


def test_webhook_ignores_unrelated_events(client, configured, monkeypatch):
    called = []
    monkeypatch.setattr(
        "whichcloud.api.store.delete_github_installations_by_installation_id",
        lambda installation_id: called.append(installation_id),
    )
    body = json.dumps({"action": "added", "installation": {"id": 999}}).encode()
    sig = "sha256=" + hmac.new(b"test-webhook-secret", body, hashlib.sha256).hexdigest()
    resp = client.post(
        "/api/github/webhook",
        content=body,
        headers={"X-Hub-Signature-256": sig, "X-GitHub-Event": "installation_repositories"},
    )
    assert resp.status_code == 200
    assert called == []
