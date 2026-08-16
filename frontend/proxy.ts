import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

/**
 * Everything is public except the workspace.
 *
 * The landing page, the price index and the provenance section are the
 * argument for the product and have to be readable without an account. The
 * dashboard is where a description is sent to a model and stored against a
 * person, so it is the part that needs one.
 *
 * Protection is declared as a matcher rather than by listing public routes.
 * With a public list, a route added later is private by accident and nobody
 * notices until someone reports a page they cannot reach; this way a new page
 * is public until it is deliberately named here, which fails in the direction
 * that gets caught immediately.
 */
const isProtected = createRouteMatcher(["/dashboard(.*)"]);

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
