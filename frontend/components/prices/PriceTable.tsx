"use client";

import { Icon } from "@iconify/react";
import { useEffect, useMemo, useState } from "react";
import { money, type CatalogRow } from "@/lib/api";

/**
 * The catalog, browsable.
 *
 * Everything else on this site quotes the catalog at you; this is the page
 * where you read it yourself. That is the whole point of it existing, so it
 * gets filters and sorting rather than a pretty summary: the claim is that
 * these prices are real and checkable, and checkable means you can find the
 * row and compare it against the provider's own page.
 *
 * Filtering and sorting happen here rather than on the server. The API caps a
 * response at 500 rows, so the set is small enough to hold, and doing it in
 * the browser means a filter costs nothing and never shows a stale result
 * from a cached fetch.
 */

const CHROME: Record<string, { label: string; logo: string }> = {
  aws: { label: "AWS", logo: "logos:aws" },
  azure: { label: "Azure", logo: "logos:microsoft-azure" },
  gcp: { label: "Google", logo: "logos:google-cloud" },
};

type SortKey = "monthly_usd" | "vcpu" | "memory_gb" | "name";

export function PriceTable({
  rows,
  region,
}: {
  rows: CatalogRow[];
  region: string;
}) {
  const [provider, setProvider] = useState<string>("all");
  const [arch, setArch] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("monthly_usd");
  const [asc, setAsc] = useState(true);

  const providers = useMemo(
    () => [...new Set(rows.map((r) => r.provider))].sort(),
    [rows],
  );
  const arches = useMemo(
    () => [...new Set(rows.map((r) => r.arch).filter(Boolean))].sort(),
    [rows],
  );

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const out = rows.filter(
      (r) =>
        (provider === "all" || r.provider === provider) &&
        (arch === "all" || r.arch === arch) &&
        (!q ||
          r.name?.toLowerCase().includes(q) ||
          r.sku?.toLowerCase().includes(q)),
    );
    out.sort((a, b) => {
      const av = a[sort] ?? 0;
      const bv = b[sort] ?? 0;
      const cmp =
        typeof av === "string" ? av.localeCompare(String(bv)) : Number(av) - Number(bv);
      return asc ? cmp : -cmp;
    });
    return out;
  }, [rows, provider, arch, query, sort, asc]);

  const head = (key: SortKey, label: string, align = "left") => (
    <th
      scope="col"
      className={`whitespace-nowrap px-3 py-2.5 text-${align} font-medium`}
    >
      <button
        onClick={() => {
          if (sort === key) setAsc((v) => !v);
          else {
            setSort(key);
            setAsc(key === "name");
          }
        }}
        className={`inline-flex items-center gap-1 rounded-sm transition-colors hover:text-ink ${
          sort === key ? "text-ink" : "text-ink-3"
        }`}
      >
        {label}
        <span aria-hidden className="text-[10px]">
          {sort === key ? (asc ? "▲" : "▼") : ""}
        </span>
      </button>
    </th>
  );

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2.5">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search a machine type…"
          aria-label="Search machine types"
          className="min-w-[200px] flex-1 rounded-lg border border-line bg-surface px-3 py-2 font-mono text-[14px] text-ink placeholder:text-ink-3"
        />

        <Segmented
          value={provider}
          onChange={setProvider}
          options={[
            { value: "all", label: "All clouds" },
            ...providers.map((p) => ({
              value: p,
              label: CHROME[p]?.label ?? p,
            })),
          ]}
        />

        {arches.length > 1 && (
          <Segmented
            value={arch}
            onChange={setArch}
            options={[
              { value: "all", label: "Any chip" },
              ...arches.map((a) => ({ value: a as string, label: a as string })),
            ]}
          />
        )}
      </div>

      <p className="mt-3 font-mono text-[13px] font-medium text-ink-3">
        {shown.length.toLocaleString()} of {rows.length.toLocaleString()} machines
        {" · "}
        {region}
      </p>

      <div className="mt-3 overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full border-collapse text-[14px]">
          <thead className="border-b border-line bg-sunk text-[12.5px] uppercase tracking-[0.06em]">
            <tr>
              <th scope="col" className="px-3 py-2.5 text-left font-medium text-ink-3">
                Cloud
              </th>
              {head("name", "Machine")}
              {head("vcpu", "vCPU", "right")}
              {head("memory_gb", "Memory", "right")}
              <th scope="col" className="px-3 py-2.5 text-left font-medium text-ink-3">
                Chip
              </th>
              {head("monthly_usd", "Per month", "right")}
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => (
              <tr
                key={`${r.provider}-${r.sku}-${r.region}`}
                className="border-b border-line last:border-0 hover:bg-sunk"
              >
                <td className="px-3 py-2">
                  <span className="inline-flex items-center gap-2 whitespace-nowrap">
                    {CHROME[r.provider]?.logo && (
                      <Icon
                        icon={CHROME[r.provider].logo}
                        width={15}
                        height={15}
                        aria-hidden
                      />
                    )}
                    <span className="text-ink-2">
                      {CHROME[r.provider]?.label ?? r.provider}
                    </span>
                  </span>
                </td>
                <td className="whitespace-nowrap px-3 py-2 font-mono text-[13.5px] text-ink">
                  {r.name || r.sku}
                </td>
                <td className="tnum px-3 py-2 text-right font-mono text-[13.5px] text-ink-2">
                  {r.vcpu ?? "—"}
                </td>
                <td className="tnum px-3 py-2 text-right font-mono text-[13.5px] text-ink-2">
                  {r.memory_gb ? `${r.memory_gb} GB` : "—"}
                </td>
                <td className="px-3 py-2 font-mono text-[13px] text-ink-3">
                  {r.arch ?? "—"}
                </td>
                <td className="tnum px-3 py-2 text-right font-mono text-[14px] font-semibold text-ink">
                  {money(r.monthly_usd, 2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {shown.length === 0 && (
          <p className="px-4 py-10 text-center text-[15px] text-ink-3">
            Nothing matches that. Try a shorter search, or a different cloud.
          </p>
        )}
      </div>
    </div>
  );
}

function Segmented({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-surface p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={`rounded-md px-2.5 py-1.5 text-[13.5px] font-medium transition-colors ${
            value === o.value
              ? "bg-accent-wash text-accent"
              : "text-ink-3 hover:text-ink-2"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
