import Link from "next/link";

export function PublicHeader() {
  return (
    <header
      style={{
        borderBottom: "1px solid rgba(255, 255, 255, 0.08)",
        backdropFilter: "blur(12px)",
        position: "sticky",
        top: 0,
        zIndex: 50,
        background: "rgba(10, 15, 29, 0.85)",
      }}
    >
      <div
        style={{
          maxWidth: "1280px",
          margin: "0 auto",
          padding: "16px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "16px",
          flexWrap: "wrap",
        }}
      >
        <Link
          href="/"
          aria-label="AgentOps home"
          style={{ display: "flex", alignItems: "center", gap: "12px", color: "inherit", textDecoration: "none" }}
        >
          <div
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, #10b981 0%, #047857 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#ffffff",
              fontWeight: "800",
              fontSize: "14px",
              boxShadow: "0 0 20px rgba(16, 185, 129, 0.3)",
            }}
          >
            AO
          </div>
          <div>
            <span style={{ fontSize: "16px", fontWeight: "800", letterSpacing: "-0.02em", color: "#ffffff" }}>
              AgentOps
            </span>
            <span
              style={{
                marginLeft: "8px",
                fontSize: "9px",
                fontFamily: "'DM Mono', monospace",
                background: "rgba(16, 185, 129, 0.15)",
                color: "#34d399",
                padding: "2px 6px",
                borderRadius: "4px",
                border: "1px solid rgba(52, 211, 153, 0.3)",
              }}
            >
              v2.4
            </span>
          </div>
        </Link>

        <nav style={{ display: "flex", alignItems: "center", gap: "20px", flexWrap: "wrap" }}>
          <Link href="/#features" style={{ fontSize: "13px", color: "#94a3b8", textDecoration: "none" }}>
            Capabilities
          </Link>
          <Link href="/#multi-tenancy" style={{ fontSize: "13px", color: "#94a3b8", textDecoration: "none" }}>
            Multi-Tenancy
          </Link>
          <Link href="/#security-rbac" style={{ fontSize: "13px", color: "#94a3b8", textDecoration: "none" }}>
            Security & Trust
          </Link>
          <Link href="/#contact" style={{ fontSize: "13px", color: "#94a3b8", textDecoration: "none" }}>
            Contact Us
          </Link>
          <div style={{ width: "1px", height: "16px", background: "rgba(255, 255, 255, 0.15)", margin: "0 4px" }} />
          <Link
            href="/login"
            style={{
              fontSize: "13px",
              fontWeight: 600,
              color: "#e2e8f0",
              textDecoration: "none",
              padding: "6px 12px",
              borderRadius: "6px",
              border: "1px solid rgba(255, 255, 255, 0.12)",
              background: "rgba(255, 255, 255, 0.04)",
              transition: "all 0.2s ease",
            }}
          >
            Sign In
          </Link>
          <Link
            href="/signup"
            style={{
              fontSize: "13px",
              fontWeight: 700,
              color: "#022c22",
              textDecoration: "none",
              padding: "6px 14px",
              borderRadius: "6px",
              background: "linear-gradient(135deg, #34d399 0%, #10b981 100%)",
              boxShadow: "0 2px 10px rgba(16, 185, 129, 0.3)",
              transition: "all 0.2s ease",
            }}
          >
            Sign Up Free
          </Link>
        </nav>

      </div>
    </header>
  );
}
