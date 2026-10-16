"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useWorkspace } from "../state/workspace-context";
import { HierarchySwitcher } from "./hierarchy-switcher";

type NavigationItem = { label: string; href: string; icon: string; exact?: boolean; nested?: boolean };
type NavigationGroup = { label: string; items: NavigationItem[] };

export function Navigation() {
  const pathname = usePathname();
  const { user, activeOrg, activeProject, activeEnvironment, effectiveRole, permissions } = useWorkspace();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeLocation, setActiveLocation] = useState("");
  const [signingOut, setSigningOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  useEffect(() => {
    setMobileOpen(false);
    const updateLocation = () => {
      setActiveLocation(`${window.location.pathname}${window.location.search}${window.location.hash}`);
    };
    updateLocation();
    window.addEventListener("hashchange", updateLocation);
    window.addEventListener("popstate", updateLocation);
    return () => {
      window.removeEventListener("hashchange", updateLocation);
      window.removeEventListener("popstate", updateLocation);
    };
  }, [pathname]);

  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setMobileOpen(false);
    }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  const roleName = activeEnvironment?.role || activeProject?.role || activeOrg?.role || effectiveRole;
  const isDemoSession = Boolean(user?.read_only_demo) || pathname === "/demo" || pathname.startsWith("/demo/");
  const overviewHref = isDemoSession ? "/demo" : "/operations";

  const navigationGroups: NavigationGroup[] = [
    {
      label: "PLATFORM CORE",
      items: [
        { label: "Overview & Console", href: overviewHref, icon: "📊" },
        ...(permissions.hasPermission("agents:read") ? [{ label: "Autonomous Agents", href: "/agents", icon: "⚡" }] : []),
        ...(permissions.hasPermission("incidents:read") ? [{ label: "Incidents & SRE", href: "/incidents", icon: "📡" }] : []),
        ...(permissions.hasPermission("cloud:read") || permissions.hasPermission("inventory:read")
          ? [{ label: "Infrastructure & K8s", href: "/integrations", icon: "🔧" }]
          : []),
        ...(permissions.hasPermission("finops:read") ? [{ label: "FinOps & Cloud Spend", href: "/finops", icon: "💰" }] : []),
        ...(permissions.hasPermission("llm:read") ? [{ label: "LLMOps & Gateway", href: "/llmops", icon: "🧠" }] : []),
        ...(permissions.hasPermission("rag:read") ? [
          { label: "Knowledge Base (RAG)", href: "/knowledge", icon: "📚" },
        ] : []),
      ],
    },
    {
      label: "WORKSPACE & SECURITY",
      items: [
        ...(permissions.hasPermission("security:read") ? [{ label: "Security & RBAC", href: "/security", icon: "🛡️" }] : []),
        ...(permissions.hasPermission("organization:read") ? [{ label: "Multi-Tenancy & Orgs", href: "/multi-tenancy", icon: "🏢" }] : []),
        ...(permissions.hasPermission("project:read") ? [{ label: "Projects & Envs", href: "/projects", icon: "📁" }] : []),
        { label: "Settings & Audit Logs", href: "/settings", icon: "⚙️" },
      ],
    },
  ];

  const displayName =
    user?.display_name ||
    (user?.email ? user.email.split("@")[0].replace(/[._-]/g, " ") : "Account");
  const initials = displayName.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase() || "AO";

  function renderItems(items: NavigationItem[]) {
    return items.map((item) => {
      const active = item.exact
        ? activeLocation === item.href
        : item.href.includes("#")
          ? activeLocation === item.href
          : (pathname === item.href || pathname.startsWith(`${item.href}/`))
            && !(activeLocation.includes("#") && navigationGroups.some((group) =>
              group.items.some((child) => child.nested && child.href.startsWith(`${item.href}#`)),
            ));
      return (
        <Link
          className={`nav-item${item.nested ? " nav-subitem" : ""}${active ? " active" : ""}`}
          href={item.href}
          key={item.href}
          aria-current={active ? "page" : undefined}
          onClick={() => {
            setMobileOpen(false);
            setActiveLocation(item.href);
          }}
        >
          <span className="nav-icon" aria-hidden="true">{item.icon}</span>
          <span>{item.label}</span>
        </Link>
      );
    });
  }

  async function handleLogout() {
    setSigningOut(true);
    setLogoutError(null);
    try {
      const response = await fetch("/api/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error(`Sign out failed (${response.status}).`);
      const data = await response.json();
      window.location.assign(data.redirect_url || "/login");
    } catch (err: unknown) {
      setLogoutError(err instanceof Error ? err.message : "Unable to sign out.");
      setSigningOut(false);
    }
  }

  return (
    <>
      <button
        type="button"
        className="mobile-nav-toggle"
        aria-controls="primary-navigation"
        aria-expanded={mobileOpen}
        aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
        onClick={() => setMobileOpen((open) => !open)}
      >
        <span aria-hidden="true">{mobileOpen ? "×" : "☰"}</span>
        {mobileOpen ? "Close menu" : "Menu"}
      </button>
      {mobileOpen && (
        <button
          type="button"
          className="mobile-nav-backdrop"
          aria-label="Close navigation menu"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside className={`sidebar${mobileOpen ? " mobile-open" : ""}`}>
        <Link href={overviewHref} className="brand" aria-label="AgentOps overview" style={{ padding: "0 4px 20px" }}>
          <div style={{
            width: "36px",
            height: "36px",
            background: "#10b981",
            borderRadius: "10px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#ffffff",
            fontWeight: "800",
            fontSize: "14px",
            letterSpacing: "-0.02em",
            boxShadow: "0 4px 12px rgba(16, 185, 129, 0.35)",
            flexShrink: 0,
          }}>
            AO
          </div>
          <div className="brand-copy" style={{ marginLeft: "10px" }}>
            <strong style={{ fontSize: "16px", color: "#ffffff", fontWeight: "800", letterSpacing: "-0.02em" }}>AgentOps</strong>
            <small style={{ color: "#94a3b8", fontSize: "11px", marginTop: "1px" }}>
              {isDemoSession ? "Demo Environment" : "Production Platform"}
            </small>
          </div>
        </Link>

        {/* Active Context / Demo Hierarchy Card */}
        <div
          style={{
            padding: "10px 14px",
            margin: "0 0 20px",
            background: "rgba(16, 185, 129, 0.05)",
            borderRadius: "10px",
            border: "1px solid rgba(16, 185, 129, 0.18)",
          }}
        >
          <div style={{ fontSize: "9px", fontFamily: "'DM Mono', monospace", color: "#34d399", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: "600" }}>
            {isDemoSession ? "ACTIVE DEMO HIERARCHY" : "ACTIVE CONTEXT SUMMARY"}
          </div>
          <div style={{ fontSize: "13px", fontWeight: "700", color: "#ffffff", marginTop: "4px" }}>
            {activeOrg?.name || "Acme Corp"}
          </div>
          <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "2px" }}>
            / {activeProject?.name || "AgentOps Core Plane"}
          </div>
          <div style={{ fontSize: "11px", color: "#34d399", fontFamily: "'DM Mono', monospace", marginTop: "2px" }}>
            / {activeEnvironment?.name || "Production"} ({roleName || "Admin"})
          </div>
        </div>

        <HierarchySwitcher />

        <nav id="primary-navigation" className="primary-navigation" aria-label="Primary navigation">
          {navigationGroups.map((group) => group.items.length > 0 && (
            <div className="nav-section" key={group.label}>
              <span className="eyebrow nav-label">{group.label}</span>
              {renderItems(group.items)}
            </div>
          ))}
        </nav>

        <div className="sidebar-footer">
          {logoutError && <p className="sidebar-error" role="alert">{logoutError}</p>}
          <div className="profile">
            <span className="avatar" aria-hidden="true">{initials}</span>
            <span className="profile-copy">
              <strong>{displayName}</strong>
              <small>{roleName}</small>
            </span>
          </div>
          <button type="button" className="sign-out-button" onClick={() => void handleLogout()} disabled={signingOut}>
            {signingOut ? "Signing out…" : "Sign out"}
          </button>
        </div>
      </aside>
    </>
  );
}
