"use client";

import React, { useRef, useState, useCallback, type ReactNode, type MouseEvent } from "react";

/*
 * Interactive card tilt + click-to-front.
 * Uses translateZ(0) + backface-visibility to force GPU compositing
 * so text stays crisp — no sub-pixel blur from perspective transforms.
 */

function TiltCard({
  children,
  index,
  active,
  onActivate,
}: {
  children: ReactNode;
  index: number;
  active: number | null;
  onActivate: (i: number | null) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState({ rx: 0, ry: 0, gx: 50, gy: 50, hovering: false });

  const handleMove = useCallback((e: MouseEvent) => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const nx = (e.clientX - r.left) / r.width;   // 0‥1
    const ny = (e.clientY - r.top) / r.height;
    setStyle({
      rx: (ny - 0.5) * -3,   // max ±1.5° — very subtle, no blur
      ry: (nx - 0.5) * 3,
      gx: nx * 100,
      gy: ny * 100,
      hovering: true,
    });
  }, []);

  const handleLeave = useCallback(() => {
    setStyle((s) => ({ ...s, rx: 0, ry: 0, hovering: false }));
  }, []);

  const isActive = active === index;
  const isDimmed = active !== null && !isActive;

  return (
    <div
      ref={ref}
      onMouseMove={handleMove}
      onMouseLeave={handleLeave}
      onClick={() => onActivate(isActive ? null : index)}
      role="button"
      tabIndex={0}
      className="relative outline-none"
      style={{
        cursor: "pointer",
        zIndex: isActive ? 20 : 1,
        transition: "transform 0.35s cubic-bezier(.22,.68,0,1), opacity 0.3s ease, filter 0.3s ease",
        transform: isActive ? "scale(1.025)" : isDimmed ? "scale(0.98)" : "scale(1)",
        opacity: isDimmed ? 0.45 : 1,
        filter: isDimmed ? "saturate(0.6) brightness(0.97)" : "none",
      }}
    >
      <div
        className="relative h-full"
        style={{
          transform: `perspective(800px) rotateX(${style.rx}deg) rotateY(${style.ry}deg) translateZ(0)`,
          transition: "transform 0.12s ease-out, box-shadow 0.3s ease",
          backfaceVisibility: "hidden",
          WebkitBackfaceVisibility: "hidden",
          willChange: "transform",
          borderRadius: 16,
          boxShadow: isActive
            ? "0 24px 48px -12px rgba(0,0,0,.18)"
            : style.hovering
              ? "0 8px 24px -4px rgba(0,0,0,.10)"
              : "0 1px 3px rgba(0,0,0,.06)",
        }}
      >
        {children}
        {/* Specular highlight — very faint */}
        {style.hovering && (
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              borderRadius: 16,
              background: `radial-gradient(ellipse at ${style.gx}% ${style.gy}%, rgba(255,255,255,0.04), transparent 55%)`,
            }}
          />
        )}
      </div>
    </div>
  );
}

export function ShowcaseGrid({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<number | null>(null);
  const items = React.Children.toArray(children);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {items.map((child, i) => (
        <TiltCard key={i} index={i} active={active} onActivate={setActive}>
          {child}
        </TiltCard>
      ))}
    </div>
  );
}
