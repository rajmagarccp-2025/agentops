"use client";

import { useEffect, useRef, useState } from "react";
import HomePage from "../home/page";
import { useWorkspace } from "../../state/workspace-context";

export default function DemoPage() {
  const { refreshWorkspace } = useWorkspace();
  const refreshWorkspaceRef = useRef(refreshWorkspace);
  const [attempt, setAttempt] = useState(0);
  const [sessionReady, setSessionReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  refreshWorkspaceRef.current = refreshWorkspace;

  useEffect(() => {
    let active = true;

    async function initDemoSession() {
      setSessionReady(false);
      setError(null);

      try {
        const response = await fetch("/api/auth/demo", { method: "POST", cache: "no-store" });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          throw new Error(data.error || "Unable to start the sample console.");
        }

        await refreshWorkspaceRef.current();
        if (active) setSessionReady(true);
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Unable to start the sample console.");
        }
      }
    }

    void initDemoSession();

    return () => {
      active = false;
    };
  }, [attempt]);

  if (error) {
    return (
      <main className="demo-start-error" role="alert">
        <h1>Sample console unavailable</h1>
        <p>{error}</p>
        <button type="button" onClick={() => setAttempt((current) => current + 1)}>
          Retry
        </button>
      </main>
    );
  }

  if (!sessionReady) {
    return (
      <main className="demo-start-loading" role="status" aria-live="polite">
        <span className="demo-start-spinner" aria-hidden="true" />
        <p>Starting the read-only sample console…</p>
      </main>
    );
  }

  return <HomePage />;
}
