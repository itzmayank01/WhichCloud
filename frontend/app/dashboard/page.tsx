import { auth, currentUser } from "@clerk/nextjs/server";
import { ArchitectureWorkbench } from "@/components/architecture/ArchitectureWorkbench";
import { CostedAdvisor } from "@/components/architecture/CostedAdvisor";

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
            Describe what you need in plain words. You get three costed
            options, one recommended, with every figure taken from the
            provider&apos;s own published rates.
          </p>
        </div>
      </div>

      {/* The advisor first: it answers the question somebody arrives with --
          what should I build and can I afford it -- and needs no knowledge of
          services to use. The workbench below draws a system for someone who
          already knows what they want, which is the rarer case. */}
      <div className="mt-8">
        <CostedAdvisor />
      </div>

      <div className="mt-14 border-t border-line pt-10">
        <h2 className="text-[20px] font-semibold tracking-[-0.015em]">
          Already know what you want to build?
        </h2>
        <p className="mt-2 max-w-2xl text-[15px] leading-relaxed text-ink-2">
          Describe the services by name and they are drawn as described —
          every one, whether or not the price catalog reaches it.
        </p>
        <div className="mt-6">
          <ArchitectureWorkbench owner={userId ?? ""} />
        </div>
      </div>
    </div>
  );
}
