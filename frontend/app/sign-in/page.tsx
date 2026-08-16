import { configuredProviders, signIn } from "@/auth";

/**
 * One page, one decision: which account to use.
 *
 * There is no separate sign-up. With OAuth the two are the same action --
 * whether an account already exists is the provider's business, not something
 * to ask someone to declare up front.
 *
 * No phone number is collected, and no field is required beyond what the
 * provider returns. The previous setup demanded a phone number and then
 * rejected Indian ones, which is what this replaces.
 */

const LABEL: Record<string, { name: string; mark: React.ReactNode }> = {
  google: {
    name: "Google",
    mark: (
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden>
        <path fill="#4285F4" d="M23.5 12.3c0-.9-.1-1.5-.2-2.2H12v4.1h6.6c-.1 1.1-.9 2.8-2.5 3.9l3.8 3c2.3-2.1 3.6-5.2 3.6-8.8z" />
        <path fill="#34A853" d="M12 24c3.2 0 6-1.1 8-2.9l-3.8-3c-1 .7-2.4 1.2-4.2 1.2-3.2 0-5.9-2.1-6.9-5l-3.9 3C3.2 21.3 7.3 24 12 24z" />
        <path fill="#FBBC05" d="M5.1 14.3c-.2-.7-.4-1.5-.4-2.3s.1-1.6.4-2.3l-4-3.1C.4 8.2 0 10 0 12s.4 3.8 1.1 5.4l4-3.1z" />
        <path fill="#EA4335" d="M12 4.7c2.3 0 3.8 1 4.7 1.8l3.4-3.3C18 1.2 15.2 0 12 0 7.3 0 3.2 2.7 1.1 6.6l4 3.1c1-2.9 3.7-5 6.9-5z" />
      </svg>
    ),
  },
  github: {
    name: "GitHub",
    mark: (
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden>
        <path fill="currentColor" d="M12 0C5.4 0 0 5.4 0 12c0 5.3 3.4 9.8 8.2 11.4.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1.1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.8-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0C17.3 4.7 18.3 5 18.3 5c.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 24 12c0-6.6-5.4-12-12-12z" />
      </svg>
    ),
  },
};

export default function SignInPage() {
  const available = configuredProviders();

  return (
    <div className="flex min-h-[70vh] items-center justify-center px-6 py-16">
      <div className="w-full max-w-sm">
        <h1 className="text-center text-[26px] font-semibold tracking-[-0.02em]">
          Sign in to WhichCloud
        </h1>
        <p className="mt-2 text-center text-[15px] leading-relaxed text-ink-2">
          Save the architectures you price, and come back to them.
        </p>

        <div className="mt-8 space-y-3">
          {available.map((id) => {
            const provider = LABEL[id];
            if (!provider) return null;
            return (
              <form
                key={id}
                action={async () => {
                  "use server";
                  await signIn(id, { redirectTo: "/architecture" });
                }}
              >
                <button
                  type="submit"
                  className="flex w-full items-center justify-center gap-3 rounded-lg border border-line-strong bg-surface px-5 py-3 text-[15.5px] font-medium text-ink transition-colors hover:bg-sunk"
                >
                  {provider.mark}
                  Continue with {provider.name}
                </button>
              </form>
            );
          })}

          {available.length === 0 && (
            <div className="rounded-lg bg-caution-wash px-4 py-3 text-[14.5px] leading-relaxed text-caution">
              No sign-in provider is configured. Set{" "}
              <code className="font-mono text-[13px]">AUTH_GOOGLE_ID</code> and{" "}
              <code className="font-mono text-[13px]">AUTH_GOOGLE_SECRET</code>{" "}
              in <code className="font-mono text-[13px]">.env.local</code>, then
              restart the dev server.
            </div>
          )}
        </div>

        <p className="mt-8 text-center text-[13.5px] leading-relaxed text-ink-3">
          No phone number, and nothing collected beyond what your provider
          returns.
        </p>
      </div>
    </div>
  );
}
