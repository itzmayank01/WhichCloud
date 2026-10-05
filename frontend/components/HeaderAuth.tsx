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

export function HeaderAuth() {
  const { isSignedIn, isLoaded } = useAuth();

  // Nothing until Clerk has read the session cookie – avoids a flash
  // of the signed-out buttons for a user who is already signed in.
  if (!isLoaded) return null;

  if (isSignedIn) {
    return (
      <>
        <Link
          href="/dashboard"
          className="shrink-0 whitespace-nowrap rounded-lg bg-accent px-3 py-1.5 text-[14px] font-medium text-canvas transition-opacity hover:opacity-90 md:px-4 md:py-2 md:text-[15.5px]"
        >
          Workspace
        </Link>
        <UserButton />
      </>
    );
  }

  return (
    <>
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
    </>
  );
}
