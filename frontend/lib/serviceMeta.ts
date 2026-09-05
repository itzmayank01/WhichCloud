/**
 * Per-kind presentation metadata: which official AWS mark stands for a
 * topology kind, its one-line role, and its plane accent. Kept apart from the
 * renderer so the same table drives the node, the legend and the harness.
 */

/** kind → a label `iconFor` resolves to the official AWS PNG. */
export const KIND_ICON_LABEL: Record<string, string> = {
  cdn: "cloudfront",
  // Plain data transfer, NOT a CDN. These shared one kind, so a design
  // with an edge cache and one without drew the same CloudFront box.
  network: "vpc",
  waf: "waf",
  apigateway: "api gateway",
  loadbalancer: "elastic load balanc",
  compute: "ec2",
  compute_fargate: "fargate",
  lambda: "lambda",
  cache: "elasticache",
  database: "rds",
  database_replica: "rds",
  dynamodb: "dynamodb",
  timestream: "timestream",
  storage: "simple storage",
  search: "opensearch",
  warehouse: "redshift",
  streaming: "kinesis",
  kafka: "kinesis",
  firehose: "firehose",
  iot: "iot core",
  athena: "athena",
  glue: "glue",
  rekognition: "rekognition",
  comprehend: "comprehend",
  nat: "nat gateway",
  // control plane
  kms: "key management",
  secrets: "secrets manager",
  tls: "certificate manager",
  auth: "cognito",
  dns: "route 53",
  backup: "backup",
  // account plane
  audit: "cloudtrail",
  threat: "guardduty",
  posture: "securityhub",
  flowlogs: "vpc",
  monitoring: "cloudwatch",
  tracing: "x-ray",
};

/** kind → the one-line role shown under the service name. */
export const KIND_ROLE: Record<string, string> = {
  client: "End users",
  cdn: "CDN / edge delivery",
  network: "Data transfer out",
  waf: "Web application firewall",
  apigateway: "Managed API front door",
  loadbalancer: "Distributes traffic",
  compute: "Application servers",
  compute_fargate: "Serverless containers",
  lambda: "Functions on demand",
  cache: "In-memory cache",
  database: "Relational database",
  database_replica: "Read replica",
  dynamodb: "Key-value store",
  timestream: "Time-series store",
  storage: "Object storage",
  search: "Search cluster",
  warehouse: "Analytics warehouse",
  streaming: "Event stream",
  kafka: "Managed Kafka",
  firehose: "Stream delivery",
  iot: "Device ingest",
  athena: "Query the data lake",
  glue: "Managed ETL / catalog",
  rekognition: "Image recognition",
  comprehend: "Text analysis",
  nat: "Outbound gateway",
  kms: "Encryption keys",
  secrets: "Secret storage",
  tls: "TLS certificate",
  auth: "User sign-in",
  dns: "DNS resolution",
  backup: "Backups",
  audit: "API audit log",
  threat: "Threat detection",
  posture: "Security posture",
  flowlogs: "Network flow logs",
  monitoring: "Metrics & alarms",
  tracing: "Distributed tracing",
};

export function roleFor(kind: string): string {
  return KIND_ROLE[kind] ?? kind;
}
