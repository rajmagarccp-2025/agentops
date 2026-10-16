"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function DashboardPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/home");
  }, [router]);

  return (
    <div style={{ minHeight: "100vh", background: "#0a0f1d", color: "#94a3b8", display: "flex", alignItems: "center", justifyContent: "center" }}>
      Loading Dashboard...
    </div>
  );
}
