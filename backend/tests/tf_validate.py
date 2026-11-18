"""Run a real `terraform init -backend=false` + `terraform validate`.

`hcl2.load` only proves the grammar parses. It cannot tell you that
`blob_properties` is a real block on `azurerm_storage_account`, or that
`backup_retention_settings` nests where the Google provider expects it --
those are provider SCHEMA questions, and only Terraform itself answers them.
That gap is exactly where a generator bug survives review: the file looks
like Terraform, parses as Terraform, and then fails on the user's machine at
`terraform plan`.

The AWS export has had this since the start (test_terraform_export.py keeps
its own copy, written before there was a second caller). GCP and Azure got
dev/prod environments later, so this is factored out here rather than
copied a third time.

Skipped when the terraform binary is absent, which is why CI installs it --
see the `terraform-validate` job in .github/workflows/ci.yml.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

TERRAFORM = shutil.which("terraform")

needs_terraform = pytest.mark.skipif(
    TERRAFORM is None, reason="terraform CLI not installed"
)


def validate_project(tmp_path: Path, files: dict[str, str]) -> None:
    """Write `files` into `tmp_path` and assert Terraform accepts them.

    `-backend=false` keeps init from wanting real credentials or remote
    state; it still downloads the providers, which is the part that makes
    validate meaningful.
    """
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    init = subprocess.run(
        [TERRAFORM, "init", "-backend=false", "-input=false"],
        cwd=tmp_path, capture_output=True, text=True, timeout=300,
    )
    assert init.returncode == 0, f"terraform init failed:\n{init.stdout}\n{init.stderr}"

    validate = subprocess.run(
        [TERRAFORM, "validate"],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
    )
    assert validate.returncode == 0, (
        f"terraform validate failed:\n{validate.stdout}\n{validate.stderr}"
    )
