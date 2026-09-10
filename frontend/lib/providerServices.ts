/** Per-provider service catalog: what each cloud CALLS a thing, and the mark
 *  it uses for it.
 *
 *  Deliberately not an override layer over an AWS base. An override still
 *  falls back when a key is missing, and that silent fallback is precisely
 *  how every icon on a Google Cloud diagram came to be an AWS icon -- and how
 *  the AWS smile ended up on a container labelled "Google Cloud project".
 *  There is no base to fall through to: a gap here renders a neutral
 *  placeholder and logs which provider and kind is missing, so it surfaces
 *  instead of disguising itself as somebody else's product.
 *
 *  Generated from the vendors' own icon sets; see public/icons/README.md.
 */
export type CloudId = "aws" | "gcp" | "azure";

export type ServiceEntry = { name: string; icon: string };

export const PROVIDER_SERVICES: Record<string, Record<string, ServiceEntry>> = {
  gcp: {
    apigateway: { name: "Cloud Load Balancing", icon: "/icons/gcp/cloudlb.png" },
    athena: { name: "BigQuery", icon: "/icons/gcp/bigquery.png" },
    audit: { name: "Cloud Audit Logs", icon: "/icons/gcp/cloudlogging.png" },
    auth: { name: "Cloud IAM", icon: "/icons/gcp/iam.png" },
    backup: { name: "Cloud Storage", icon: "/icons/gcp/cloudstorage.png" },
    cache: { name: "Memorystore", icon: "/icons/gcp/memorystore.png" },
    compute: { name: "Compute Engine", icon: "/icons/gcp/computeengine.png" },
    compute_fargate: { name: "Cloud Run", icon: "/icons/gcp/cloudrun.png" },
    database: { name: "Cloud SQL", icon: "/icons/gcp/cloudsql.png" },
    database_replica: { name: "Cloud SQL", icon: "/icons/gcp/cloudsql.png" },
    dns: { name: "Cloud DNS", icon: "/icons/gcp/clouddns.png" },
    dynamodb: { name: "Firestore", icon: "/icons/gcp/firestore.png" },
    flowlogs: { name: "VPC Flow Logs", icon: "/icons/gcp/vpcnetwork.png" },
    glue: { name: "BigQuery", icon: "/icons/gcp/bigquery.png" },
    kms: { name: "Cloud KMS", icon: "/icons/gcp/cloudkms.png" },
    lambda: { name: "Cloud Functions", icon: "/icons/gcp/cloudfunctions.png" },
    loadbalancer: { name: "Cloud Load Balancing", icon: "/icons/gcp/cloudlb.png" },
    monitoring: { name: "Cloud Monitoring", icon: "/icons/gcp/cloudmonitoring.png" },
    nat: { name: "Cloud NAT", icon: "/icons/gcp/cloudnat.png" },
    cdn: { name: "Cloud CDN", icon: "/icons/gcp/cloudcdn.png" },
    network: { name: "Data transfer", icon: "/icons/gcp/cloudcdn.png" },
    notification: { name: "Pub/Sub", icon: "/icons/gcp/pubsub.png" },
    posture: { name: "Security Command Center", icon: "/icons/gcp/scc.png" },
    queue: { name: "Pub/Sub", icon: "/icons/gcp/pubsub.png" },
    rekognition: { name: "Cloud Run", icon: "/icons/gcp/cloudrun.png" },
    search: { name: "Firestore", icon: "/icons/gcp/firestore.png" },
    secrets: { name: "Secret Manager", icon: "/icons/gcp/secretmanager.png" },
    storage: { name: "Cloud Storage", icon: "/icons/gcp/cloudstorage.png" },
    threat: { name: "Security Command Center", icon: "/icons/gcp/scc.png" },
    tls: { name: "Certificate Manager", icon: "/icons/gcp/certmanager.png" },
    tracing: { name: "Cloud Trace", icon: "/icons/gcp/cloudmonitoring.png" },
    waf: { name: "Cloud Armor", icon: "/icons/gcp/cloudarmor.png" },
    warehouse: { name: "BigQuery", icon: "/icons/gcp/bigquery.png" },
  },
  azure: {
    flowlogs: { name: "NSG flow logs", icon: "/icons/azure/nsg.png" },
    tracing: { name: "Application Insights", icon: "/icons/azure/monitor.svg" },
    audit: { name: "Activity log", icon: "/icons/azure/monitor.svg" },
    monitoring: { name: "Azure Monitor", icon: "/icons/azure/monitor.svg" },
    apigateway: { name: "Application Gateway", icon: "/icons/azure/appgateway.png" },
    athena: { name: "Synapse Analytics", icon: "/icons/azure/synapse.png" },
    backup: { name: "Blob Storage", icon: "/icons/azure/blob.png" },
    cache: { name: "Azure Cache for Redis", icon: "/icons/azure/redis.png" },
    compute: { name: "Virtual Machines", icon: "/icons/azure/vm.png" },
    database: { name: "Azure Database for PostgreSQL", icon: "/icons/azure/postgresql.png" },
    database_replica: { name: "Azure Database for PostgreSQL", icon: "/icons/azure/postgresql.png" },
    dns: { name: "Azure DNS", icon: "/icons/azure/azuredns.png" },
    dynamodb: { name: "Cosmos DB", icon: "/icons/azure/cosmosdb.png" },
    glue: { name: "Synapse Analytics", icon: "/icons/azure/synapse.png" },
    kms: { name: "Key Vault", icon: "/icons/azure/keyvault.png" },
    lambda: { name: "Azure Functions", icon: "/icons/azure/functions.png" },
    loadbalancer: { name: "Application Gateway", icon: "/icons/azure/appgateway.png" },
    nat: { name: "NAT Gateway", icon: "/icons/azure/natgateway.png" },
    cdn: { name: "Azure Front Door", icon: "/icons/azure/frontdoor.png" },
    network: { name: "Data transfer", icon: "/icons/azure/frontdoor.png" },
    posture: { name: "Defender for Cloud", icon: "/icons/azure/defender.png" },
    search: { name: "Cosmos DB", icon: "/icons/azure/cosmosdb.png" },
    secrets: { name: "Key Vault", icon: "/icons/azure/keyvault.png" },
    storage: { name: "Blob Storage", icon: "/icons/azure/blob.png" },
    threat: { name: "Defender for Cloud", icon: "/icons/azure/defender.png" },
    tls: { name: "App Service Certificate", icon: "/icons/azure/keyvaultcert.png" },
    waf: { name: "Front Door WAF", icon: "/icons/azure/frontdoorwaf.png" },
    warehouse: { name: "Synapse Analytics", icon: "/icons/azure/synapse.png" },
  },
};

/** The chip mark on a container label -- the account/project/subscription
 *  boundary. This was hardcoded to the AWS wordmark, so a GCP diagram
 *  announced itself with the AWS smile. */
export const CLOUD_MARK: Record<CloudId, string | null> = {
  aws: null, // drawn as the "aws" wordmark in the badge component
  gcp: "/icons/gcp/vpcnetwork.png",
  azure: "/icons/azure/vnet.png",
};
