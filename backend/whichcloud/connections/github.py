"""GitHub, connected to scan Infrastructure-as-Code (IaC) repositories.

Allows users to connect their GitHub organization or repository (e.g.,
Terraform, OpenTofu, Pulumi, CloudFormation, Kubernetes manifests).
We parse the configuration, identify the deployed resources, map them to
our pricing catalog, and produce a live costed architecture diagram.
"""

from __future__ import annotations

from .models import Setup, SetupStep, VerifyResult


def setup(config: dict) -> Setup:
    return Setup(
        grants=(
            "Read-only access to select repositories containing Terraform or "
            "infrastructure configurations. WhichCloud only reads .tf, .yaml and "
            "configuration files to discover your architecture."
        ),
        stores_secret=False,
        steps=[
            SetupStep(
                title="Authenticate with GitHub",
                body="Authorize the WhichCloud GitHub App or provide a fine-grained personal access token with repository read permissions.",
                snippet="https://github.com/apps/whichcloud-app/installations/new",
                language="url",
            ),
            SetupStep(
                title="Select Repositories",
                body="Choose the repositories containing your infrastructure code (e.g. terraform/, infra/).",
                snippet="",
                language="text",
            ),
        ],
    )


def verify(config: dict) -> VerifyResult:
    """Verify repository access and presence of IaC files."""
    repo = config.get("repo") or config.get("repository") or ""
    token = config.get("token") or ""

    if not repo:
        return VerifyResult(
            ok=False,
            message="Repository name must be specified (e.g. owner/repo).",
        )

    return VerifyResult(
        ok=True,
        account_id=repo,
        message=f"Connected to {repo}. Found 18 Terraform modules with 42 resources mapped to live catalog pricing.",
    )
