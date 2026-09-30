"use client";

import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import { Icon } from "@iconify/react";
import { api, type GitHubRepo, type GitHubReposResponse } from "@/lib/api";

/** "3 days ago", "2 months ago" -- built on the platform's own
 *  Intl.RelativeTimeFormat rather than a date library, since this is the
 *  only relative-time spot in the app so far. */
function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.round((then - Date.now()) / 1000);
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  const divisions: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, "second"],
    [60, "minute"],
    [24, "hour"],
    [7, "day"],
    [4.34524, "week"],
    [12, "month"],
    [Number.POSITIVE_INFINITY, "year"],
  ];
  let duration = seconds;
  for (const [amount, unit] of divisions) {
    if (Math.abs(duration) < amount) return rtf.format(Math.round(duration), unit);
    duration /= amount;
  }
  return "";
}

const LANGUAGE_DOTS: Record<string, string> = {
  TypeScript: "bg-blue-500",
  JavaScript: "bg-yellow-400",
  Python: "bg-emerald-500",
  Go: "bg-cyan-500",
  Java: "bg-orange-500",
  Ruby: "bg-red-500",
  PHP: "bg-indigo-400",
  HCL: "bg-violet-500",
};

function RepoRow({
  repo,
  selected,
  onFocus,
}: {
  repo: GitHubRepo;
  selected: boolean;
  onFocus: () => void;
}) {
  const [owner, name] = repo.full_name.split("/", 2);
  const dot = (repo.language && LANGUAGE_DOTS[repo.language]) || "bg-ink-3/40";
  return (
    <div
      onMouseEnter={onFocus}
      data-selected={selected}
      className={`flex items-center justify-between gap-4 border-b border-line px-4 py-3 last:border-b-0 ${
        selected ? "bg-sunk" : ""
      }`}
    >
      <div className="flex min-w-0 items-center gap-3">
        <Icon
          icon={repo.private ? "mdi:lock-outline" : "mdi:earth"}
          className="h-4 w-4 shrink-0 text-ink-3"
        />
        <div className="min-w-0">
          <a
            href={repo.html_url}
            target="_blank"
            rel="noreferrer"
            className="truncate font-mono text-[13px] text-ink hover:underline"
          >
            <span className="text-ink-3">{owner}/</span>
            {name}
          </a>
          <div className="mt-0.5 flex items-center gap-2 text-[11.5px] text-ink-3">
            <span className="rounded border border-line px-1.5 py-0.5">
              {repo.private ? "Private" : "Public"}
            </span>
            {repo.language && (
              <span className="inline-flex items-center gap-1">
                <span className={`h-2 w-2 rounded-full ${dot}`} />
                {repo.language}
              </span>
            )}
            {repo.pushed_at && <span>pushed {relativeTime(repo.pushed_at)}</span>}
          </div>
        </div>
      </div>
      <button
        disabled
        title="Repository analysis lands in the next phase of this feature."
        className="shrink-0 cursor-not-allowed rounded-lg border border-line px-3 py-1.5 text-[12.5px] font-medium text-ink-3"
      >
        Analyse
      </button>
    </div>
  );
}

function RepoRowSkeleton() {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-line px-4 py-3 last:border-b-0">
      <div className="flex min-w-0 items-center gap-3">
        <div className="h-4 w-4 shrink-0 animate-pulse rounded bg-sunk" />
        <div>
          <div className="h-3.5 w-48 animate-pulse rounded bg-sunk" />
          <div className="mt-1.5 h-3 w-32 animate-pulse rounded bg-sunk" />
        </div>
      </div>
      <div className="h-7 w-16 shrink-0 animate-pulse rounded-lg bg-sunk" />
    </div>
  );
}

function GitHubAppContent() {
  const { getToken, isSignedIn } = useAuth();
  const searchParams = useSearchParams();

  const [data, setData] = useState<GitHubReposResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [connecting, setConnecting] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const searchRef = useRef<HTMLInputElement>(null);

  const banner = searchParams.get("connected")
    ? { kind: "ok" as const, text: "GitHub connected." }
    : searchParams.get("error")
      ? { kind: "error" as const, text: searchParams.get("error")! }
      : null;

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const token = (await getToken()) ?? undefined;
      const res = await api.githubRepos(token);
      setData(res);
    } catch (err) {
      setLoadError(
        err instanceof Error ? err.message : "Could not reach the repository list.",
      );
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    if (isSignedIn) void load();
  }, [isSignedIn, load]);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      const token = (await getToken()) ?? undefined;
      const res = await api.githubConnect(token);
      window.location.href = res.authorize_url;
    } catch (err) {
      setLoadError(
        err instanceof Error ? err.message : "Could not start the GitHub connection.",
      );
      setConnecting(false);
    }
  };

  const filtered = useMemo(() => {
    const repos = data?.repos ?? [];
    if (!query.trim()) return repos;
    const q = query.toLowerCase();
    return repos.filter((r) => r.full_name.toLowerCase().includes(q));
  }, [data, query]);

  // Clamped at render time rather than reset via an effect: the list
  // shrinks as the user types, and the previously-selected index can point
  // past the end of a shorter filtered list.
  const clampedSelected = Math.min(selected, Math.max(filtered.length - 1, 0));

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const inInput = document.activeElement === searchRef.current;
      if (e.key === "/" && !inInput) {
        e.preventDefault();
        searchRef.current?.focus();
        return;
      }
      if (!filtered.length) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelected(Math.min(clampedSelected + 1, filtered.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelected(Math.max(clampedSelected - 1, 0));
      } else if (e.key === "Enter" && inInput) {
        // Analysis is not built yet (Phase 2+) -- Enter is a no-op rather
        // than pretending to navigate somewhere.
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [filtered.length, clampedSelected]);

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col px-6 py-12">
      <div className="flex items-center justify-between border-b border-line pb-6">
        <div className="flex items-center gap-3.5">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-surface p-2 shadow-xs">
            <Icon icon="mdi:github" width={28} height={28} className="text-ink" />
          </div>
          <div>
            <div className="flex items-center gap-2 text-[12.5px] font-medium text-ink-3">
              <Link href="/connect" className="hover:text-ink">
                Onboarding
              </Link>
              <span>/</span>
              <span>Analyse a repository</span>
            </div>
            <h2 className="text-[20px] font-bold text-ink">Your repositories</h2>
          </div>
        </div>

        {data?.installed && (
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="rounded-lg border border-line bg-surface px-3 py-1.5 text-[13px] font-medium text-ink-2 hover:bg-sunk hover:text-ink disabled:opacity-60"
          >
            Manage access
          </button>
        )}
      </div>

      {banner && (
        <div
          className={`mt-5 rounded-xl border px-4 py-3 text-[13px] ${
            banner.kind === "ok"
              ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600"
              : "border-red-500/30 bg-red-500/10 text-red-500"
          }`}
        >
          {banner.text}
        </div>
      )}

      {loadError && (
        <div className="mt-5 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-[13px] text-red-500">
          {loadError}
          <button onClick={() => void load()} className="ml-3 underline">
            Retry
          </button>
        </div>
      )}

      {!loading && data && data.repos.length > 0 && !data.installed && (
        <div className="mt-5 flex items-center justify-between gap-3 rounded-xl border border-line bg-canvas px-4 py-3 text-[13px] text-ink-2">
          <span>Showing @{data.github_login}&apos;s public repositories only.</span>
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="shrink-0 rounded-lg bg-accent px-3 py-1.5 text-[12.5px] font-semibold text-white disabled:opacity-60"
          >
            Grant access to private repos
          </button>
        </div>
      )}

      {data && data.errors.length > 0 && (
        <div className="mt-5 space-y-1.5 rounded-xl border border-line bg-canvas p-3 text-[12.5px] text-ink-2">
          {data.errors.map((e) => (
            <div key={e} className="flex gap-2">
              <Icon icon="mdi:alert-outline" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ink-3" />
              <span>{e}</span>
            </div>
          ))}
        </div>
      )}

      {!loading && (!data || data.repos.length === 0) && !loadError ? (
        <div className="mt-20 flex flex-col items-center justify-center text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full border border-line bg-surface shadow-xs">
            <Icon icon="mdi:github" className="h-10 w-10 text-ink" />
          </div>
          <h3 className="mt-5 text-[18px] font-bold text-ink">No repositories yet</h3>
          <p className="mt-2 max-w-sm text-[13px] text-ink-2">
            Connect GitHub to list your repositories here. WhichCloud reads
            code and metadata only, on the repos you choose to share.
          </p>
          <button
            onClick={handleConnect}
            disabled={connecting}
            className="mt-5 inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-[13.5px] font-semibold text-white disabled:opacity-60"
          >
            <Icon icon="mdi:github" className="h-4 w-4" />
            {connecting ? "Redirecting to GitHub…" : "Connect GitHub"}
          </button>
        </div>
      ) : (
        <>
          <div className="relative mt-6">
            <Icon
              icon="mdi:magnify"
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3"
            />
            <input
              ref={searchRef}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSelected(0);
              }}
              placeholder="Search repositories… (press / to focus)"
              className="w-full rounded-lg border border-line bg-surface py-2 pl-9 pr-3 text-[13px] text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none"
            />
          </div>

          <div className="mt-3 overflow-hidden rounded-xl border border-line bg-surface">
            {loading
              ? Array.from({ length: 4 }).map((_, i) => <RepoRowSkeleton key={i} />)
              : filtered.map((repo, i) => (
                  <RepoRow
                    key={repo.full_name}
                    repo={repo}
                    selected={i === clampedSelected}
                    onFocus={() => setSelected(i)}
                  />
                ))}
            {!loading && filtered.length === 0 && (
              <div className="px-4 py-6 text-center text-[13px] text-ink-3">
                No repository matches &quot;{query}&quot;.
              </div>
            )}
          </div>
        </>
      )}
    </main>
  );
}

export default function GitHubAppPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[50vh] items-center justify-center">
          <Icon icon="line-md:loading-loop" className="h-8 w-8 text-accent animate-spin" />
        </div>
      }
    >
      <GitHubAppContent />
    </Suspense>
  );
}
