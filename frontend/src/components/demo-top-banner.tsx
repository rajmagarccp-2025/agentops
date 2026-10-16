"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useWorkspace } from "../state/workspace-context";

export function DemoTopBanner() {
  const pathname = usePathname();
  const { user } = useWorkspace();

  // Show if user is in read-only demo mode or if pathname is /demo
  const isDemo = Boolean(user?.read_only_demo) || pathname === "/demo" || pathname.startsWith("/demo/");

  if (!isDemo) return null;

  return (
    <div
      style={{
        background: "#064e3b",
        borderBottom: "1px solid rgba(52, 211, 153, 0.3)",
        color: "#ffffff",
        padding: "8px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: "12px",
        position: "sticky",
        top: 0,
        zIndex: 1000,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
        <span
          style={{
            border: "1px solid #10b981",
            color: "#34d399",
            background: "rgba(16, 185, 129, 0.12)",
            borderRadius: "6px",
            padding: "3px 8px",
            fontSize: "10px",
            fontWeight: "700",
            fontFamily: "'DM Mono', monospace",
            letterSpacing: "0.06em",
            textTransform: "uppercase",
          }}
        >
          DEMO MODE — READ ONLY
        </span>
        <span style={{ fontSize: "12px", color: "#e2e8f0", fontWeight: "500" }}>
          You are exploring the complete AgentOps platform with realistic sample data.
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <Link
          href="/"
          style={{
            background: "rgba(255, 255, 255, 0.1)",
            border: "1px solid rgba(255, 255, 255, 0.2)",
            color: "#ffffff",
            borderRadius: "6px",
            padding: "5px 12px",
            fontSize: "12px",
            fontWeight: "600",
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            transition: "all 0.15s ease",
          }}
        >
          ← Back to Home
        </Link>
        <Link
          href="/signup"
          style={{
            background: "#6ee7b7",
            color: "#064e3b",
            border: "none",
            borderRadius: "6px",
            padding: "5px 14px",
            fontSize: "12px",
            fontWeight: "700",
            textDecoration: "none",
            display: "inline-flex",
            alignItems: "center",
            transition: "all 0.15s ease",
          }}
        >
          Create Account
        </Link>
      </div>
    </div>
  );
}
