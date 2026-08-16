/**
 * A service's own logo, found from the name a description used.
 *
 * The names arriving here are whatever someone wrote: "Aurora PostgreSQL
 * Global Database", "Amazon MSK", "SQS/SNS". So this matches on keywords
 * contained in the name rather than expecting an exact identifier, and the
 * keys are tried longest first -- otherwise "API Gateway" matches "api" and
 * gets the wrong mark, and "OpenSearch" loses to "search".
 *
 * Every entry below was checked against the icon set rather than guessed. The
 * `logos` collection carries 62 AWS marks; a name with no match returns null
 * and the caller falls back to a tier glyph, which is honest -- an approximate
 * logo is worse than no logo, because it asserts a service that is not there.
 */

const AWS: Record<string, string> = {
  "api gateway": "aws-api-gateway",
  "secrets manager": "aws-secrets-manager",
  "certificate manager": "aws-certificate-manager",
  "systems manager": "aws-systems-manager",
  "step functions": "aws-step-functions",
  "lake formation": "aws-lake-formation",
  "elastic beanstalk": "aws-elastic-beanstalk",
  "load balancer": "aws-elb",
  "elasticache": "aws-elasticache",
  "cloudformation": "aws-cloudformation",
  "documentdb": "aws-documentdb",
  "cloudfront": "aws-cloudfront",
  "cloudwatch": "aws-cloudwatch",
  "cloudtrail": "aws-cloudtrail",
  "eventbridge": "aws-eventbridge",
  "opensearch": "aws-open-search",
  "open search": "aws-open-search",
  "codepipeline": "aws-codepipeline",
  "quicksight": "aws-quicksight",
  "cloudsearch": "aws-cloudsearch",
  "app mesh": "aws-app-mesh",
  "timestream": "aws-timestream",
  "codecommit": "aws-codecommit",
  "codedeploy": "aws-codedeploy",
  "keyspaces": "aws-keyspaces",
  "lightsail": "aws-lightsail",
  "route 53": "aws-route53",
  "route53": "aws-route53",
  "dynamodb": "aws-dynamodb",
  "codebuild": "aws-codebuild",
  "codestar": "aws-codestar",
  "kubernetes": "aws-eks",
  "opsworks": "aws-opsworks",
  "redshift": "aws-redshift",
  "cognito": "aws-cognito",
  "appsync": "aws-appsync",
  "appflow": "aws-appflow",
  "amplify": "aws-amplify",
  "neptune": "aws-neptune",
  "glacier": "aws-glacier",
  "kinesis": "aws-kinesis",
  "fargate": "aws-fargate",
  "aurora": "aws-aurora",
  "athena": "aws-athena",
  "backup": "aws-backup",
  "shield": "aws-shield",
  "config": "aws-config",
  "batch": "aws-batch",
  "redis": "aws-elasticache",
  "kafka": "aws-msk",
  "x-ray": "aws-xray",
  "xray": "aws-xray",
  "glue": "aws-glue",
  "lambda": "aws-lambda",
  "waf": "aws-waf",
  "iam": "aws-iam",
  "kms": "aws-kms",
  "rds": "aws-rds",
  "sqs": "aws-sqs",
  "sns": "aws-sns",
  "ses": "aws-ses",
  "eks": "aws-eks",
  "ecs": "aws-ecs",
  "ec2": "aws-ec2",
  "msk": "aws-msk",
  "elb": "aws-elb",
  "vpc": "aws-vpc",
  "s3": "aws-s3",
  "mq": "aws-mq",
};

/* Longest first, so a specific name is never beaten by a substring of it. */
const KEYS = Object.keys(AWS).sort((a, b) => b.length - a.length);

/** The Iconify name for this service, or null if there is no honest match. */
export function iconFor(label: string): string | null {
  const name = label.toLowerCase().replace(/[^a-z0-9 /-]/g, " ");
  for (const key of KEYS) {
    if (name.includes(key)) return `logos:${AWS[key]}`;
  }
  return null;
}
