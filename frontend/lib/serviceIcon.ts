/**
 * A service's own mark, found from the name a description used.
 *
 * These are AWS's official architecture icons, vendored under
 * public/icons/aws by scripts/fetch_aws_icons.py. The reference architectures
 * AWS publishes are drawn with exactly this artwork -- the orange Lambda
 * square, the green S3 bucket -- and a diagram built from approximations
 * reads as an imitation of one rather than as the thing itself. Iconify's
 * `logos` set carries 62 AWS marks and left four of twenty three services in
 * a real description with no icon at all; this carries 85 of the 868 AWS
 * publishes, chosen as the ones that turn up in descriptions.
 *
 * The names arriving here are whatever somebody wrote -- "Aurora PostgreSQL
 * Global Database", "Amazon MSK", "SQS/SNS" -- so matching is on keywords
 * contained in the name, tried longest first. Otherwise "API Gateway" matches
 * "api" and "OpenSearch" loses to "search".
 *
 * A name with no match returns null and the caller falls back to a glyph for
 * the tier, which is honest: an approximate logo asserts a service that is
 * not in the architecture.
 */

/** keyword → the vendored file's basename */
const AWS: Record<string, string> = {
  "elastic kubernetes": "elastickubernetesservice",
  "elastic container registry": "elasticcontainerregistry",
  "elastic container": "elasticcontainerservice",
  "elastic load balanc": "elasticloadbalancing",
  "elastic beanstalk": "elasticbeanstalk",
  "certificate manager": "certificatemanager",
  "identity and access": "identityandaccessmanagement",
  "key management": "keymanagementservice",
  "secrets manager": "secretsmanager",
  "systems manager": "systemsmanager",
  "storage gateway": "storagegateway",
  "step functions": "stepfunctions",
  "lake formation": "lakeformation",
  "network firewall": "networkfirewall",
  "transit gateway": "transitgateway",
  "direct connect": "directconnect",
  "global accelerator": "globalaccelerator",
  "trusted advisor": "trustedadvisor",
  "control tower": "controltower",
  "nat gateway": "vpcnatgateway",
  "api gateway": "apigateway",
  "auto scaling": "autoscaling",
  "cloudformation": "cloudformation",
  "elasticache": "elasticache",
  "opensearch": "opensearchservice",
  "open search": "opensearchservice",
  "codepipeline": "codepipeline",
  "codeartifact": "codeartifact",
  "cloudfront": "cloudfront",
  "cloudwatch": "cloudwatch",
  "cloudtrail": "cloudtrail",
  "documentdb": "documentdb",
  "eventbridge": "eventbridge",
  "codecommit": "codecommit",
  "codedeploy": "codedeploy",
  "sagemaker": "sagemakerai",
  "rekognition": "rekognition",
  "comprehend": "comprehend",
  "guardduty": "guardduty",
  "securityhub": "securityhub",
  "security hub": "securityhub",
  "beanstalk": "elasticbeanstalk",
  "lightsail": "lightsail",
  "memorydb": "memorydb",
  "keyspaces": "keyspaces",
  "timestream": "timestream",
  "firehose": "datafirehose",
  "cloudhsm": "cloudhsm",
  "codebuild": "codebuild",
  "route 53": "route53",
  "route53": "route53",
  "dynamodb": "dynamodb",
  "redshift": "redshift",
  "inspector": "inspector",
  "amplify": "amplify",
  "appsync": "appsync",
  "aurora": "aurora",
  "athena": "athena",
  "bedrock": "bedrock",
  "backup": "backup",
  "cognito": "cognito",
  "fargate": "fargate",
  "kinesis": "kinesis",
  "neptune": "neptune",
  "textract": "textract",
  "kafka": "managedstreamingforapachekafka",
  "lambda": "lambda",
  "config": "config",
  "batch": "batch",
  "macie": "macie",
  "polly": "polly",
  "redis": "elasticache",
  "shield": "shield",
  "x-ray": "xray",
  "xray": "xray",
  "glue": "glue",
  "msk": "managedstreamingforapachekafka",
  "sqs": "simplequeueservice",
  "sns": "simplenotificationservice",
  "eks": "elastickubernetesservice",
  "ecs": "elasticcontainerservice",
  "ecr": "elasticcontainerregistry",
  "efs": "efs",
  "elb": "elasticloadbalancing",
  "emr": "emr",
  "ec2": "ec2",
  "iam": "identityandaccessmanagement",
  "kms": "keymanagementservice",
  "rds": "rds",
  "vpc": "vpc",
  "waf": "waf",
  "fsx": "fsx",
  "s3": "simplestorageservice",
  "mq": "mq",
};

/* Longest first, so a specific name is never beaten by a substring of it. */
const KEYS = Object.keys(AWS).sort((a, b) => b.length - a.length);

/** Path to the official mark for this service, or null if there is none. */
export function iconFor(label: string): string | null {
  const name = label.toLowerCase().replace(/[^a-z0-9 /-]/g, " ");
  for (const key of KEYS) {
    if (name.includes(key)) return `/icons/aws/${AWS[key]}.png`;
  }
  return null;
}
