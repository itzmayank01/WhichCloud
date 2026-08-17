import type { ArchitectureView, LineItem } from "@/lib/api";

/**
 * Putting the catalog's prices onto the services somebody actually named.
 *
 * The engine prices seven categories, because that is what a price catalog can
 * be indexed by. A description names services: Aurora, Fargate, ElastiCache.
 * Neither is wrong and they do not line up on their own -- so a diagram of
 * what was described carried no figures, and a diagram carrying figures was a
 * fixed seven-box arrangement that ignored the description.
 *
 * This joins them by what a service *is*. Aurora is a database, so it carries
 * the database price. Fargate is compute. A service the catalog has no
 * category for stays unpriced, which is the honest result rather than a
 * missing one -- and where several named services share a category, the price
 * lands on one of them rather than being counted twice.
 */

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
  "dynamodb": "database",
  "aurora": "database",
  "neptune": "database",
  "timestream": "database",
  "keyspaces": "database",
  "fargate": "compute",
  "lambda": "compute",
  "beanstalk": "compute",
  "app runner": "compute",
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
  for (const key of KEYS) {
    if (name.includes(key)) return CATEGORY[key];
  }
  return null;
}

/** The catalog category a priced line item covers. */
function categoryOfItem(item: LineItem): string | null {
  const label = item.label.toLowerCase();
  if (label.startsWith("compute")) return "compute";
  if (label.startsWith("database")) return "database";
  if (label.startsWith("object storage")) return "storage";
  if (label.startsWith("cache")) return "cache";
  if (label.startsWith("monitoring")) return "monitoring";
  if (label.startsWith("load balancer")) return "loadbalancer";
  if (label.startsWith("egress")) return "network";
  return null;
}

/**
 * A copy of the drawing with catalog prices attached where they belong.
 *
 * Returns the view and how many services were priced, so the interface can
 * say "9 of 26 priced" rather than implying the total covers everything.
 */
export function withPrices(
  view: ArchitectureView,
  items: LineItem[],
): { view: ArchitectureView; priced: number; total: number } {
  const byCategory = new Map<string, LineItem>();
  for (const item of items) {
    const category = categoryOfItem(item);
    if (category && !byCategory.has(category)) byCategory.set(category, item);
  }

  /* One price per category, on the first service that claims it. Two
     databases in a description do not cost twice what the catalog quoted for
     one -- the quote was for the tier, not per box. */
  const spent = new Set<string>();
  let priced = 0;
  let total = 0;

  const nodes = view.nodes.map((node) => {
    const category = categoryOf(node.label);
    if (!category || spent.has(category)) return node;

    const item = byCategory.get(category);
    if (!item) return node;

    spent.add(category);
    priced += 1;
    total += item.monthly_usd;
    return {
      ...node,
      priced: true,
      monthly_usd: item.monthly_usd,
      sku: item.sku,
    };
  });

  return {
    view: { ...view, nodes, counts: { ...view.counts, priced } },
    priced,
    total,
  };
}
