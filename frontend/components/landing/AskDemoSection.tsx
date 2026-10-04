"use client";

import { useEffect, useState } from "react";
import { AskDemo, type Scenario } from "@/components/landing/AskDemo";
import { DEFAULT_DEMO_SCENARIOS } from "@/lib/defaultLandingData";

export function AskDemoSection() {
  const [scenarios, setScenarios] = useState<Scenario[]>(DEFAULT_DEMO_SCENARIOS);

  useEffect(() => {
    let live = true;

    fetch("/api/landing/demos")
      .then((res) => {
        if (!res.ok) throw new Error(`demos ${res.status}`);
        return res.json() as Promise<{ scenarios: Scenario[] }>;
      })
      .then((body) => {
        if (live && body.scenarios?.length) setScenarios(body.scenarios);
      })
      .catch(() => {
        // Keeps the default scenarios seamlessly
      });

    return () => {
      live = false;
    };
  }, []);

  return <AskDemo scenarios={scenarios} />;
}
