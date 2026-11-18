import Link from "next/link";

/**
 * Shown on /sign-in and /sign-up when the deployment has no Clerk keys.
 *
 * The alternative was the 500 that used to come out of proxy.ts, which told
 * a visitor nothing and told an operator only "Missing publishableKey" in a
 * server log they may not be reading. This says which pages are shut, why,
 * and where the rest of the product still works -- the pricing engine,
 * diagrams and Terraform export need no account.
 */
export function AuthNotConfigured({ action }: { action: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div
        role="status"
        className="max-w-md rounded-2xl border border-line bg-surface p-7 text-center shadow-xs"
      >
        <h1 className="text-[19px] font-semibold text-ink">
          {action} is unavailable
        </h1>
        <p className="mt-3 text-[14.5px] leading-relaxed text-ink-2">
          This deployment has no authentication provider configured, so
          accounts cannot be created or signed in to. The workspace, FinOps
          Live and cloud-account connection stay closed until it is.
        </p>
        <p className="mt-3 text-[13.5px] leading-relaxed text-ink-3">
          Everything that does not need an account still works: pricing a
          workload, the architecture diagrams, the price index and the
          Terraform export.
        </p>
        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Link
            href="/estimate"
            className="rounded-lg bg-accent px-4 py-2 text-[13.5px] font-medium text-canvas hover:opacity-95"
          >
            Price a workload
          </Link>
          <Link
            href="/"
            className="rounded-lg border border-line px-4 py-2 text-[13.5px] font-medium text-ink-2 hover:bg-sunk"
          >
            Back to home
          </Link>
        </div>
      </div>
    </div>
  );
}
