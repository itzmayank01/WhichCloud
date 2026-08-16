"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Plays a staggered reveal on the children the first time they are scrolled
 * to, and never again.
 *
 * The animation exists to show these panels assembling rather than arriving
 * finished, so it has to start when the reader is looking at them. Running it
 * on mount would mean it had already finished by the time anyone scrolled
 * down.
 *
 * The timeout is the part that matters. Everything inside starts at zero
 * opacity, so if the observer never fires -- no IntersectionObserver, a
 * browser that throttles it, an environment that stubs it -- the content
 * would be permanently invisible. A missed animation is a cosmetic loss; a
 * blank panel is a broken page, so the reveal happens on a timer regardless
 * and the observer only ever makes it happen sooner.
 */
export function Reveal({
  children,
  className = "",
  style,
}: {
  children: React.ReactNode;
  className?: string;
  /* Carries the --i stagger index when a Reveal is one of a row, so a grid
     can deal its cards in rather than snapping in as a block. */
  style?: React.CSSProperties;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const fallback = window.setTimeout(() => setShown(true), 1500);
    const reveal = () => {
      window.clearTimeout(fallback);
      setShown(true);
    };

    if (typeof IntersectionObserver === "undefined") {
      reveal();
      return () => window.clearTimeout(fallback);
    }

    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          reveal();
          io.disconnect();
        }
      },
      { threshold: 0.2 },
    );
    io.observe(el);

    return () => {
      io.disconnect();
      window.clearTimeout(fallback);
    };
  }, []);

  return (
    <div ref={ref} data-revealed={shown} className={className} style={style}>
      {children}
    </div>
  );
}
