"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { PublicHeader } from "../../components/public-header";
import { getKeycloakInstance } from "../../lib/keycloak";

export default function SignupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const calculatePasswordStrength = (pass: string) => {
    if (!pass) return { score: 0, label: "Empty", color: "#64748b" };
    let score = 0;
    if (pass.length >= 8) score += 1;
    if (/[0-9]/.test(pass)) score += 1;
    if (/[a-z]/.test(pass) && /[A-Z]/.test(pass)) score += 1;
    if (/[^A-Za-z0-9]/.test(pass)) score += 1;

    if (score <= 1) return { score: 1, label: "Weak", color: "#ef4444" };
    if (score <= 3) return { score: 2, label: "Good", color: "#f59e0b" };
    return { score: 3, label: "Strong", color: "#10b981" };
  };

  const strength = calculatePasswordStrength(password);

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    // 1. Validate required fields
    if (!fullName.trim() || !email.trim() || !password || !confirmPassword) {
      setErrorMsg("All fields are required.");
      return;
    }

    // 2. Validate email format
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.trim())) {
      setErrorMsg("Please enter a valid email address.");
      return;
    }

    // 3. Validate password length & strength
    if (password.length < 8) {
      setErrorMsg("Password must be at least 8 characters long.");
      return;
    }
    const hasDigitOrSpecial = /[0-9!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password);
    if (!hasDigitOrSpecial) {
      setErrorMsg("Password must contain at least one number or special character.");
      return;
    }

    // 4. Validate password confirmation
    if (password !== confirmPassword) {
      setErrorMsg("Passwords do not match. Please verify and re-enter.");
      return;
    }

    setIsSubmitting(true);

    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
          password,
          confirm_password: confirmPassword,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        const errDetail =
          typeof data.error === "string"
            ? data.error
            : typeof data.error === "object" && data.error !== null
            ? JSON.stringify(data.error)
            : "Unable to create account. Please try again.";
        throw new Error(errDetail);
      }

      // Signup successful! Redirect directly to operations platform
      router.push("/operations");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to create account. Please try again.";
      setErrorMsg(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleKeycloakSignup = () => {
    setIsSubmitting(true);
    try {
      const kc = getKeycloakInstance();
      if (kc && typeof kc.login === "function") {
        kc.login({ action: "register", redirectUri: window.location.origin });
        return;
      }
    } catch (e) {
      console.warn("Client-side Keycloak instance not ready, using server redirect fallback:", e);
    }
    window.location.href = "/api/auth/signup";
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
            maxWidth: "460px",
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
            Create Your AgentOps Account
          </h1>
          <p style={{ margin: 0, fontSize: "13px", color: "#94a3b8" }}>
            Start with autonomous SRE, FinOps & LLMOps control plane
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

        <form onSubmit={handleSignup} style={{ display: "grid", gap: "16px" }}>
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
              Full Name *
            </label>
            <input
              type="text"
              id="signup-name-input"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="e.g. Alex Rivera"
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
              Work Email *
            </label>
            <input
              type="email"
              id="signup-email-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alex.rivera@enterprise.com"
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
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
              <label
                style={{
                  fontSize: "11px",
                  fontWeight: "700",
                  fontFamily: "'DM Mono', monospace",
                  color: "#cbd5e1",
                  textTransform: "uppercase",
                }}
              >
                Password *
              </label>
              {password && (
                <span style={{ fontSize: "11px", color: strength.color, fontFamily: "'DM Mono', monospace" }}>
                  Strength: {strength.label}
                </span>
              )}
            </div>
            <input
              type="password"
              id="signup-password-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Minimum 8 characters (with number/symbol)"
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
              Confirm Password *
            </label>
            <input
              type="password"
              id="signup-confirm-password-input"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="Re-type your password"
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
            id="signup-submit-btn"
            disabled={isSubmitting}
            style={{
              marginTop: "8px",
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
            {isSubmitting ? (
              <span>Creating your account...</span>
            ) : (
              <>
                <span>Sign Up</span>
                <span>→</span>
              </>
            )}
          </button>
        </form>

        <div style={{ display: "flex", alignItems: "center", margin: "20px 0" }}>
          <div style={{ flex: 1, height: "1px", background: "rgba(255, 255, 255, 0.1)" }} />
          <span style={{ padding: "0 10px", fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>
            or Single Sign-On
          </span>
          <div style={{ flex: 1, height: "1px", background: "rgba(255, 255, 255, 0.1)" }} />
        </div>

        <button
          type="button"
          onClick={handleKeycloakSignup}
          id="keycloak-signup-btn"
          disabled={isSubmitting}
          style={{
            width: "100%",
            background: "rgba(255, 255, 255, 0.06)",
            color: "#e2e8f0",
            border: "1px solid rgba(255, 255, 255, 0.15)",
            borderRadius: "8px",
            padding: "11px",
            fontWeight: "600",
            fontSize: "13px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "8px",
          }}
        >
          <span>🔐</span>
          <span>Sign Up with Keycloak SSO (OIDC + PKCE)</span>
        </button>

        <div style={{ textAlign: "center", fontSize: "13px", color: "#94a3b8", marginTop: "24px" }}>
          Already have an account?{" "}
          <Link href="/login" style={{ color: "#34d399", fontWeight: "700", textDecoration: "none" }}>
            Sign In
          </Link>
        </div>

        <div style={{ borderTop: "1px solid rgba(255, 255, 255, 0.08)", marginTop: "24px", paddingTop: "16px" }}>
          <div style={{ fontSize: "11px", color: "#64748b", lineHeight: 1.6 }}>
            ✓ Cryptographic PBKDF2 / SHA-256 password protection.<br />
            ✓ Zero-Trust multi-tenant isolation enforced by default.<br />
            ✓ Default Workspace (Org, Project & Environment) is automatically provisioned for your account.
          </div>
        </div>
      </div>
    </div>
    </>
  );
}
