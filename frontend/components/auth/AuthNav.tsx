import { auth, signOut } from "@/auth";

/**
 * The header's account corner.
 *
 * A server component, so the signed-in state is settled before the page is
 * sent. The previous provider resolved it in the browser, which meant the
 * header rendered signed-out for a moment on every load and then swapped --
 * a flicker on every page of the site.
 */
export async function AuthNav() {
  const session = await auth();

  if (!session?.user) {
    return (
      <>
        <a
          href="/sign-in"
          className="text-sm text-ink-2 transition-colors hover:text-ink"
        >
          Sign in
        </a>
        <a
          href="/sign-in"
          className="rounded-lg bg-accent px-4 py-2 text-[15.5px] font-medium text-white transition-opacity hover:opacity-90"
        >
          Get started
        </a>
      </>
    );
  }

  const name = session.user.name ?? session.user.email ?? "Account";

  return (
    <div className="flex items-center gap-3">
      {session.user.image ? (
        /* Plain img: the avatar host differs per provider, and next/image
           would need every one listed in next.config before it would load. */
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={session.user.image}
          alt=""
          width={30}
          height={30}
          className="rounded-full border border-line"
        />
      ) : (
        <span className="grid h-[30px] w-[30px] place-items-center rounded-full bg-accent text-[13px] font-semibold text-white">
          {name.slice(0, 1).toUpperCase()}
        </span>
      )}
      <span className="hidden text-sm text-ink-2 sm:inline">{name}</span>
      <form
        action={async () => {
          "use server";
          await signOut({ redirectTo: "/" });
        }}
      >
        <button
          type="submit"
          className="text-sm text-ink-3 transition-colors hover:text-ink"
        >
          Sign out
        </button>
      </form>
    </div>
  );
}
