import { auth, currentUser } from "@clerk/nextjs/server";
import { WorkspaceView } from "@/components/workspace/WorkspaceView";

/* Behind sign-in, unlike the rest of the site. A description here is sent to
   a model and will shortly be stored against a person, which is the line
   between reading the argument for the product and using it. */
export const metadata = {
  title: "Workspace — WhichCloud",
  description: "Describe what you need and get a costed, drawn architecture.",
};

export default async function DashboardPage() {
  /* A second check, behind the matcher in proxy.ts rather than instead of it.
     Clerk now deprecates `createRouteMatcher` on the grounds that a path
     matcher can diverge from how Next actually routes a request, leaving a
     page reachable by a path the matcher did not predict. The matcher stays
     because its bias is the safe one -- a new route is public until named --
     but the page that reads the data is the one place that cannot be missed,
     so it asks too. Without this, a divergence would not fail loudly: the
     workspace would render signed-out and greet the visitor as nobody. */
  const { isAuthenticated, redirectToSignIn } = await auth();
  if (!isAuthenticated) return redirectToSignIn();

  const user = await currentUser();
  const name = user?.firstName ?? user?.username ?? null;

  /* Full-bleed, not the site's centred column. The workspace is an
     application view -- the canvas is sized from the viewport, so a page
     container with its own max-width and vertical padding would be taking
     the space the diagram exists to use. */
  return <WorkspaceView name={name} />;
}
