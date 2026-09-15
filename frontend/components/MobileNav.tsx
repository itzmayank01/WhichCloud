"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { TerraformLogo } from "@/components/Logo";

/** Same links as the desktop <nav> in layout.tsx, which is `hidden md:flex`
 *  -- below that breakpoint the primary navigation had no way to reach a
 *  reader at all, not even a button to open one. This is that button. */
const LINKS = [
  { href: "/prices", label: "Price index" },
  { href: "/estimate", label: "Price your app" },
  { href: "/connect", label: "Connect" },
  { href: "/finops", label: "FinOps Live", accent: true },
  { href: "/terraform", label: "Terraform IaC", terraform: true },
  { href: "/#architecture", label: "Architecture" },
  { href: "/#optimizations", label: "Optimizations" },
];

export function MobileNav() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // A route change means a link was just followed -- close behind it,
  // otherwise the panel is still open over whatever page it navigated to.
  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  return (
    <div className="md:hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? "Close menu" : "Open menu"}
        aria-expanded={open}
        className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 transition-colors hover:bg-sunk hover:text-ink"
      >
        {open ? (
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        ) : (
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        )}
      </button>

      {open && (
        <nav
          aria-label="Main"
          className="fixed inset-x-0 top-16 z-30 flex flex-col gap-1 border-b border-line bg-canvas px-4 py-3 text-[15.5px] shadow-lg"
        >
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`flex items-center gap-1.5 rounded-lg px-2 py-2.5 transition-colors hover:bg-sunk ${
                l.accent ? "font-medium text-accent" : "text-ink-2 hover:text-ink"
              }`}
            >
              {l.accent && <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />}
              {l.terraform && <TerraformLogo className="h-4 w-4" />}
              {l.label}
            </Link>
          ))}
        </nav>
      )}
    </div>
  );
}
