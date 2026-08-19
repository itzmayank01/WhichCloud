"use client";

import { useSyncExternalStore } from "react";

/**
 * Whether the reader has asked for reduced motion.
 *
 * Read during render rather than in an effect. Every animated panel on the
 * landing page used to check the media query inside its effect and then set
 * state to the finished frame, which React flags: setting state
 * synchronously in an effect renders once with the wrong content and again
 * with the right one, and on a slow device the empty frame is visible.
 *
 * useSyncExternalStore is what this is for. The server snapshot is false --
 * markup cannot know the preference -- and the client subscribes to the
 * query, so a reader toggling the setting sees panels stop moving without
 * a reload.
 */

const QUERY = "(prefers-reduced-motion: reduce)";

function subscribe(onChange: () => void): () => void {
  if (typeof window === "undefined" || !window.matchMedia) return () => {};
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

function getSnapshot(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia(QUERY).matches;
}

/** The server has no preference to report, so it always animates. */
function getServerSnapshot(): boolean {
  return false;
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
