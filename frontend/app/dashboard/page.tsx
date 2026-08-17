import { currentUser } from "@clerk/nextjs/server";
import { CostedAdvisor } from "@/components/architecture/CostedAdvisor";

/* Behind sign-in, unlike the rest of the site. A description here is sent to
   a model and will shortly be stored against a person, which is the line
   between reading the argument for the product and using it. */
export const metadata = {
  title: "Workspace — WhichCloud",
  description: "Describe what you need and get three costed architectures.",
};

export default async function DashboardPage() {
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

      {/* One thing on this page. The advisor answers the question somebody
          arrives with -- what should I build and can I afford it -- and needs
          no knowledge of services to use. A second tool alongside it, with
          templates and its own prompt, asked the visitor to decide which of
          two products they wanted before either had answered anything. */}
      <div className="mt-8">
        <CostedAdvisor />
      </div>
    </div>
  );
}
