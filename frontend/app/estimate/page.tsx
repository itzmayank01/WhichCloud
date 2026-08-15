import { EstimateWorkbench } from "@/components/estimate/EstimateWorkbench";

export const metadata = {
  title: "Price your app — WhichCloud",
  description:
    "Describe your app and get three priced architectures across AWS, Azure and Google Cloud.",
};

export default function EstimatePage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-14">
      <h1 className="text-balance text-[clamp(2rem,4.5vw,3rem)] font-semibold leading-[1.06] tracking-[-0.03em]">
        Price your app
      </h1>
      <p className="mt-4 max-w-2xl text-[17px] leading-relaxed text-ink-2">
        Describe it in a sentence, or set the details yourself. You get three
        architectures — cheapest, balanced, most reliable — priced against live
        provider rates.
      </p>

      <div className="mt-10">
        <EstimateWorkbench />
      </div>
    </div>
  );
}
