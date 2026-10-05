"use client";

import { useEffect } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8010";
const KEY = "wc:warmed-at";
const EVERY_MS = 5 * 60 * 1000;

/**
 * Wakes the engine the moment anyone opens any page.
 *
 * The engine runs on a free plan that sleeps when idle and takes 30-60s to
 * boot. Without this, the first request that needed it -- connecting an AWS
 * account, pricing an app -- paid that whole wait at the moment the visitor
 * was looking at a spinner. Firing a /health request on arrival starts the
 * boot while they are still reading, so by the time they act it is usually
 * up. Fire-and-forget: nothing renders from it and a failure changes nothing.
 * At most once per tab every five minutes.
 */
export function BackendWarmup() {
  useEffect(() => {
    try {
      const last = Number(sessionStorage.getItem(KEY) || 0);
      if (Date.now() - last < EVERY_MS) return;
      sessionStorage.setItem(KEY, String(Date.now()));
    } catch {
      // storage blocked -- warm anyway
    }
    fetch(`${BASE}/health`, { cache: "no-store", keepalive: true }).catch(() => {});
  }, []);
  return null;
}
