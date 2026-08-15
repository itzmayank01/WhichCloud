"use client";

import { useEffect, useLayoutEffect, useRef, useState } from "react";

/**
 * Counts a figure up to its value once the panel around it is revealed.
 *
 * The diff panel is showing the moment a price changes, and a number that
 * settles reads as one that was worked out. It waits on the same
 * `data-revealed` flag the surrounding Reveal sets, so the count runs with
 * the line it belongs to rather than before the reader has arrived.
 *
 * The same caution applies as there: the displayed value starts at zero, so
 * anything that stops the animation starting would leave a price reading
 * $0.00, which is far worse than an unanimated one. A timeout puts the real
 * figure in place regardless.
 */
export function CountUp({
  value,
  prefix = "",
  decimals = 2,
  delayMs = 0,
  durationMs = 850,
  className = "",
}: {
  value: number;
  prefix?: string;
  decimals?: number;
  delayMs?: number;
  durationMs?: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);

  /* Starts at the real figure, not at zero. This renders on the server, so a
     zero start ships a price of $0.00 in the HTML -- wrong for anyone
     without JavaScript, and wrong for everyone in the moment before
     hydration. The count is set back to zero in a layout effect instead,
     before the browser paints, so the animation still begins from nothing
     while the markup never carries a false number. */
  const [shown, setShown] = useState(value);

  const useIsomorphicLayoutEffect =
    typeof window !== "undefined" ? useLayoutEffect : useEffect;

  useIsomorphicLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    setShown(0);

    let raf = 0;
    let startTimer = 0;
    let observer: MutationObserver | undefined;
    let done = false;

    const animate = () => {
      const t0 = performance.now();
      const tick = (now: number) => {
        const p = Math.min(1, (now - t0) / durationMs);
        const eased = 1 - Math.pow(1 - p, 3); // ease-out cubic
        setShown(value * eased);
        if (p < 1) raf = requestAnimationFrame(tick);
        else done = true;
      };
      raf = requestAnimationFrame(tick);
    };

    const begin = () => {
      startTimer = window.setTimeout(animate, delayMs);
    };

    const host = el.closest("[data-revealed]");
    if (!host || host.getAttribute("data-revealed") === "true") {
      begin();
    } else {
      observer = new MutationObserver(() => {
        if (host.getAttribute("data-revealed") === "true") {
          observer?.disconnect();
          begin();
        }
      });
      observer.observe(host, {
        attributes: true,
        attributeFilter: ["data-revealed"],
      });
    }

    // Whatever happens above, the real figure is on screen by now.
    const guard = window.setTimeout(() => {
      if (!done) {
        cancelAnimationFrame(raf);
        setShown(value);
      }
    }, delayMs + durationMs + 1800);

    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(startTimer);
      window.clearTimeout(guard);
      observer?.disconnect();
    };
  }, [value, delayMs, durationMs]);

  return (
    <span ref={ref} className={`tnum ${className}`}>
      {prefix}${shown.toFixed(decimals)}
    </span>
  );
}
