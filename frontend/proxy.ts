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
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
    "/__clerk/:path*",
  ],
};
