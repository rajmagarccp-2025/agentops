import Link from "next/link";

export default function RBACPage() {
  return (
    <div style={{ minHeight: "100vh", background: "#0a0f1d", color: "#f8fafc", fontFamily: "'Manrope', sans-serif" }}>
      <header style={{ borderBottom: "1px solid rgba(255,255,255,0.08)", background: "rgba(10,15,29,0.85)" }}>
        <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "16px 24px", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <Link href="/" style={{ display: "flex", alignItems: "center", gap: "12px", color: "inherit", textDecoration: "none" }}>
            <div style={{ width: "36px", height: "36px", borderRadius: "10px", background: "linear-gradient(135deg, #10b981 0%, #047857 100%)", display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, color: "#fff" }}>AO</div>
            <span style={{ fontSize: "16px", fontWeight: 800 }}>AgentOps</span>
          </Link>
          <nav style={{ display: "flex", gap: "22px", fontSize: "13px", color: "#94a3b8" }}>
            <Link href="/capabilities" style={{ color: "inherit", textDecoration: "none" }}>Capabilities</Link>
            <Link href="/multi-tenancy" style={{ color: "inherit", textDecoration: "none" }}>Multi-Tenancy</Link>
            <Link href="/contact" style={{ color: "inherit", textDecoration: "none" }}>Contact Us</Link>
          </nav>
        </div>
      </header>

      <main style={{ maxWidth: "1100px", margin: "0 auto", padding: "56px 24px 80px" }}>
        <div style={{ maxWidth: "760px" }}>
          <span style={{ color: "#34d399", fontFamily: "'DM Mono', monospace", letterSpacing: "0.1em", fontSize: "11px" }}>RBAC & ACCESS CONTROL</span>
          <h1 style={{ fontSize: "42px", letterSpacing: "-0.04em", margin: "12px 0" }}>Roles, permissions, and delegated authority.</h1>
          <p style={{ color: "#94a3b8", fontSize: "18px", lineHeight: 1.7 }}>
            AgentOps enforces enterprise access control at the organization, project, and environment scope so administrators can grant only the permissions each team needs.
          </p>
        </div>

        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "20px", marginTop: "28px" }}>
          {[
            ["Administrator", "Full access to tenant configuration, member approval, and workflow controls."],
            ["Writer", "Can operate within a project or environment while remaining constrained from administrative changes."],
            ["Reader", "Read-only access to observability, projects, and policy context without mutating production systems."],
          ].map(([role, copy]) => (
            <article key={role} style={{ background: "rgba(15,23,42,0.75)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "16px", padding: "24px" }}>
              <h2 style={{ margin: "0 0 12px", fontSize: "22px" }}>{role}</h2>
              <p style={{ margin: 0, color: "#94a3b8", lineHeight: 1.7 }}>{copy}</p>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
