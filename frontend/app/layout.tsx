import { ClerkProvider, Show, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
import type { Metadata } from "next";
import Link from "next/link";
import { IBM_Plex_Mono, Inter } from "next/font/google";
import { Wordmark } from "@/components/Logo";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "WhichCloud: know what it costs before you build it",
  description:
    "Describe your app in a sentence. Get three priced architectures across AWS, " +
    "Azure and Google, with the optimizations that lower the bill.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col bg-canvas text-ink">
        <ClerkProvider>
          <header className="sticky top-0 z-30 flex h-16 items-center gap-8 border-b border-line bg-canvas/85 px-6 backdrop-blur">
            <Link href="/" aria-label="WhichCloud home">
              <Wordmark />
            </Link>

            <nav className="hidden gap-7 text-[15.5px] text-ink-2 md:flex">
              <Link href="/prices" className="transition-colors hover:text-ink">
                Price index
              </Link>
              <Link href="/estimate" className="transition-colors hover:text-ink">
                Architecture
              </Link>
              <Link href="/techniques" className="transition-colors hover:text-ink">
                Optimizations
              </Link>
              <Link href="/docs" className="transition-colors hover:text-ink">
                Docs
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
                <UserButton />
              </Show>
            </div>
          </header>

          <main className="flex-1">{children}</main>

        </ClerkProvider>
      </body>
    </html>
  );
}
