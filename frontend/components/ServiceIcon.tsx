"use client";

import { Icon } from "@iconify/react";
import Image from "next/image";

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
  network: "logos:aws-cloudfront",
  loadbalancer: "logos:aws-elb",
  compute: "logos:aws-ecs",
  database: "logos:aws-rds",
  storage: "logos:aws-s3",
  cache: "logos:aws-elasticache",
  monitoring: "logos:aws-cloudwatch",
};

const FILE_ICON: Record<string, Record<string, string>> = {
  azure: {
    network: "/icons/azure/front-door.svg",
    loadbalancer: "/icons/azure/load-balancer.svg",
    compute: "/icons/azure/virtual-machines.svg",
    database: "/icons/azure/postgresql.svg",
    storage: "/icons/azure/storage.svg",
  },
  gcp: {
    network: "/icons/gcp/cloud-cdn.svg",
    loadbalancer: "/icons/gcp/cloud-load-balancing.svg",
    compute: "/icons/gcp/compute-engine.svg",
    database: "/icons/gcp/cloud-sql.svg",
    storage: "/icons/gcp/cloud-storage.svg",
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
        aria-hidden
      />
    );
  }

  const iconify = provider === "aws" ? AWS_ICON[kind] : undefined;
  if (iconify) {
    return <Icon icon={iconify} width={size} height={size} style={style} aria-hidden />;
  }

  // Nothing published for this service — a neutral square rather than a
  // wrong logo.
  return (
    <span
      className="grid place-items-center rounded-md bg-sunk"
      style={{ width: size, height: size, ...style }}
      aria-hidden
    >
      <span className="h-2 w-2 rounded-sm bg-ink-3" />
    </span>
  );
}
