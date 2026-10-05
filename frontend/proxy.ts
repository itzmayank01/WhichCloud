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

export default clerkMiddleware(async (auth, request) => {
  if (isProtected(request)) {
    await auth.protect();
  }
});

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
