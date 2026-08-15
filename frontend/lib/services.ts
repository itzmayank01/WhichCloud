/**
 * Provider service names for each architecture role.
 *
 * The engine reasons in neutral terms — compute, database, storage — because
 * that is what makes cross-cloud comparison possible at all. But an engineer
 * looking at a diagram wants to see "RDS", not "Database", so the neutral role
 * is translated back into each provider's vocabulary at the last possible
 * moment: here, in the interface.
 */

type Service = { name: string; short: string };

const SERVICES: Record<string, Record<string, Service>> = {
  aws: {
    client: { name: "Users", short: "Users" },
    network: { name: "Amazon CloudFront", short: "CloudFront" },
    loadbalancer: { name: "Elastic Load Balancing", short: "ALB" },
    compute: { name: "Amazon ECS on EC2", short: "ECS" },
    database: { name: "Amazon RDS for PostgreSQL", short: "RDS" },
    storage: { name: "Amazon S3", short: "S3" },
    cache: { name: "Amazon ElastiCache", short: "ElastiCache" },
    monitoring: { name: "Amazon CloudWatch", short: "CloudWatch" },
  },
  azure: {
    client: { name: "Users", short: "Users" },
    network: { name: "Azure Front Door", short: "Front Door" },
    loadbalancer: { name: "Azure Load Balancer", short: "Load Balancer" },
    compute: { name: "Azure Virtual Machines", short: "Virtual Machines" },
    database: { name: "Azure Database for PostgreSQL", short: "PostgreSQL" },
    storage: { name: "Azure Blob Storage", short: "Blob Storage" },
    cache: { name: "Azure Cache for Redis", short: "Cache for Redis" },
    monitoring: { name: "Azure Monitor", short: "Monitor" },
  },
  gcp: {
    client: { name: "Users", short: "Users" },
    network: { name: "Cloud CDN", short: "Cloud CDN" },
    loadbalancer: { name: "Cloud Load Balancing", short: "Load Balancing" },
    compute: { name: "Compute Engine", short: "Compute Engine" },
    database: { name: "Cloud SQL for PostgreSQL", short: "Cloud SQL" },
    storage: { name: "Cloud Storage", short: "Cloud Storage" },
    cache: { name: "Memorystore", short: "Memorystore" },
    monitoring: { name: "Cloud Monitoring", short: "Monitoring" },
  },
};

export function serviceName(provider: string, kind: string, fallback: string): string {
  return SERVICES[provider]?.[kind]?.name ?? fallback;
}

export const PROVIDER_LABEL: Record<string, string> = {
  aws: "AWS",
  azure: "Azure",
  gcp: "Google Cloud",
};
