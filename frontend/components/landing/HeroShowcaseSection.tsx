"use client";

import { useCallback, useEffect, useState } from "react";
import { HeroShowcase, type ShowcaseData } from "@/components/landing/HeroShowcase";
import { DEFAULT_SHOWCASE_DATA } from "@/lib/defaultLandingData";

export function HeroShowcaseSection() {
  const [data, setData] = useState<ShowcaseData>(DEFAULT_SHOWCASE_DATA);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;

    fetch("/api/landing/showcase")
      .then((res) => {
        if (!res.ok) throw new Error(`showcase ${res.status}`);
        return res.json() as Promise<ShowcaseData>;
      })
      .then((showcase) => {
        if (live && showcase && showcase.chart?.clouds?.length) {
          setData(showcase);
        }
      })
      .catch(() => {
        // Keep the default showcase data in place seamlessly
      });

    return () => {
      live = false;
    };
  }, [attempt]);

  return <HeroShowcase data={data} />;
}
