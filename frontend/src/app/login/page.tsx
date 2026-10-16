"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getKeycloakInstance } from "../../lib/keycloak";
import { PublicHeader } from "../../components/public-header";
import Link from "next/link";
import { Suspense } from "react";

function safeRedirectPath(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\") || value === "/") {
    return "/operations";
  }
  return value;
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectParam = safeRedirectPath(searchParams.get("redirect"));
  const errorParam = searchParams.get("error");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (errorParam === "session_expired") {
      setErrorMsg("Your session has expired. Please sign in again.");
    } else if (errorParam) {
      setErrorMsg(decodeURIComponent(errorParam));
    }
  }, [errorParam]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password) {
      setErrorMsg("Please enter both email and password.");
      return;
    }

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        const errDetail =
          typeof data.error === "string"
            ? data.error
            : typeof data.error === "object" && data.error !== null
            ? JSON.stringify(data.error)
            : "Invalid email or password.";
        throw new Error(errDetail);
      }

      // Redirect directly to destination or operations platform
      router.push(redirectParam);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Invalid email or password.";
      setErrorMsg(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeycloakLogin = () => {
    setIsSubmitting(true);
    try {
      const kc = getKeycloakInstance();
      if (kc && typeof kc.login === "function") {
        kc.login({ redirectUri: window.location.origin });
        return;
      }
    } catch (e) {
      console.warn("Client-side Keycloak instance not ready, using server redirect fallback:", e);
    }
    window.location.href = `/api/auth/login?redirect=${encodeURIComponent(redirectParam)}`;
  };

  const handleOneClickDemo = async () => {
    setIsSubmitting(true);
    setErrorMsg(null);
    try {
      const res = await fetch("/api/auth/demo", { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Unable to start demo mode.");
      }
      router.push("/operations");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to start demo mode.";
      setErrorMsg(msg);
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <PublicHeader />
      <div
        style={{
          minHeight: "calc(100vh - 73px)",
          background: "radial-gradient(ellipse at top, #102a20 0%, #0a0f1d 70%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "24px 20px",
          fontFamily: "'Manrope', sans-serif",
          color: "#f8fafc",
        }}
      >
        <div
          style={{
            background: "#0f172a",
            border: "1px solid rgba(255, 255, 255, 0.1)",
            borderRadius: "16px",
            width: "100%",
            maxWidth: "440px",
            padding: "36px",
            boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 40px rgba(16, 185, 129, 0.1)",
          }}
        >
          <div style={{ textAlign: "center", marginBottom: "28px" }}>
        <div
          style={{
            width: "48px",
            height: "48px",
            background: "linear-gradient(135deg, #10b981 0%, #047857 100%)",
            borderRadius: "12px",
            color: "#ffffff",
            fontWeight: "800",
            fontSize: "18px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            margin: "0 auto 12px",
            boxShadow: "0 0 20px rgba(16, 185, 129, 0.4)",
          }}
        >
          AO
        </div>
        <h1 style={{ margin: "0 0 6px 0", fontSize: "24px", fontWeight: "800", letterSpacing: "-0.03em" }}>
          AgentOps Sign In
        </h1>
        <p style={{ margin: 0, fontSize: "13px", color: "#94a3b8" }}>
          Enterprise Autonomous Operations Control Plane
        </p>
      </div>

      {errorMsg && (
        <div
          style={{
            padding: "12px 14px",
            background: "rgba(239, 68, 68, 0.15)",
            border: "1px solid #ef4444",
            borderRadius: "8px",
            color: "#fca5a5",
            fontSize: "13px",
            marginBottom: "20px",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span>⚠️</span>
          <span>{errorMsg}</span>
        </div>
      )}

      <form onSubmit={handleLogin} style={{ display: "grid", gap: "16px" }}>
        <div>
          <label
            style={{
              display: "block",
              fontSize: "11px",
              fontWeight: "700",
              fontFamily: "'DM Mono', monospace",
              color: "#cbd5e1",
              marginBottom: "6px",
              textTransform: "uppercase",
            }}
          >
            Work Email
          </label>
          <input
            type="email"
            id="login-email-input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="name@enterprise.com"
            required
            style={{
              width: "100%",
              padding: "10px 12px",
              borderRadius: "8px",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              background: "rgba(255, 255, 255, 0.05)",
              color: "#ffffff",
              fontSize: "13px",
              outline: "none",
            }}
          />
        </div>

        <div>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
            <label
              style={{
                fontSize: "11px",
                fontWeight: "700",
                fontFamily: "'DM Mono', monospace",
                color: "#cbd5e1",
                textTransform: "uppercase",
              }}
            >
              Password
            </label>
            <Link href="/forgot-password" style={{ fontSize: "11px", color: "#34d399", textDecoration: "none" }}>
              Forgot password?
            </Link>
          </div>
          <input
            type="password"
            id="login-password-input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter your password"
            required
            style={{
              width: "100%",
              padding: "10px 12px",
              borderRadius: "8px",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              background: "rgba(255, 255, 255, 0.05)",
              color: "#ffffff",
              fontSize: "13px",
              outline: "none",
            }}
          />
        </div>

        <button
          type="submit"
          id="login-submit-btn"
          disabled={isSubmitting}
          style={{
            marginTop: "6px",
            padding: "12px",
            background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
            color: "#ffffff",
            border: "none",
            borderRadius: "8px",
            fontWeight: "700",
            fontSize: "14px",
            cursor: isSubmitting ? "wait" : "pointer",
            boxShadow: "0 4px 14px rgba(16, 185, 129, 0.35)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
          }}
        >
          {isSubmitting ? <span>Authenticating...</span> : <span>Sign In to AgentOps</span>}
        </button>
      </form>

      <div style={{ display: "flex", alignItems: "center", margin: "20px 0" }}>
        <div style={{ flex: 1, height: "1px", background: "rgba(255, 255, 255, 0.1)" }} />
        <span style={{ padding: "0 10px", fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>
          or choose method
        </span>
        <div style={{ flex: 1, height: "1px", background: "rgba(255, 255, 255, 0.1)" }} />
      </div>

      <div style={{ display: "grid", gap: "10px" }}>
        <button
          type="button"
          id="keycloak-login-btn"
          onClick={handleKeycloakLogin}
          disabled={isSubmitting}
          style={{
            background: "rgba(255, 255, 255, 0.06)",
            color: "#e2e8f0",
            border: "1px solid rgba(255, 255, 255, 0.15)",
            borderRadius: "8px",
            padding: "10px",
            fontWeight: "600",
            fontSize: "12px",
            cursor: isSubmitting ? "wait" : "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
          }}
        >
          <span>🔐</span>
          <span>Log in with Keycloak (OIDC + PKCE)</span>
        </button>

        <button
          type="button"
          id="demo-quick-login-btn"
          onClick={handleOneClickDemo}
          disabled={isSubmitting}
          style={{
            background: "rgba(16, 185, 129, 0.1)",
            color: "#34d399",
            border: "1px solid rgba(16, 185, 129, 0.3)",
            borderRadius: "8px",
            padding: "10px",
            fontWeight: "600",
            fontSize: "12px",
            cursor: isSubmitting ? "wait" : "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
          }}
        >
          <span>⚡</span>
          <span>Explore Demo as Alex Rivera (Read-Only)</span>
        </button>
      </div>

      <div style={{ textAlign: "center", fontSize: "13px", color: "#94a3b8", marginTop: "24px" }}>
        Don&apos;t have an account?{" "}
        <Link href="/signup" style={{ color: "#34d399", fontWeight: "700", textDecoration: "none" }}>
          Sign Up Free
        </Link>
      </div>

      <p style={{ textAlign: "center", fontSize: "10px", color: "#64748b", marginTop: "20px", fontFamily: "'DM Mono', monospace" }}>
        Strict Server-Side Identity Verification & RFC 7636 PKCE
      </p>
        </div>
      </div>
    </>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<div style={{ color: "#94a3b8" }}>Loading...</div>}>
      <LoginForm />
    </Suspense>
  );
}
