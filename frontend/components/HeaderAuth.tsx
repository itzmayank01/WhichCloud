"use client";

/**
 * HeaderAuth – client component for the sign-in / workspace controls.
 *
 * Why a client component?
 *
 * The root layout is a React Server Component.  Clerk's <Show> component also
 * runs server-side and calls auth() internally to know whether the visitor is
 * signed in.  auth() reads from request headers that Clerk's Edge Middleware
 * sets -- so Clerk's middleware MUST run on every page for <Show> to work.
 *
 * That forced Clerk's middleware matcher to be as broad as possible, and
 * Clerk's middleware unconditionally sets
 *
 *   cache-control: private, no-cache, no-store, max-age=0
 *
 * on every response, which means Vercel's CDN can never cache any page.
 * Every visitor gets a cold serverless invocation even on fully static pages.
 *
 * Moving auth state to a client component via useAuth() breaks that coupling:
 *
 *  • The server component (layout.tsx) renders the same HTML for every user.
 *  • Vercel can cache that HTML on its CDN edge and serve it in <20 ms.
 *  • Once React hydrates, useAuth() reads the Clerk session cookie and swaps
 *    in the right controls (Sign in / Get started  vs  Workspace / avatar).
 *
 * There is a brief moment (~100 ms) after hydration where the auth state is
 * "loading" – during that time we show nothing to avoid a flash of incorrect
 * content.  This is the standard pattern used by every Clerk example that
 * needs static/CDN-cached public pages.
 */

import {
  SignInButton,
  SignUpButton,
  UserButton,
  useAuth,
} from "@clerk/nextjs";
import Link from "next/link";

const HAS_CLERK_KEY = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);

function ClerkHeaderAuth() {
  const { isSignedIn, isLoaded } = useAuth();

  // Nothing until Clerk has read the session cookie – avoids a flash
  // of the signed-out buttons for a user who is already signed in.
  if (!isLoaded) return null;

  if (isSignedIn) {
    return (
      <div className="flex items-center gap-2 md:gap-3">
        <Link
          href="/pricing"
          className="hidden lg:inline-flex items-center gap-1 rounded-full border border-accent/40 bg-accent/10 px-2.5 py-1 text-[12.5px] font-semibold text-accent transition-colors hover:bg-accent/20"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
          Upgrade to Pro
        </Link>
        <Link
          href="/projects"
          className="hidden sm:inline-block shrink-0 whitespace-nowrap rounded-lg border border-line bg-surface px-3 py-1.5 text-[13.5px] font-medium text-ink transition-colors hover:bg-sunk md:text-[14px]"
        >
          Projects
        </Link>
        <Link
          href="/dashboard"
          className="shrink-0 whitespace-nowrap rounded-lg bg-accent px-3 py-1.5 text-[13.5px] font-medium text-canvas transition-opacity hover:opacity-90 md:px-3.5 md:py-2 md:text-[14.5px]"
        >
          Workspace
        </Link>
        <UserButton />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 md:gap-3">
      <Link
        href="/pricing"
        className="hidden md:inline-block whitespace-nowrap text-sm font-semibold text-accent transition-colors hover:opacity-85"
      >
        Pricing
      </Link>
      <SignInButton>
        <button className="whitespace-nowrap text-sm text-ink-2 transition-colors hover:text-ink">
          Sign in
        </button>
      </SignInButton>
      {/* Below `sm` there is no room for both next to the logo, the menu and
          the theme toggle: "Sign in" wrapped onto two lines and this button
          ran off the right edge. Sign-in links to sign-up, so it alone stays. */}
      <SignUpButton>
        <button className="hidden shrink-0 whitespace-nowrap sm:inline-block rounded-lg bg-accent px-3 py-1.5 text-[14px] font-medium text-canvas transition-opacity hover:opacity-90 md:px-4 md:py-2 md:text-[15.5px]">
          Get started
        </button>
      </SignUpButton>
    </div>
  );
}

export function HeaderAuth() {
  if (!HAS_CLERK_KEY) return null;
  return <ClerkHeaderAuth />;
}
