import { AuditWorkbench } from "@/components/audit/AuditWorkbench";

export const metadata = {
  title: "Audit — WhichCloud",
  description:
    "Upload a billing export and see what it would cost less to run, " +
    "with the trade-off attached to every figure.",
};

export default function AuditPage() {
  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-2xl font-semibold text-neutral-900">
          Audit a bill you already have
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-neutral-600">
          Upload a cost export — AWS Cost and Usage Report, GCP billing
          export or Azure cost export. Nothing leaves your browser except
          the file, nothing is stored, and no account access is asked for:
          v1 reads a CSV you can look at first, deliberately.
        </p>
      </header>
      <AuditWorkbench />
    </main>
  );
}
