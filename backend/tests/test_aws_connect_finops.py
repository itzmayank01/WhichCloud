"""End-to-end tests for multi-user AWS account connection & FinOps Live isolation."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from fastapi.testclient import TestClient

from whichcloud.api import _OWNER_EXTERNAL_IDS, app
from whichcloud.connections import aws as conn_aws
from whichcloud.connections import aws_live


client = TestClient(app)


def _mock_owner_map(token_map: dict[str, str]):
    def _fake_verify(token: str) -> dict:
        if token not in token_map:
            from whichcloud.auth import AuthError
            raise AuthError("Invalid token")
        return {"sub": token_map[token]}

    return _fake_verify


def test_unauthenticated_setup_and_live_rejected_even_if_finops_owners_env_set(monkeypatch):
    monkeypatch.setenv("WHICHCLOUD_FINOPS_OWNERS", "user_operator_123")
    r1 = client.post("/api/connections/setup", json={"provider": "aws", "config": {}})
    assert r1.status_code == 401

    r2 = client.get("/api/finops/live?provider=aws")
    assert r2.status_code == 401


def test_demo_mode_works_without_auth_and_never_touches_real_credentials():
    r = client.get("/api/finops/live?provider=aws&account_id=demo")
    assert r.status_code == 200
    body = r.json()
    assert body["account"]["id"] == "demo"
    assert "Demo" in body["account"]["name"]
    assert body["summary"]["total_monthly_usd"] > 0
    assert len(body["nodes"]) >= 3

    r_res = client.get("/api/finops/resources?provider=aws&account_id=demo")
    assert r_res.status_code == 200
    assert r_res.json()["account_id"] == "demo"

    r_iss = client.get("/api/finops/issues?provider=aws&account_id=demo")
    assert r_iss.status_code == 200
    assert len(r_iss.json()["issues"]) >= 1


def test_access_denied_explanation_includes_actionable_diagnostics(monkeypatch):
    monkeypatch.setattr(conn_aws, "our_account_id", lambda: "616551057703")
    exc = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "User is not authorized to perform: sts:AssumeRole"}},
        "AssumeRole",
    )
    msg = conn_aws._explain(
        exc,
        role_arn="arn:aws:iam::201210176165:role/WhichCloudCostRole",
        external_id="whichcloud-test123",
    )
    assert "616551057703" in msg
    assert "arn:aws:iam::201210176165:role/WhichCloudCostRole" in msg
    assert "get-caller-identity" in msg


def test_multi_user_connect_verify_me_and_strict_finops_isolation(monkeypatch):
    _OWNER_EXTERNAL_IDS.clear()
    aws_live.invalidate_cache()

    fake_db: dict[tuple[str, str], dict] = {}

    def fake_save_connection(owner, provider, display_name, account_id, config, status="active", dsn=None):
        row = {
            "id": f"id_{owner}_{provider}",
            "owner": owner,
            "provider": provider,
            "display_name": display_name,
            "account_id": account_id,
            "config": dict(config),
            "status": status,
            "last_error": "",
        }
        fake_db[(owner, provider)] = row
        return row

    def fake_get_connection(owner, provider, dsn=None):
        return fake_db.get((owner, provider))

    def fake_list_connections(owner, dsn=None):
        return [v for (o, _), v in fake_db.items() if o == owner]

    monkeypatch.setattr("whichcloud.auth.verify", _mock_owner_map({
        "tok_a": "user_alice",
        "tok_b": "user_bob",
        "tok_c": "user_carol",
    }))
    monkeypatch.setattr("whichcloud.pricing.store.save_connection", fake_save_connection)
    monkeypatch.setattr("whichcloud.pricing.store.get_connection", fake_get_connection)
    monkeypatch.setattr("whichcloud.pricing.store.list_connections", fake_list_connections)
    monkeypatch.setattr(conn_aws, "our_account_id", lambda: "616551057703")

    # 1. Alice and Bob get distinct stable external IDs
    s_a1 = client.post("/api/connections/setup", json={"provider": "aws", "config": {}}, headers={"Authorization": "Bearer tok_a"})
    s_a2 = client.post("/api/connections/setup", json={"provider": "aws", "config": {}}, headers={"Authorization": "Bearer tok_a"})
    s_b = client.post("/api/connections/setup", json={"provider": "aws", "config": {}}, headers={"Authorization": "Bearer tok_b"})
    assert s_a1.status_code == 200 and s_a2.status_code == 200 and s_b.status_code == 200
    ext_a = s_a1.json()["external_id"]
    ext_b = s_b.json()["external_id"]
    assert ext_a == s_a2.json()["external_id"]
    assert ext_a != ext_b

    # 2. Mock STS AssumeRole for Alice (111111111111) and Bob (222222222222)
    def fake_session(cfg):
        arn = conn_aws._normalize_role_arn(cfg["role_arn"])
        acct = arn.split(":")[4]
        sess = MagicMock()
        sts_client = MagicMock()
        sts_client.get_caller_identity.return_value = {"Account": acct, "Arn": arn}
        frozen = MagicMock(access_key=f"AKIA{acct}", secret_key="sec", token="tok")
        sess.get_credentials.return_value.get_frozen_credentials.return_value = frozen

        ce_client = MagicMock()
        spend = "123.45" if acct == "111111111111" else "456.78"
        svc = "Amazon EC2" if acct == "111111111111" else "Amazon RDS"
        ce_client.get_cost_and_usage.return_value = {
            "ResultsByTime": [
                {
                    "Groups": [{"Keys": [svc], "Metrics": {"UnblendedCost": {"Amount": spend}}}],
                    "Total": {"UnblendedCost": {"Amount": spend}},
                }
            ]
        }

        def _client(service_name, **kwargs):
            if service_name == "sts":
                return sts_client
            if service_name == "ce":
                return ce_client
            # Simulate a Cost-Explorer-only IAM role where EC2/S3/RDS describe calls return AccessDenied
            denied = MagicMock()
            denied.describe_instances.side_effect = RuntimeError("AccessDenied")
            denied.describe_volumes.side_effect = RuntimeError("AccessDenied")
            denied.describe_addresses.side_effect = RuntimeError("AccessDenied")
            denied.describe_vpcs.side_effect = RuntimeError("AccessDenied")
            denied.describe_db_instances.side_effect = RuntimeError("AccessDenied")
            denied.list_buckets.side_effect = RuntimeError("AccessDenied")
            denied.list_clusters.side_effect = RuntimeError("AccessDenied")
            denied.list_functions.side_effect = RuntimeError("AccessDenied")
            denied.list_tables.side_effect = RuntimeError("AccessDenied")
            return denied

        sess.client.side_effect = _client
        return sess

    monkeypatch.setattr(conn_aws, "_session", fake_session)

    # Verify Alice with bare 12-digit account ID and omitted external_id (auto-filled from stored)
    v_a = client.post(
        "/api/connections/verify",
        json={"provider": "aws", "credentials": {"role_arn": "111111111111", "region": "ap-south-1"}},
        headers={"Authorization": "Bearer tok_a"},
    )
    assert v_a.status_code == 200 and v_a.json()["ok"] is True
    assert v_a.json()["account_id"] == "111111111111"

    # Verify Bob
    v_b = client.post(
        "/api/connections/verify",
        json={"provider": "aws", "credentials": {"role_arn": "arn:aws:iam::222222222222:role/WhichCloudCostRole", "external_id": ext_b, "region": "us-east-1"}},
        headers={"Authorization": "Bearer tok_b"},
    )
    assert v_b.status_code == 200 and v_b.json()["ok"] is True

    # GET /api/connections/me returns each user's own account only
    me_a = client.get("/api/connections/me", headers={"Authorization": "Bearer tok_a"})
    assert me_a.status_code == 200
    assert me_a.json()["connections"][0]["account_id"] == "111111111111"

    me_c = client.get("/api/connections/me", headers={"Authorization": "Bearer tok_c"})
    assert me_c.status_code == 200
    assert me_c.json()["connections"] == []

    # 3. FinOps Live strictly isolates Alice vs Bob (no shared global cache, no hardcoded awsmayank!)
    def fake_boto3_session():
        creds = aws_live._CREDENTIALS.get()
        return fake_session({"role_arn": creds["AWS_ROLE_ARN"], "external_id": "x"})

    with patch.object(aws_live, "_boto3_session", side_effect=fake_boto3_session):
        live_a = client.get("/api/finops/live?provider=aws", headers={"Authorization": "Bearer tok_a"})
        live_b = client.get("/api/finops/live?provider=aws", headers={"Authorization": "Bearer tok_b"})
        live_c = client.get("/api/finops/live?provider=aws", headers={"Authorization": "Bearer tok_c"})

    assert live_a.status_code == 200
    assert live_b.status_code == 200
    assert live_c.status_code == 409  # Carol has no AWS account connected

    ja = live_a.json()
    jb = live_b.json()
    assert ja["account"]["id"] == "111111111111"
    assert jb["account"]["id"] == "222222222222"
    assert "awsmayank" not in ja["account"]["name"].lower()
    assert ja["summary"]["total_monthly_usd"] == 123.45
    assert jb["summary"]["total_monthly_usd"] == 456.78
    # Cost-Explorer-only role still populates real Cost Explorer topology nodes!
    assert any("Amazon EC2" in n["label"] for n in ja["nodes"])
    assert any("Amazon RDS" in n["label"] for n in jb["nodes"])

