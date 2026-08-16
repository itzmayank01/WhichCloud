import { auth, currentUser } from "@clerk/nextjs/server";
import { ArchitectureWorkbench } from "@/components/architecture/ArchitectureWorkbench";

/* Behind sign-in, unlike the rest of the site. A description here is sent to
   a model and will shortly be stored against a person, which is the line
   between reading the argument for the product and using it. */
export const metadata = {
  title: "Workspace — WhichCloud",
  description: "Describe a system and see it drawn across AWS, Azure and Google.",
};

export default async function DashboardPage() {
  const { userId } = await auth();
  const user = await currentUser();
  const name = user?.firstName ?? user?.username ?? null;

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <h1 className="text-[clamp(1.75rem,3.6vw,2.5rem)] font-semibold tracking-[-0.025em]">
            {name ? `Welcome back, ${name}` : "Your workspace"}
          </h1>
          <p className="mt-3 max-w-2xl text-[16px] leading-relaxed text-ink-2">
            Describe a system and it is drawn as described — every service
            named, whether or not the price catalog reaches it. Services it
            cannot price say so rather than showing nothing.
          </p>
        </div>
      </div>

      <div className="mt-8">
        <ArchitectureWorkbench owner={userId ?? ""} />
      </div>
    </div>
  );
}
