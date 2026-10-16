"use client";

import { useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");
    const errorDesc = searchParams.get("error_description");

    if (error) {
      router.push(`/login?error=${encodeURIComponent(errorDesc || error)}`);
      return;
    }

    if (code) {
      // Delegate to BFF callback route handler
      const callbackUrl = `/api/auth/callback?code=${encodeURIComponent(code)}${state ? `&state=${encodeURIComponent(state)}` : ""}`;
      window.location.href = callbackUrl;
    } else {
      router.push("/home");
    }
  }, [searchParams, router]);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "radial-gradient(ellipse at top, #102a20 0%, #0a0f1d 70%)",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        color: "#f8fafc",
        fontFamily: "'Manrope', sans-serif",
      }}
    >
      <div style={{ fontSize: "24px", fontWeight: "800", marginBottom: "12px", color: "#34d399" }}>
        Authenticating with Keycloak...
      </div>
      <p style={{ color: "#94a3b8", fontSize: "14px" }}>
        Verifying OAuth 2.0 PKCE proof and mapping local user identity...
      </p>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={<div style={{ color: "#94a3b8" }}>Loading SSO Session...</div>}>
      <CallbackHandler />
    </Suspense>
  );
}
