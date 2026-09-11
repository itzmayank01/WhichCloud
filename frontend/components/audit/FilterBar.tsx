"use client";

import { useRef, useState } from "react";
import type { CostRow } from "@/lib/api";
import {
  DIMENSIONS, OPERATORS, facet, money,
  type Dimension, type Filter, type Operator,
} from "@/lib/costReport";

/**
 * Filters, as chips that open a menu.
 *
 * The menu offers only values that are actually in the bill, priced, and
 * ranked by spend — so the common case ("show me the expensive thing") is
 * the first item rather than something to hunt for. And it is built from
 * the rows surviving the OTHER filters, so a filter can never be narrowed
 * into returning nothing.
 */
export function FilterBar({
  rows, filters, onChange,
}: {
  rows: CostRow[];
  filters: Filter[];
  onChange: (next: Filter[]) => void;
}) {
  const [open, setOpen] = useState<string | null>(null);
  /* A counter rather than Date.now(): the id only has to be unique among
     the filters on screen, and a clock read during render is unstable
     across the double render React does in development. */
  const nextId = useRef(0);

  const add = (dimension: Dimension) => {
    const filter: Filter = {
      id: `f${(nextId.current += 1)}`, dimension, operator: "is", values: [],
    };
    onChange([...filters, filter]);
    setOpen(filter.id);
  };
  const update = (id: string, patch: Partial<Filter>) =>
    onChange(filters.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  const remove = (id: string) => {
    onChange(filters.filter((f) => f.id !== id));
    setOpen(null);
  };

  const unused = DIMENSIONS.filter(
    (d) => !filters.some((f) => f.dimension === d.id),
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      {filters.map((filter) => (
        <div key={filter.id} className="relative">
          <button
            type="button"
            onClick={() => setOpen(open === filter.id ? null : filter.id)}
            className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
              filter.values.length
                ? "border-accent-line bg-accent-wash text-accent"
                : "border-dashed border-line-strong text-ink-3 hover:text-ink-2"
            }`}
          >
            <span className="font-semibold">
              {DIMENSIONS.find((d) => d.id === filter.dimension)?.label}
            </span>
            <span className="opacity-70">{filter.operator}</span>
            <span className="max-w-[220px] truncate font-medium">
              {filter.values.length === 0
                ? "any value"
                : filter.values.length <= 2
                  ? filter.values.join(", ")
                  : `${filter.values.length} values`}
            </span>
            <span aria-hidden className="opacity-50">▾</span>
          </button>

          {open === filter.id && (
            <FilterMenu
              rows={rows}
              filters={filters}
              filter={filter}
              onUpdate={(patch) => update(filter.id, patch)}
              onRemove={() => remove(filter.id)}
              onClose={() => setOpen(null)}
            />
          )}
        </div>
      ))}

      {unused.length > 0 && (
        <div className="relative">
          <button
            type="button"
            onClick={() => setOpen(open === "+" ? null : "+")}
            className="rounded-lg border border-dashed border-line-strong px-2.5 py-1.5 text-xs font-medium text-ink-3 hover:border-line hover:text-ink-2"
          >
            + Filter
          </button>
          {open === "+" && (
            <div className="absolute left-0 top-full z-20 mt-1 min-w-[160px] rounded-lg border border-line bg-surface p-1 shadow-lg">
              {unused.map((dimension) => (
                <button
                  key={dimension.id}
                  type="button"
                  onClick={() => add(dimension.id)}
                  className="block w-full rounded px-2.5 py-1.5 text-left text-xs text-ink-2 hover:bg-sunk hover:text-ink"
                >
                  {dimension.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {filters.length > 0 && (
        <button
          type="button"
          onClick={() => { onChange([]); setOpen(null); }}
          className="ml-1 text-xs text-ink-3 underline decoration-dotted underline-offset-2 hover:text-ink-2"
        >
          Clear
        </button>
      )}
    </div>
  );
}

function FilterMenu({
  rows, filters, filter, onUpdate, onRemove, onClose,
}: {
  rows: CostRow[];
  filters: Filter[];
  filter: Filter;
  onUpdate: (patch: Partial<Filter>) => void;
  onRemove: () => void;
  onClose: () => void;
}) {
  const [search, setSearch] = useState("");
  const free = filter.operator === "contains" || filter.operator === "does not contain";

  // Priced and ranked, from the rows the other filters still allow.
  const options = facet(rows, filter.dimension, filters, filter.id)
    .filter((o) => o.value.toLowerCase().includes(search.toLowerCase()));

  const toggle = (value: string) =>
    onUpdate({
      values: filter.values.includes(value)
        ? filter.values.filter((v) => v !== value)
        : [...filter.values, value],
    });

  return (
    <div className="absolute left-0 top-full z-20 mt-1 w-[300px] rounded-lg border border-line bg-surface shadow-lg">
      <div className="flex items-center gap-1 border-b border-line p-2">
        {OPERATORS.map((operator) => (
          <button
            key={operator}
            type="button"
            onClick={() => onUpdate({ operator: operator as Operator, values: [] })}
            className={`rounded px-1.5 py-1 text-[11px] transition-colors ${
              filter.operator === operator
                ? "bg-accent-wash font-semibold text-accent"
                : "text-ink-3 hover:text-ink-2"
            }`}
          >
            {operator}
          </button>
        ))}
      </div>

      {free ? (
        <div className="p-2">
          <input
            autoFocus
            value={filter.values[0] ?? ""}
            onChange={(e) => onUpdate({ values: e.target.value ? [e.target.value] : [] })}
            placeholder="Text to match…"
            className="w-full rounded border border-line bg-sunk px-2 py-1.5 text-xs text-ink outline-none focus:border-accent-line"
          />
          <p className="mt-1.5 text-[11px] leading-relaxed text-ink-3">
            Matches anywhere in the value, ignoring case.
          </p>
        </div>
      ) : (
        <>
          <div className="p-2 pb-1">
            <input
              autoFocus
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search values…"
              className="w-full rounded border border-line bg-sunk px-2 py-1.5 text-xs text-ink outline-none focus:border-accent-line"
            />
          </div>
          <ul className="max-h-[220px] overflow-y-auto p-1">
            {options.length === 0 && (
              <li className="px-2 py-3 text-center text-[11px] text-ink-3">
                No matching values.
              </li>
            )}
            {options.map((option) => (
              <li key={option.value}>
                <button
                  type="button"
                  onClick={() => toggle(option.value)}
                  className="flex w-full items-center justify-between gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-sunk"
                >
                  <span className="flex min-w-0 items-center gap-2">
                    <span
                      className={`flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-[3px] border text-[9px] leading-none ${
                        filter.values.includes(option.value)
                          ? "border-accent bg-accent text-white"
                          : "border-line-strong"
                      }`}
                    >
                      {filter.values.includes(option.value) ? "✓" : ""}
                    </span>
                    <span className="truncate text-ink-2">{option.value}</span>
                  </span>
                  <span className="shrink-0 font-mono text-[11px] text-ink-3">
                    {money(option.monthly_usd)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <div className="flex items-center justify-between border-t border-line p-2">
        <button
          type="button"
          onClick={onRemove}
          className="text-[11px] text-ink-3 hover:text-spend"
        >
          Remove filter
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded bg-accent px-2.5 py-1 text-[11px] font-semibold text-white"
        >
          Done
        </button>
      </div>
    </div>
  );
}
