import Link from "next/link";

export default function CapabilitiesPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#0a0f1d", color: "#f8fafc", fontFamily: "'Manrope', sans-serif" }}>
      <header style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", background: "rgba(10,15,29,0.85)" }}>
        <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: "12px", color: "inherit", textDecoration: "none" }}>
            <div style={{ width: "36px", height: "36px", borderRadius: "10px", background: "linear-gradient(135deg, #10b981 0%, #047857 100%)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, color: "#fff" }}>AO</div>
            <span style={{ fontSize: "16px", fontWeight: 800 }}>AgentOps</span>
          </Link>
          <nav style={{ display: "flex", gap: "22px", fontSize: "13px", color: "#94a3b8" }}>
            <Link href="/multi-tenancy" style={{ color: "inherit", textDecoration: "none" }}>Multi-Tenancy</Link>
            <Link href="/security" style={{ color: "inherit", textDecoration: "none" }}>Security & RBAC</Link>
            <Link href="/contact" style={{ color: "inherit", textDecoration: "none" }}>Contact Us</Link>
          </nav>
        </div>
      </header>

      <main style={{ maxWidth: "1100px", margin: "0 auto", padding: "56px 24px 80px" }}>
        <div style={{ maxWidth: "760px", marginBottom: "32px" }}>
          <span style={{ color: "#34d399", fontFamily: "'DM Mono', monospace", letterSpacing: "0.1em", fontSize: "11px" }}>PLATFORM CAPABILITIES</span>
          <h1 style={{ fontSize: "42px", letterSpacing: "-0.04em", margin: "12px 0" }}>Autonomous operations for cloud, cost, and AI workloads.</h1>
          <p style={{ color: "#94a3b8", fontSize: "18px", lineHeight: 1.7 }}>
            AgentOps unifies SRE, FinOps, security investigations, and LLMOps under a common control plane so teams can automate incident response, optimize cloud spend, and govern AI workloads with consistent policy.
          </p>
        </div>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "20px" }}>
          {[
            ["Autonomous SRE", "Correlate changes, incidents, and infrastructure telemetry to shorten time to root cause and safely recommend or execute remediation."],
            ["FinOps Intelligence", "Track resource efficiency, forecast spend, and surface cost anomalies across multi-cloud and hybrid workloads."],
            ["LLMOps Observability", "Monitor LLM gateway latency, token consumption, model quality, and fallback behavior from one operational view."],
            ["Zero-Trust Governance", "Apply tenant isolation, policy enforcement, approval gates, and role-based access across every workflow."],
          ].map(([title, copy]) => (
            <article key={title} style={{ background: "rgba(15,23,42,0.75)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "16px", padding: "24px" }}>
              <h2 style={{ margin: "0 0 12px", fontSize: "20px" }}>{title}</h2>
              <p style={{ margin: 0, color: "#94a3b8", lineHeight: 1.7 }}>{copy}</p>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
