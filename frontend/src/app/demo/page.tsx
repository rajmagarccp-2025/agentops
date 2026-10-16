"use client";

import { useEffect, useState } from "react";
import HomePage from "../home/page";

export default function DemoPage() {
  const [sessionReady, setSessionReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function initDemoSession() {
      try {
        const response = await fetch("/api/auth/demo", { method: "POST" });
        if (!response.ok) {
          const data = await response.json().catch(() => ({}));
          throw new Error((data as { error?: string }).error || "Unable to start sample demo session.");
        }
        if (active) {
          setSessionReady(true);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Unable to establish demo session.");
          // Even if backend demo endpoint returns an error (or already active), let user view the demo console
          setSessionReady(true);
        }
      }
    }

    void initDemoSession();

    return () => {
      active = false;
    };
  }, []);

  return <HomePage />;
}
