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
      <body className="min-h-full flex flex-col bg-zinc-50 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
        <ClerkProvider>
          <header className="sticky top-0 z-30 flex h-16 items-center gap-8 border-b border-zinc-200 bg-zinc-50/80 px-6 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80">
            <Link href="/" aria-label="WhichCloud home">
              <Wordmark />
            </Link>

            <nav className="hidden gap-6 text-sm text-zinc-600 sm:flex dark:text-zinc-400">
              <Link href="/prices" className="hover:text-zinc-900 dark:hover:text-zinc-100">
                Prices
              </Link>
              <Link href="/techniques" className="hover:text-zinc-900 dark:hover:text-zinc-100">
                Techniques
              </Link>
            </nav>

            <div className="ml-auto flex items-center gap-3">
              <Show when="signed-out">
                <SignInButton>
                  <button className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">
                    Sign in
                  </button>
                </SignInButton>
                <SignUpButton>
                  <button className="rounded-md bg-zinc-900 px-3.5 py-1.5 text-sm font-medium text-zinc-50 hover:bg-zinc-800 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200">
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
        </ClerkProvider>
      </body>
    </html>
  );
}
