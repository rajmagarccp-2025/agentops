import Link from "next/link";
import Image from "next/image";
import { PublicHeader } from "../components/public-header";

export const metadata = {
  title: "AgentOps",
  description: "Cloud-agnostic agentic SRE, FinOps, and LLMOps operations console with tenant-scoped workspaces and role-based access.",
};

export default function LandingPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#0a0f1d", color: "#f8fafc", fontFamily: "'Manrope', sans-serif" }}>
      <PublicHeader />

      {/* Hero Section */}
      <section style={{ maxWidth: "1280px", margin: "0 auto", padding: "80px 24px 60px" }}>
        <div style={{ textAlign: "center", maxWidth: "860px", margin: "0 auto 48px" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 14px",
              borderRadius: "9999px",
              background: "rgba(16, 185, 129, 0.1)",
              border: "1px solid rgba(16, 185, 129, 0.25)",
              color: "#34d399",
              fontSize: "12px",
              fontFamily: "'DM Mono', monospace",
              marginBottom: "24px",
            }}
          >
            <span>⚡ Next-Generation Autonomous Multi-Tenant Cloud Control Plane</span>
          </div>

          <h1
            style={{
              fontSize: "clamp(36px, 5vw, 64px)",
              fontWeight: "800",
              letterSpacing: "-0.04em",
              lineHeight: 1.1,
              margin: "0 0 20px 0",
              background: "linear-gradient(180deg, #ffffff 0%, #cbd5e1 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Cloud-Agnostic Agentic SRE, FinOps & LLMOps Platform
          </h1>

          <p style={{ fontSize: "18px", color: "#94a3b8", lineHeight: 1.6, margin: "0 auto 36px", maxWidth: "700px" }}>
            Unify reliability engineering, multi-cloud cost optimization, and LLM gateway observability with
            server-enforced workspace scope and role-based access controls.
          </p>

          <div style={{ display: "flex", justifyContent: "center", gap: "16px", flexWrap: "wrap" }}>
            <Link
              href="/demo"
              style={{
                padding: "14px 28px",
                fontSize: "14px",
                fontWeight: "700",
                background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                color: "#ffffff",
                borderRadius: "8px",
                boxShadow: "0 6px 20px rgba(16, 185, 129, 0.4)",
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                textDecoration: "none",
              }}
            >
              <span>Explore sample console</span>
              <span>→</span>
            </Link>
            <Link
              href="/signup"
              style={{
                padding: "14px 28px",
                fontSize: "14px",
                fontWeight: "700",
                background: "rgba(255, 255, 255, 0.05)",
                color: "#f8fafc",
                borderRadius: "8px",
                border: "1px solid rgba(255, 255, 255, 0.15)",
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                textDecoration: "none",
                backdropFilter: "blur(8px)",
              }}
            >
              <span>Sign up free</span>
            </Link>
          </div>
        </div>

        {/* Hero Visual Mockup */}
        <div
          style={{
            position: "relative",
            borderRadius: "16px",
            overflow: "hidden",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.6), 0 0 80px rgba(16, 185, 129, 0.12)",
            background: "#0f172a",
          }}
        >
          <div
            style={{
              padding: "12px 18px",
              background: "#1e293b",
              borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#ef4444" }} />
              <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#f59e0b" }} />
              <span style={{ width: "10px", height: "10px", borderRadius: "50%", background: "#10b981" }} />
              <span style={{ marginLeft: "12px", fontSize: "11px", color: "#94a3b8", fontFamily: "'DM Mono', monospace" }}>
                agentops.internal / enterprise-control-plane
              </span>
            </div>
            <div style={{ display: "flex", gap: "10px" }}>
              <span style={{ fontSize: "10px", color: "#34d399", fontFamily: "'DM Mono', monospace" }}>
                Operations workspace preview
              </span>
            </div>
          </div>
          <div style={{ position: "relative", width: "100%", height: "auto", minHeight: "380px" }}>
            <Image
              src="/hero-illustration.jpg"
              alt="AgentOps Multi-Tenant AI SRE & FinOps Architecture Overview"
              width={1600}
              height={900}
              priority
              style={{ width: "100%", height: "auto", display: "block" }}
            />
          </div>
        </div>
      </section>

      {/* Trust & Enterprise Badges */}
      <section
        style={{
          borderTop: "1px solid rgba(255, 255, 255, 0.06)",
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
          background: "rgba(255, 255, 255, 0.02)",
          padding: "36px 24px",
        }}
      >
        <div
          style={{
            maxWidth: "1280px",
            margin: "0 auto",
            display: "flex",
            justifyContent: "space-around",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "24px",
          }}
        >
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "18px", fontWeight: "800", color: "#ffffff" }}>OIDC Support</div>
            <div style={{ fontSize: "11px", color: "#64748b", fontFamily: "'DM Mono', monospace" }}>
              Configurable identity provider
            </div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "18px", fontWeight: "800", color: "#ffffff" }}>Workspace Scoping</div>
            <div style={{ fontSize: "11px", color: "#64748b", fontFamily: "'DM Mono', monospace" }}>
              Org → Project → Environment
            </div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "18px", fontWeight: "800", color: "#ffffff" }}>3-Tier RBAC</div>
            <div style={{ fontSize: "11px", color: "#64748b", fontFamily: "'DM Mono', monospace" }}>
              ADMIN · WRITE · READ (AI Guarded)
            </div>
          </div>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: "18px", fontWeight: "800", color: "#ffffff" }}>Audit Logging</div>
            <div style={{ fontSize: "11px", color: "#64748b", fontFamily: "'DM Mono', monospace" }}>
              Recorded administrative events
            </div>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" style={{ maxWidth: "1280px", margin: "0 auto", padding: "80px 24px 40px" }}>
        <div style={{ textAlign: "center", marginBottom: "50px" }}>
          <span style={{ color: "#34d399", fontFamily: "'DM Mono', monospace", fontSize: "11px", letterSpacing: "0.1em" }}>
            CORE CAPABILITIES
          </span>
          <h2 style={{ fontSize: "32px", fontWeight: "800", marginTop: "8px", letterSpacing: "-0.03em" }}>
            Architected for Mission-Critical Infrastructure
          </h2>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "24px" }}>
          <div
            style={{
              background: "rgba(255, 255, 255, 0.03)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "12px",
              padding: "28px",
            }}
          >
            <div style={{ fontSize: "28px", marginBottom: "14px" }}>🏢</div>
            <h3 style={{ fontSize: "18px", fontWeight: "700", marginBottom: "10px", color: "#ffffff" }}>
              Strict Multi-Tenancy Hierarchy
            </h3>
            <p style={{ fontSize: "13px", color: "#94a3b8", lineHeight: 1.6 }}>
              Organization → Project → Environment isolation. Independent membership scoping ensures that User A in Org X can never inspect or modify assets in Org Y.
            </p>
          </div>

          <div
            style={{
              background: "rgba(255, 255, 255, 0.03)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "12px",
              padding: "28px",
            }}
          >
            <div style={{ fontSize: "28px", marginBottom: "14px" }}>🛡️</div>
            <h3 style={{ fontSize: "18px", fontWeight: "700", marginBottom: "10px", color: "#ffffff" }}>
              AI Guardrailed Authorization
            </h3>
            <p style={{ fontSize: "13px", color: "#94a3b8", lineHeight: 1.6 }}>
              API permissions are enforced server-side for protected operations, including AI query access. The effective role and granted permissions depend on the authenticated workspace context.
            </p>
          </div>

          <div
            style={{
              background: "rgba(255, 255, 255, 0.03)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "12px",
              padding: "28px",
            }}
          >
            <div style={{ fontSize: "28px", marginBottom: "14px" }}>📨</div>
            <h3 style={{ fontSize: "18px", fontWeight: "700", marginBottom: "10px", color: "#ffffff" }}>
              Secure Multi-Scope Invitations
            </h3>
            <p style={{ fontSize: "13px", color: "#94a3b8", lineHeight: 1.6 }}>
              Admins invite members via high-entropy cryptographically secure invitation tokens targeting specific Organizations, Projects, or Environments with automated expiration.
            </p>
          </div>
        </div>
      </section>







      <section id="multi-tenancy" style={{ maxWidth: "1280px", margin: "0 auto", padding: "48px 24px 12px" }}>
        <div
          style={{
            background: "rgba(255, 255, 255, 0.03)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "18px",
            padding: "32px 28px",
          }}
        >
          <span style={{ color: "#34d399", fontFamily: "'DM Mono', monospace", fontSize: "11px", letterSpacing: "0.1em" }}>
            MULTI-TENANCY
          </span>
          <h3 style={{ fontSize: "30px", fontWeight: "800", margin: "12px 0 16px", letterSpacing: "-0.03em" }}>
            One shared control plane, isolated by tenant scope.
          </h3>
          <p style={{ margin: 0, color: "#cbd5e1", lineHeight: 1.7, maxWidth: "760px" }}>
            Each organization, project, and environment is isolated behind server-enforced tenancy checks. The same UI,
            workflow, and permissions model applies across production and demo contexts without mixing customer data.
          </p>
        </div>
      </section>

      <section id="security-rbac" style={{ maxWidth: "1280px", margin: "0 auto", padding: "36px 24px 12px" }}>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: "20px",
          }}
        >
          <div
            style={{
              background: "rgba(16, 185, 129, 0.05)",
              border: "1px solid rgba(16, 185, 129, 0.2)",
              borderRadius: "16px",
              padding: "24px",
            }}
          >
            <div style={{ fontSize: "28px", marginBottom: "12px" }}>🔐</div>
            <h3 style={{ margin: "0 0 10px", fontSize: "22px", color: "#ffffff" }}>Security-first policy</h3>
            <p style={{ margin: 0, color: "#cbd5e1", lineHeight: 1.7 }}>
              OIDC, tenant membership validation, and permission checks are enforced on the backend before any resource is returned or mutated.
            </p>
          </div>
          <div
            style={{
              background: "rgba(255, 255, 255, 0.03)",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              borderRadius: "16px",
              padding: "24px",
            }}
          >
            <div style={{ fontSize: "28px", marginBottom: "12px" }}>🧭</div>
            <h3 style={{ margin: "0 0 10px", fontSize: "22px", color: "#ffffff" }}>Role-aware access</h3>
            <p style={{ margin: 0, color: "#cbd5e1", lineHeight: 1.7 }}>
              Read, write, and administrator scopes map to real tenant-bound permissions rather than client-side role assumptions.
            </p>
          </div>
        </div>
      </section>

      <section id="contact" style={{ maxWidth: "960px", margin: "0 auto", padding: "48px 24px 24px" }}>
        <div
          style={{
            background: "linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(14, 165, 233, 0.08))",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: "18px",
            padding: "32px 28px",
            textAlign: "center",
          }}
        >
          <span style={{ color: "#34d399", fontFamily: "'DM Mono', monospace", fontSize: "11px", letterSpacing: "0.1em" }}>
            CONTACT US
          </span>
          <h3 style={{ fontSize: "30px", fontWeight: "800", margin: "12px 0 14px", letterSpacing: "-0.03em" }}>
            Talk with our platform team
          </h3>
          <p style={{ margin: "0 auto 20px", maxWidth: "620px", color: "#cbd5e1", lineHeight: 1.7 }}>
            Need a tenant-scoped operations environment, SRE automation workflow, or secure multi-cloud rollout plan? We can help you design it.
          </p>
          <a
            href="mailto:hello@agentops.example"
            style={{
              display: "inline-block",
              padding: "12px 22px",
              borderRadius: "8px",
              background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
              color: "#ffffff",
              textDecoration: "none",
              fontWeight: "700",
            }}
          >
            hello@agentops.example
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ borderTop: "1px solid rgba(255, 255, 255, 0.08)", padding: "40px 24px", textAlign: "center", color: "#64748b", fontSize: "12px" }}>
        <p style={{ margin: "0 0 10px 0" }}>
          © 2026 AgentOps Cloud Platform · Enterprise Identity & Multi-Tenant RBAC Subsystem
        </p>
        <p style={{ fontFamily: "'DM Mono', monospace", margin: 0 }}>
          Built with an OIDC-compatible identity layer · FastAPI · Next.js App Router
        </p>
      </footer>
    </div>
  );
}