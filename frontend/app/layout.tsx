import { ClerkProvider, Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { Wordmark } from "@/components/Logo";
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
  themeColor: "#fbfbfc",
  colorScheme: "light",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${mono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-canvas text-ink">
        {/* First thing in the tab order, invisible until focused: lets a
            keyboard user past the header without walking the whole nav. */}
        <a
          href="#content"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-4 focus:py-2 focus:text-[15px] focus:font-medium focus:text-white"
        >
          Skip to content
        </a>
        <ClerkProvider>
          <header className="sticky top-0 z-30 flex h-16 items-center gap-8 border-b border-line bg-canvas/85 px-6 backdrop-blur">
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
              <Link
                href="/#provenance"
                className="rounded-sm transition-colors hover:text-ink"
              >
                Provenance
              </Link>
              <Link
                href="/estimate"
                className="rounded-sm transition-colors hover:text-ink"
              >
                Price your app
              </Link>
            </nav>

            <div className="ml-auto flex items-center gap-4">
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
