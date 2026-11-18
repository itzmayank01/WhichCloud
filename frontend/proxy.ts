import { NextResponse, type NextFetchEvent, type NextRequest } from "next/server";
import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

/**
 * Everything is public except the workspace, connecting a cloud account, and
 * FinOps Live.
 *
 * The landing page, the price index and the provenance section are the
 * argument for the product and have to be readable without an account. The
 * dashboard and the FinOps Live page are where a description is sent to a
 * model and stored against a person, so they need one. Connecting a cloud
 * account needs one too, and needs it *before* the wizard starts rather than
 * after: /connect/* used to be public and only redirected to /finops (which
 * requires sign-in) once the user had already stepped through the flow, so
 * an anonymous visitor could get most of the way through connecting an
 * account before hitting a sign-in wall. Gating /connect here moves that
 * prompt to the front of the funnel instead of the middle of it.
 *
 * Protection is declared as a matcher rather than by listing public routes.
 * With a public list, a route added later is private by accident and nobody
 * notices until someone reports a page they cannot reach; this way a new page
 * is public until it is deliberately named here, which fails in the direction
 * that gets caught immediately.
 */
const isProtected = createRouteMatcher(["/dashboard(.*)", "/finops(.*)", "/connect(.*)"]);

/** FinOps Live has a credential-free demo account so the page can be shown
 *  without an account. It is the one protected path that stays open, and it
 *  is keyed on an exact account_id rather than a prefix so that a real
 *  account id can never be mistaken for it. */
function isDemoRequest(request: NextRequest): boolean {
  return (
    request.nextUrl.pathname.startsWith("/finops") &&
    request.nextUrl.searchParams.get("account_id") === "demo"
  );
}

const clerkHandler = clerkMiddleware(async (auth, request) => {
  if (isProtected(request) && !isDemoRequest(request)) {
    await auth.protect();
  }
});

/**
 * Both keys are required: the publishable key names the Clerk instance and
 * the secret key authenticates this server to it. One without the other is a
 * half-configured deployment, which fails in more confusing ways than no
 * configuration at all, so it counts as unconfigured.
 */
function clerkConfigured(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY && process.env.CLERK_SECRET_KEY,
  );
}

/**
 * Why this is guarded at all: clerkMiddleware() throws "Missing
 * publishableKey" the moment it runs without credentials, and because it runs
 * here -- before any route renders -- the throw became a 500 on every path in
 * the matcher. That included /api/(.*), so the two landing API routes 500'd
 * too, and the header nav prefetches /connect and /finops on every page, so
 * four 500s were recorded per page view. It failed all nine Playwright specs,
 * not just the two that visit those pages.
 *
 * Why the guard redirects rather than calling NextResponse.next(): next()
 * lets the request THROUGH, so a deployment missing its Clerk keys served
 * /dashboard, /finops and the /connect cloud-account wizard to anyone who
 * asked. Without credentials nobody can sign in, so there is no version of
 * this state in which those pages should answer 200 -- the gate has to close,
 * not open. Sending them to /sign-in keeps them shut, and /sign-in renders an
 * "authentication is not configured" notice (components/AuthNotConfigured)
 * rather than a Clerk component that cannot mount without a key.
 *
 * A well-formed fake key is not a way around this either: the middleware then
 * initialises and redirects every browser navigation to that key's Clerk FAPI
 * host for the session handshake. For an invented key that host does not
 * resolve, so /connect, /sign-in and even the demo FinOps page fail at the
 * network layer instead of rendering.
 *
 * When both keys are present nothing here changes.
 */
export default function proxy(request: NextRequest, event: NextFetchEvent) {
  if (!clerkConfigured()) {
    if (isProtected(request) && !isDemoRequest(request)) {
      const signIn = new URL("/sign-in", request.url);
      signIn.searchParams.set("redirect_url", request.url);
      return NextResponse.redirect(signIn);
    }
    return NextResponse.next();
  }
  return clerkHandler(request, event);
}

export const config = {
  matcher: [
    /*
     * Only run Clerk on routes that actually need auth or are Clerk internals.
     *
     * Public pages (/, /prices, /architecture, /terraform, /plan, /audit,
     * /estimate, /optimizations, /finops-live, /sign-in, /sign-up) are
     * intentionally excluded from this matcher so Vercel can cache them on
     * its CDN edge network.  Clerk's <Show> / useUser hooks still work on
     * those pages because they read auth state from cookies client-side.
     *
     * Running Clerk on every request (the old pattern) caused Clerk to set
     *   cache-control: private, no-cache, no-store, max-age=0
     * which forced x-vercel-cache: MISS on every hit, meaning every visitor
     * triggered a cold serverless invocation even on fully-static pages.
     */

    // Protected app routes — auth must run here
    "/dashboard(.*)",
    "/finops(.*)",
    "/connect(.*)",

    // Sign-in / sign-up flows
    "/sign-in(.*)",
    "/sign-up(.*)",

    // Clerk's own internal endpoints
    "/__clerk(.*)",

    // Next.js API routes (may need auth state server-side)
    "/api/(.*)",
  ],
};
