/**
 * Whether this deployment has Clerk credentials.
 *
 * Kept in its own module because proxy.ts must not import from the render
 * tree -- Next deploys proxy separately and warns against sharing modules
 * with it -- so the proxy keeps its own copy of this check and the pages use
 * this one. The two must agree on the rule: both keys, or unconfigured.
 *
 * Read through a function rather than exported as a constant so it is
 * evaluated per render on the server instead of being frozen at module load.
 */
export function clerkConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY,
  );
}
