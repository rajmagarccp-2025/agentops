"use client";

import Link from "next/link";
import { useState } from "react";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await fetch("/api/proxy/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const body = await response.json().catch(() => null);
      if (!response.ok) throw new Error(body?.detail || `Password recovery failed (${response.status}).`);
      setSubmitted(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Password recovery could not be completed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #0a0f1d 0%, #0d1e17 100%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "20px",
        fontFamily: "'Manrope', sans-serif",
      }}
    >
      <div
        style={{
          background: "#ffffff",
          borderRadius: "16px",
          width: "100%",
          maxWidth: "440px",
          padding: "36px",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.3)",
        }}
      >
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <h1 style={{ margin: "0 0 6px 0", fontSize: "20px", letterSpacing: "-0.03em" }}>
            Reset Your Password
          </h1>
          <p style={{ margin: 0, fontSize: "12px", color: "#64748b" }}>
            Password recovery depends on the identity provider configured for your account.
          </p>
        </div>

        {submitted ? (
          <div style={{ textAlign: "center", padding: "12px 0" }}>
            <div className="alert-banner success" style={{ marginBottom: "20px" }}>
              <span>✓</span>
              <div>
                Password recovery instructions have been requested for <strong>{email}</strong>.
              </div>
            </div>
            <Link href="/login" className="btn btn-primary" style={{ width: "100%" }}>
              Return to Login
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} style={{ display: "grid", gap: "16px" }}>
            {error && <div className="alert-banner error" role="alert">{error}</div>}
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">Enter Work Email</label>
              <input
                type="email"
                required
                className="form-input"
                placeholder="alex.rivera@enterprise.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: "100%", padding: "12px" }} disabled={isSubmitting}>
              {isSubmitting ? "Requesting…" : "Send Reset Instructions"}
            </button>

            <div style={{ textAlign: "center", fontSize: "12px" }}>
              <Link href="/login" style={{ color: "#64748b" }}>
                ← Back to Login
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
