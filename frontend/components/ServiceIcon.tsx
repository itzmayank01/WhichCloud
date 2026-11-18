"use client";

import { Icon } from "@iconify/react";
import Image from "next/image";
import { iconFor } from "@/lib/serviceIcon";
import { KIND_ICON_LABEL } from "@/lib/serviceMeta";

/**
 * Official provider service icons.
 *
 * Three sources, because the three providers licence their artwork
 * differently:
 *
 *   AWS    Iconify's `logos` set, rendered inline. AWS's own pack is CC-BY-ND,
 *          so it cannot be recoloured or restyled; these are equivalents that
 *          can.
 *   Azure  Microsoft's official pack, MIT licensed — free to redistribute.
 *          Copied into public/icons/azure.
 *   GCP    Google's official pack, Apache 2.0 — same. public/icons/gcp.
 *
 * Every icon is rendered at its published colours and never recoloured, which
 * keeps the CC-BY-ND spirit even where the licence would allow otherwise, and
 * means a diagram reads the way the provider's own documentation does.
 */

const AWS_ICON: Record<string, string> = {
  cdn: "logos:aws-cloudfront",
  loadbalancer: "logos:aws-elb",
  compute: "logos:aws-ecs",
  database: "logos:aws-rds",
  storage: "logos:aws-s3",
  cache: "logos:aws-elasticache",
  monitoring: "logos:aws-cloudwatch",
};

const FILE_ICON: Record<string, Record<string, string>> = {
  azure: {
    cdn: "/icons/azure/front-door.svg",
    network: "/icons/azure/vnet.png",
    waf: "/icons/azure/frontdoorwaf.png",
    loadbalancer: "/icons/azure/load-balancer.svg",
    apigateway: "/icons/azure/appgateway.png",
    compute: "/icons/azure/virtual-machines.svg",
    compute_fargate: "/icons/azure/aks.png",
    lambda: "/icons/azure/functions.png",
    database: "/icons/azure/postgresql.svg",
    database_replica: "/icons/azure/postgresql.png",
    dynamodb: "/icons/azure/cosmosdb.png",
    storage: "/icons/azure/storage.svg",
    cache: "/icons/azure/cache-redis.svg",
    warehouse: "/icons/azure/synapse.png",
    nat: "/icons/azure/natgateway.png",
    kms: "/icons/azure/keyvault.png",
    secrets: "/icons/azure/keyvault.png",
    tls: "/icons/azure/keyvaultcert.png",
    dns: "/icons/azure/azuredns.png",
    threat: "/icons/azure/defender.png",
    posture: "/icons/azure/defender.png",
    flowlogs: "/icons/azure/nsg.png",
    monitoring: "/icons/azure/monitor.svg",
  },
  gcp: {
    cdn: "/icons/gcp/cloud-cdn.svg",
    network: "/icons/gcp/vpcnetwork.png",
    waf: "/icons/gcp/cloudarmor.png",
    loadbalancer: "/icons/gcp/cloud-load-balancing.svg",
    apigateway: "/icons/gcp/cloudlb.png",
    compute: "/icons/gcp/compute-engine.svg",
    compute_fargate: "/icons/gcp/cloudrun.png",
    lambda: "/icons/gcp/cloudfunctions.png",
    database: "/icons/gcp/cloud-sql.svg",
    database_replica: "/icons/gcp/cloudsql.png",
    dynamodb: "/icons/gcp/firestore.png",
    storage: "/icons/gcp/cloud-storage.svg",
    cache: "/icons/gcp/memorystore.svg",
    warehouse: "/icons/gcp/bigquery.png",
    queue: "/icons/gcp/pubsub.png",
    streaming: "/icons/gcp/pubsub.png",
    nat: "/icons/gcp/cloudnat.png",
    kms: "/icons/gcp/cloudkms.png",
    secrets: "/icons/gcp/secretmanager.png",
    tls: "/icons/gcp/certmanager.png",
    dns: "/icons/gcp/clouddns.png",
    auth: "/icons/gcp/iam.png",
    threat: "/icons/gcp/scc.png",
    posture: "/icons/gcp/scc.png",
    audit: "/icons/gcp/cloudlogging.png",
    flowlogs: "/icons/gcp/firewallrules.png",
    monitoring: "/icons/gcp/cloud-monitoring.svg",
  },
};

/** Users sit outside every provider's icon set, so they get a drawn mark. */
function UsersGlyph({ size }: { size: number }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="#5A6270"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <circle cx="9" cy="8" r="3.2" />
      <path d="M2.5 20c0-3.6 2.9-6.5 6.5-6.5s6.5 2.9 6.5 6.5" />
      <circle cx="17" cy="7.5" r="2.4" />
      <path d="M17 12.5c2.5 0 4.5 2 4.5 4.5" />
    </svg>
  );
}

export function ServiceIcon({
  provider,
  kind,
  size = 40,
  faded = false,
}: {
  provider: string;
  kind: string;
  size?: number;
  faded?: boolean;
}) {
  const style = faded ? { opacity: 0.4 } : undefined;

  if (kind === "client") {
    return (
      <span style={style}>
        <UsersGlyph size={size} />
      </span>
    );
  }

  const file = FILE_ICON[provider]?.[kind];
  if (file) {
    return (
      <Image
        src={file}
        alt=""
        width={size}
        height={size}
        style={style}
        /* These are diagram content, not decoration further down the page —
           a box whose icon arrives late reads as a box with no icon. They
           are a few hundred bytes each, so deferring them buys nothing. */
        loading="eager"
        aria-hidden
      />
    );
  }

  const iconify = provider === "aws" ? AWS_ICON[kind] : undefined;
  if (iconify) {
    return <Icon icon={iconify} width={size} height={size} style={style} aria-hidden />;
  }

  // The rest of AWS's kinds (NAT, KMS, Route 53, Backup...) through the same
  // official PNG set the architecture graph draws with.
  const png = provider === "aws" && KIND_ICON_LABEL[kind] ? iconFor(KIND_ICON_LABEL[kind]) : null;
  if (png) {
    return (
      <Image src={png} alt="" width={size} height={size} style={style} loading="eager" aria-hidden />
    );
  }

  // Nothing published for this service in the provider's own pack — a
  // neutral mark rather than a wrong logo, per the note at the top.
  //
  // The intent was right and the execution was invisible. This was a
  // `bg-sunk` tile with an 8px dot inside it, and `--surface-sunk`
  // resolves to `--paper` in light mode: pure white, the exact colour of
  // the card behind it. So the tile disappeared and all that reached the
  // page was the dot, which reads as an image that failed to load rather
  // than as a service the provider publishes no icon for. It is not rare
  // either -- four of Azure's eight supporting services land here (backup,
  // telemetry, audit, auth), because neither Microsoft's nor Google's
  // vendored pack ships a mark for them.
  //
  // A bordered tile with a generic resource glyph reads as deliberate at
  // 24px, and the grey is a literal rather than a token so it cannot be
  // flattened into the background by either theme.
  return (
    <span
      className="grid place-items-center rounded-md border border-line"
      style={{
        width: size,
        height: size,
        backgroundColor: "rgba(127, 134, 148, 0.16)",
        ...style,
      }}
      aria-hidden
    >
      <svg
        viewBox="0 0 24 24"
        width={Math.round(size * 0.62)}
        height={Math.round(size * 0.62)}
        fill="none"
        stroke="currentColor"
        className="text-ink-3"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 2.8 20.5 7v10L12 21.2 3.5 17V7z" />
        <path d="M3.5 7 12 11.2 20.5 7M12 11.2v10" />
      </svg>
    </span>
  );
}
