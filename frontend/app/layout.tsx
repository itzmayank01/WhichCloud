import { ClerkProvider, Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import { ThemeToggle } from "@/components/ThemeToggle";
import { MobileNav } from "@/components/MobileNav";
import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { Wordmark, TerraformLogo } from "@/components/Logo";
import "./globals.css";

/* Geist and Geist Mono are drawn as one system, which matters on a page that
   sets prose and figures side by side constantly: the mono lines up with the
   sans at the same optical size instead of sitting slightly heavier and
   wider, the way a borrowed mono usually does. Both carry proper tabular
   figures, which is what keeps a column of prices from shuffling. */
const sans = Geist({
  variable: "--font-sans-family",
  subsets: ["latin"],
  display: "swap",
});
/* No weight list. Both of these are variable fonts, so they carry their whole
   weight range in one file; asking for static instances made the loader look
   for cuts Google does not serve for Geist Mono, and the dev server failed to
   resolve the font module at all. */
const mono = Geist_Mono({
  variable: "--font-mono-family",
  subsets: ["latin"],
  display: "swap",
});

const TITLE = "WhichCloud: know what it costs before you build it";
const DESCRIPTION =
  "Describe your app in a sentence. Get three priced architectures across AWS, " +
  "Azure and Google, with the optimizations that lower the bill.";

export const metadata: Metadata = {
  /* Without metadataBase, Next resolves social image URLs against nothing and
     warns at build; with it, relative URLs below become absolute. */
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000",
  ),
  title: TITLE,
  description: DESCRIPTION,
  applicationName: "WhichCloud",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    siteName: "WhichCloud",
    title: TITLE,
    description: DESCRIPTION,
    url: "/",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
  },
  robots: { index: true, follow: true },
};

export const viewport = {
  /* Both, or the browser's own chrome stays light behind a dark page -- the
     address bar on mobile and the scrollbars everywhere. `colorScheme` is
     what tells the engine to render form controls and scrollbars to match;
     pinned to "light" it undid the palette on the two widgets CSS does not
     own. */
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfbfc" },
    { media: "(prefers-color-scheme: dark)", color: "#12151a" },
  ],
  colorScheme: "light dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${mono.variable} h-full antialiased`}
      // Browser extensions write their own attributes onto <html> before
      // React hydrates -- password managers, analytics, ad blockers. The one
      // that surfaced here was data-qb-installed. React compares the server
      // HTML against the live DOM, finds an attribute it did not render, and
      // reports a hydration mismatch that no application change can fix,
      // because the markup React produced was correct. Suppressing on this
      // element only covers attributes on <html> itself; mismatches anywhere
      // inside the app still report normally.
      suppressHydrationWarning
    >
      <head>
        {/* Applied BEFORE first paint, which is the whole reason this is an
            inline script rather than an effect. React mounts after the
            browser has already painted, so a stored dark choice would show a
            white page first and then snap -- the flash every theme switcher
            has to solve, and the reason the attribute is stamped here rather
            than in the component that owns it.

            "system" stores nothing to stamp: removing the attribute is what
            hands the decision back to prefers-color-scheme. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var c=localStorage.getItem("whichcloud.theme");if(c==="dark"||c==="light"){document.documentElement.setAttribute("data-theme",c);document.documentElement.classList.add(c)}else if(window.matchMedia("(prefers-color-scheme: dark)").matches){document.documentElement.classList.add("dark")}}catch(e){}})()`,
          }}
        />
      </head>
      <body className="flex min-h-full flex-col bg-canvas text-ink">
        {/* First thing in the tab order, invisible until focused: lets a
            keyboard user past the header without walking the whole nav. */}
        <a
          href="#content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-[15px] focus:font-medium focus:text-white"
        >
          Skip to content
        </a>
        {/* Signing in lands in the workspace, not back on the landing page.
            Someone who has just authenticated came here to price something;
            returning them to the marketing argument makes them navigate to
            the product they already chose.

            Fallback, not force: a visitor sent to sign-in from a deep link
            still returns to the page they were trying to reach. Force would
            discard that and send everyone to the workspace regardless.

            Set here as well as in .env.local because that file is gitignored
            -- it holds the secret key -- so an env-only setting silently
            reverts to the landing page on any other machine. */}
        <ClerkProvider
          signInFallbackRedirectUrl="/dashboard"
          signUpFallbackRedirectUrl="/dashboard"
        >
          <header className="sticky top-0 z-40 flex h-16 items-center gap-8 border-b border-line bg-canvas/85 px-6 backdrop-blur">
            <Link href="/" aria-label="WhichCloud home">
              <Wordmark />
            </Link>

            {/* Price index is a real page again. The other two still address
                sections of the landing page, and become routes when those
                pages exist. */}
            <nav
              aria-label="Main"
              className="hidden gap-7 text-[15.5px] text-ink-2 md:flex"
            >
              <Link
                href="/prices"
                className="rounded-sm transition-colors hover:text-ink"
              >
                Price index
              </Link>
              <Link
                href="/estimate"
                className="rounded-sm transition-colors hover:text-ink"
              >
                Price your app
              </Link>
              <Link
                href="/connect"
                className="rounded-sm transition-colors hover:text-ink"
              >
                Connect
              </Link>
              <Link
                href="/finops"
                className="flex items-center gap-1.5 rounded-sm font-medium text-accent transition-colors hover:opacity-80"
              >
                <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
                FinOps Live
              </Link>
              <Link
                href="/terraform"
                className="flex items-center gap-1.5 rounded-sm font-medium text-ink-2 transition-colors hover:text-ink"
              >
                <TerraformLogo className="h-4 w-4" />
                Terraform IaC
              </Link>
              <Link
                href="/#architecture"
                className="rounded-sm transition-colors hover:text-ink"
              >
                Architecture
              </Link>
              <Link
                href="/#optimizations"
                className="rounded-sm transition-colors hover:text-ink"
              >
                Optimizations
              </Link>
            </nav>

            <div className="ml-auto flex items-center gap-4">
              <MobileNav />
              {/* Before the account controls, matching where every docs site
                  and editor puts it: theme is a property of the reader, not
                  of the session, and it has to be reachable signed out. */}
              <ThemeToggle />
              <Show when="signed-out">
                <SignInButton>
                  <button className="text-sm text-ink-2 transition-colors hover:text-ink">
                    Sign in
                  </button>
                </SignInButton>
                <SignUpButton>
                  <button className="rounded-lg bg-accent px-4 py-2 text-[15.5px] font-medium text-white transition-opacity hover:opacity-90">
                    Get started
                  </button>
                </SignUpButton>
              </Show>
              <Show when="signed-in">
                <Link
                  href="/dashboard"
                  className="rounded-lg bg-accent px-4 py-2 text-[15.5px] font-medium text-white transition-opacity hover:opacity-90"
                >
                  Workspace
                </Link>
                <UserButton />
              </Show>
            </div>
          </header>

          <main id="content" className="flex-1">
            {children}
          </main>

        </ClerkProvider>
      </body>
    </html>
  );
}
