import { currentUser } from "@clerk/nextjs/server";
import { WorkspaceView } from "@/components/workspace/WorkspaceView";

/* Behind sign-in, unlike the rest of the site. A description here is sent to
   a model and will shortly be stored against a person, which is the line
   between reading the argument for the product and using it. */
export const metadata = {
  title: "Workspace — WhichCloud",
  description: "Describe what you need and get a costed, drawn architecture.",
};

export default async function DashboardPage() {
  const user = await currentUser();
  const name = user?.firstName ?? user?.username ?? null;

  /* Full-bleed, not the site's centred column. The workspace is an
     application view -- the canvas is sized from the viewport, so a page
     container with its own max-width and vertical padding would be taking
     the space the diagram exists to use. */
  return <WorkspaceView name={name} />;
}
