#!/usr/bin/env python3
"""Vendor the official AWS architecture icons the diagram can use.

The reference architectures AWS publishes are drawn with their own icon set --
the orange Lambda square, the green S3 bucket -- and a diagram using
approximations of those marks reads as an imitation of one. Iconify's `logos`
collection carries 62 AWS icons; this set has 868, and it is the artwork the
references themselves use.

Taken from awslabs/aws-icons-for-plantuml, which is AWS's own repository. Its
`source/official` directory is gitignored -- the SVGs are fetched from AWS at
build time -- so `dist` PNGs are what is actually distributed.

Vendored rather than hotlinked. A diagram must render with no network, and a
raw.githubusercontent URL in a page is a dependency on someone else's uptime
for something that changes about twice a year.

    python3 scripts/fetch_aws_icons.py
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

TREE = (
    "https://api.github.com/repos/awslabs/aws-icons-for-plantuml/"
    "git/trees/main?recursive=1"
)
RAW = "https://raw.githubusercontent.com/awslabs/aws-icons-for-plantuml/main/"
OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "icons" / "aws"

#: Services that turn up in real architecture descriptions. Downloading all
#: 868 would be 40MB in the repository for marks nobody names; this is the set
#: worth carrying, and anything missing falls back to a category glyph rather
#: than to nothing.
WANTED = {
    "Route53", "CloudFront", "WAF", "Shield", "GlobalAccelerator", "APIGateway",
    "ElasticLoadBalancing", "VPC", "DirectConnect", "TransitGateway", "NATGateway",
    "EC2", "Lambda", "Fargate", "Batch", "AppRunner", "Lightsail",
    # AWS files these under their full product names, not the acronyms
    # everybody actually types.
    "ElasticKubernetesService", "ElasticContainerService",
    "ElasticBeanstalk", "AutoScaling",
    "RDS", "Aurora", "DynamoDB", "ElastiCache", "DocumentDB", "Neptune",
    "Redshift", "Timestream", "MemoryDB", "Keyspaces",
    "SimpleStorageService", "EFS", "FSx", "Backup", "StorageGateway",
    "SimpleQueueService", "SimpleNotificationService", "EventBridge",
    "StepFunctions", "AppSync", "MQ", "ManagedStreamingforApacheKafka",
    "Kinesis", "Glue", "Athena", "EMR", "LakeFormation",
    "OpenSearchService", "DataFirehose", "VPCNATGateway",
    "SageMakerAI", "Bedrock", "Comprehend", "Rekognition", "Textract", "Polly",
    "IdentityandAccessManagement", "KeyManagementService", "SecretsManager",
    "Cognito", "CertificateManager", "GuardDuty", "SecurityHub", "Inspector",
    "Macie", "CloudHSM", "NetworkFirewall",
    "CloudWatch", "CloudTrail", "XRay", "Config", "SystemsManager",
    "CloudFormation", "Organizations", "ControlTower", "TrustedAdvisor",
    "CodePipeline", "CodeBuild", "CodeDeploy", "CodeCommit", "CodeArtifact",
    "ElasticContainerRegistry", "Amplify", "AppConfig", "Cloud9",
}


def key(filename: str) -> str:
    return re.sub(r"[^a-z0-9]", "", filename.removesuffix(".png").lower())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = {key(w) for w in WANTED}

    with urllib.request.urlopen(TREE, timeout=90) as response:
        tree = json.load(response)

    paths = [
        entry["path"]
        for entry in tree.get("tree", [])
        if entry["path"].startswith("dist/") and entry["path"].endswith(".png")
    ]

    taken: dict[str, str] = {}
    for path in paths:
        name = path.rsplit("/", 1)[-1]
        k = key(name)
        # First match wins: categories are walked in order and the plain name
        # ("Lambda.png") sorts before its variants ("LambdaFunction.png").
        if k in wanted and k not in taken:
            taken[k] = path

    written = 0
    for k, path in sorted(taken.items()):
        target = OUT / f"{k}.png"
        if target.exists():
            continue
        with urllib.request.urlopen(RAW + urllib.parse.quote(path), timeout=90) as r:
            target.write_bytes(r.read())
        written += 1

    missing = sorted(wanted - set(taken))
    print(f"  vendored {len(taken)} icons ({written} newly downloaded)")
    print(f"  into {OUT}")
    if missing:
        print(f"  no icon found for {len(missing)}: {', '.join(missing[:8])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
