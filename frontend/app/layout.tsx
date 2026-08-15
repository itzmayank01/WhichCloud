import { ClerkProvider, Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { Wordmark } from "@/components/Logo";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "WhichCloud — know what it costs before you build it",
  description:
    "Describe your app in a sentence. Get three priced architectures across AWS, " +
    "Azure and Google, with the optimizations that lower the bill.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-canvas text-ink">
        <ClerkProvider>
          <header className="sticky top-0 z-30 flex h-16 items-center gap-8 border-b border-line bg-canvas/85 px-6 backdrop-blur">
            <Link href="/" aria-label="WhichCloud home">
              <Wordmark />
            </Link>

            <nav className="hidden gap-6 text-sm text-ink-2 sm:flex">
              <Link href="/prices" className="transition-colors hover:text-ink">
                Prices
              </Link>
              <Link href="/techniques" className="transition-colors hover:text-ink">
                Techniques
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
                  <button className="rounded-md bg-ink px-3.5 py-1.5 text-sm font-medium text-white transition-opacity hover:opacity-88">
                    Try it
                  </button>
                </SignUpButton>
              </Show>
              <Show when="signed-in">
                <UserButton />
              </Show>
            </div>
          </header>

          <main className="flex-1">{children}</main>

          <footer className="border-t border-line px-6 py-8">
            <p className="max-w-3xl font-mono text-[11px] leading-relaxed text-ink-3">
              Prices fetched from provider APIs · sizing is heuristic ·
              estimate, not a quote
            </p>
          </footer>
        </ClerkProvider>
      </body>
    </html>
  );
}
