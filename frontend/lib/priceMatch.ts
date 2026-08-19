import type { ArchitectureView, ArchNode } from "@/lib/api";

/**
 * Refining the priced diagram's generic labels with what was actually named.
 *
 * The backend's own topology (`option.drawn`) is the ground truth: every box
 * on it is one of the line items in the bill, because it was built from the
 * same priced architecture. It just uses the catalog's generic name for the
 * category -- "Amazon RDS", "Amazon ECS" -- because that is all a price
 * catalog knows. A description often names something more specific for the
 * same box: "Aurora PostgreSQL Global Database" is still an RDS-family
 * instance-hour, just a more exact name for it.
 *
 * This only relabels. It never adds a box, and it never lets a named service
 * pull a price onto itself -- both of those are how a $121.91 RDS number
 * used to end up sitting under "DynamoDB", a service billed per-request that
 * was never actually priced. Grounding in the backend's boxes and only
 * borrowing better words for them removes that failure mode by construction:
 * there is nothing left to attach a price to except a box the backend
 * already priced.
 */

/**
 * Serverless and request-billed services the catalog has no meter for.
 *
 * The catalog only ever prices EC2 instance-hours, RDS instance-hours, S3,
 * ALB, ElastiCache node-hours, CloudWatch and egress -- see
 * backend/whichcloud/pricing/aws.py. A box labelled "Amazon RDS" is always an
 * RDS-family name, never a DynamoDB or Aurora Serverless one, so those never
 * enter as a relabelling candidate even though "Aurora" would otherwise
 * match below. Checked first, so it wins regardless of match length.
 */
const UNPRICEABLE = [
  "serverless",
  "dynamodb",
  "fargate",
  "lambda",
  "app runner",
  "keyspaces",
  "timestream",
  "api gateway",
  "step functions",
  "sqs",
  "sns",
  "eventbridge",
];

/** keyword → the catalog category it belongs to. Longest match wins. */
const CATEGORY: Record<string, string> = {
  "elastic load balanc": "loadbalancer",
  "load balancer": "loadbalancer",
  "application load": "loadbalancer",
  "elasticache": "cache",
  "memorydb": "cache",
  "cloudfront": "network",
  "global accelerator": "network",
  "cloudwatch": "monitoring",
  "opensearch": "database",
  "documentdb": "database",
  "aurora": "database",
  "neptune": "database",
  "beanstalk": "compute",
  "redis": "cache",
  "rds": "database",
  "eks": "compute",
  "ecs": "compute",
  "ec2": "compute",
  "efs": "storage",
  "fsx": "storage",
  "s3": "storage",
  "alb": "loadbalancer",
  "elb": "loadbalancer",
};

const KEYS = Object.keys(CATEGORY).sort((a, b) => b.length - a.length);

/** Which catalog category this service belongs to, if any. */
export function categoryOf(label: string): string | null {
  const name = label.toLowerCase();
  if (UNPRICEABLE.some((key) => name.includes(key))) return null;
  for (const key of KEYS) {
    if (name.includes(key)) return CATEGORY[key];
  }
  return null;
}

/**
 * The priced view with generic labels swapped for a more specific name from
 * the description, everywhere the two are the same catalog category.
 *
 * `described` is optional: when the architecture reader hit its quota or
 * found nothing worth drawing, the priced view is returned exactly as the
 * backend built it -- generic AWS category names, still fully accurate.
 */
export function withLabels(
  view: ArchitectureView,
  described: ArchitectureView | null,
): ArchitectureView {
  if (!described) return view;

  const byCategory = new Map<string, ArchNode>();
  for (const node of described.nodes) {
    const category = categoryOf(node.label);
    if (category && !byCategory.has(category)) byCategory.set(category, node);
  }

  const nodes = view.nodes.map((node) => {
    const category = categoryOf(node.label);
    const match = category ? byCategory.get(category) : undefined;
    if (!match || match.label === node.label) return node;
    return { ...node, label: match.label, purpose: match.purpose || node.purpose };
  });

  return { ...view, nodes };
}
