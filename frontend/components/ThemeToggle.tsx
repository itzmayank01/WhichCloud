"use client";

import { useEffect, useRef, useState } from "react";

/**
 * System / Light / Dark.
 *
 * Three states rather than a two-way switch, because "follow my machine" is a
 * real answer and the commonest one. A binary toggle forces a reader who has
 * already told their OS what they want to say it again, and then stops
 * tracking it when they change their mind at sunset.
 *
 * The choice is stored as an attribute on <html> rather than a class, so CSS
 * can express all three states: an explicit choice stamps data-theme, and the
 * system setting stamps nothing at all, leaving prefers-color-scheme to
 * decide. See globals.css.
 */

type Choice = "system" | "light" | "dark";

const KEY = "whichcloud.theme";

const OPTIONS: { id: Choice; label: string; icon: React.ReactNode }[] = [
  {
    id: "system",
    label: "System",
    icon: (
      <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
        <rect x="2" y="3" width="12" height="8" rx="1.2" />
        <path d="M6 13.5h4" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "light",
    label: "Light",
    icon: (
      <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
        <circle cx="8" cy="8" r="3.1" />
        <path d="M8 1.4v1.6M8 13v1.6M14.6 8H13M3 8H1.4M12.7 3.3l-1.1 1.1M4.4 11.6l-1.1 1.1M12.7 12.7l-1.1-1.1M4.4 4.4L3.3 3.3" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "dark",
    label: "Dark",
    icon: (
      <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.4" aria-hidden>
        <path d="M13.2 9.6A5.6 5.6 0 016.4 2.8a5.6 5.6 0 106.8 6.8z" strokeLinejoin="round" />
      </svg>
    ),
  },
];

/** Stamp the root. "system" removes the attribute rather than setting one,
 *  which is what hands the decision back to prefers-color-scheme. */
function apply(choice: Choice) {
  const root = document.documentElement;
  if (choice === "system") {
    root.removeAttribute("data-theme");
    root.classList.remove("dark", "light");
    if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
      root.classList.add("dark");
    } else {
      root.classList.add("light");
    }
  } else {
    root.setAttribute("data-theme", choice);
    root.classList.remove("dark", "light");
    root.classList.add(choice);
  }
}

export function ThemeToggle() {
  const [choice, setChoice] = useState<Choice>("system");
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  // Read once on mount. The inline script in layout.tsx has already applied
  // the stored choice by now -- this only syncs the control's own state, so
  // the menu shows a tick against what is actually in force.
  useEffect(() => {
    const stored = window.localStorage.getItem(KEY) as Choice | null;
    if (stored === "light" || stored === "dark" || stored === "system") {
      setChoice(stored);
    }
  }, []);

  // Close on outside click and on Escape, both bound on the document: a menu
  // that only closes via its own button is a menu people leave open.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function pick(next: Choice) {
    setChoice(next);
    setOpen(false);
    apply(next);
    try {
      window.localStorage.setItem(KEY, next);
    } catch {
      // Private browsing, or storage disabled. The theme still applies for
      // this page; only remembering it is lost.
    }
  }

  const current = OPTIONS.find((o) => o.id === choice) ?? OPTIONS[0];

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Theme: ${current.label}`}
        title={`Theme: ${current.label}`}
        className="grid h-9 w-9 place-items-center rounded-lg text-ink-2 transition-colors hover:bg-sunk hover:text-ink"
      >
        {current.icon}
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-[80] mt-1.5 w-36 overflow-hidden rounded-xl border border-line bg-surface p-1 shadow-xl backdrop-blur-sm"
        >
          {OPTIONS.map((option) => (
            <button
              key={option.id}
              role="menuitemradio"
              aria-checked={choice === option.id}
              onClick={() => pick(option.id)}
              className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-[13px] transition-colors ${
                choice === option.id
                  ? "text-accent"
                  : "text-ink-2 hover:bg-sunk hover:text-ink"
              }`}
            >
              {option.icon}
              <span className="flex-1">{option.label}</span>
              {choice === option.id && (
                <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
                  <path d="M3.5 8.5l3 3 6-6.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
