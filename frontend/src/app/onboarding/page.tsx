"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useWorkspace, type OrganizationItem } from "../../state/workspace-context";

interface PendingInvitation {
  id: string;
  token: string;
  email: string;
  organization_id: string;
  project_id?: string | null;
  environment_id?: string | null;
  role: string;
  expires_at: string;
}

interface ExistingOrg {
  id: string;
  name: string;
  slug: string;
  description?: string;
}

export default function OnboardingPage() {
  const router = useRouter();
  const { refreshWorkspace, setActiveOrg, switchOrg, workspaceError } = useWorkspace();

  const [mode, setMode] = useState<"create" | "join">("create");
  const [currentStep, setCurrentStep] = useState<1 | 2 | 3 | 4>(1);

  // Step 1: Organization
  const [orgName, setOrgName] = useState("");
  const [orgSlug, setOrgSlug] = useState("");
  const [orgDescription, setOrgDescription] = useState("");
  const [createdOrgId, setCreatedOrgId] = useState<string | null>(null);
  const [createdOrganization, setCreatedOrganization] = useState<OrganizationItem | null>(null);

  // Step 2: Project
  const [projectName, setProjectName] = useState("Production AI Platform");
  const [projectSlug, setProjectSlug] = useState("production-ai-platform");
  const [projectDescription, setProjectDescription] = useState("Primary SRE and LLM operations workspace");
  const [, setCreatedProjectId] = useState<string | null>(null);

  // Step 3: Environment
  const [envName, setEnvName] = useState("Production");
  const [envType, setEnvType] = useState("Production");
  const [envDescription, setEnvDescription] = useState("Live production environment");
  const [, setCreatedEnvId] = useState<string | null>(null);

  // Invitations & Existing Orgs
  const [tokenInput, setTokenInput] = useState("");
  const [pendingInvitations, setPendingInvitations] = useState<PendingInvitation[]>([]);
  const [existingOrgs, setExistingOrgs] = useState<ExistingOrg[]>([]);
  const [userEmail, setUserEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const res = await fetch("/api/proxy/onboarding/status");
        if (!res.ok) {
          const body = await res.json().catch(() => null);
          throw new Error(body?.detail || `Unable to load onboarding status (${res.status}).`);
        }
        const data = await res.json();
        if (data.user?.email) {
          setUserEmail(data.user.email);
        }
        if (data.organizations && data.organizations.length > 0) {
          setExistingOrgs(data.organizations);
        }
        if (data.pending_invitations && data.pending_invitations.length > 0) {
          setPendingInvitations(data.pending_invitations);
          setMode("join");
        }
      } catch (err: unknown) {
        setErrorMsg(err instanceof Error ? err.message : "Unable to load onboarding status.");
      }
    };
    checkStatus();
  }, []);

  const handleStep1Org = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!orgName.trim()) {
      setErrorMsg("Organization name is required.");
      return;
    }
    setIsLoading(true);
    setErrorMsg(null);

    try {
      const res = await fetch("/api/proxy/organizations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: orgName.trim(),
          slug: orgSlug.trim() || undefined,
          description: orgDescription.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed to create organization" }));
        throw new Error(err.detail || "Failed to create organization");
      }

      const orgData = await res.json();
      setCreatedOrgId(orgData.id);
      setCreatedOrganization(orgData);
      const switched = await setActiveOrg(orgData);
      if (!switched) {
        throw new Error("Organization was created, but its workspace context could not be selected.");
      }
      await refreshWorkspace();
      setCurrentStep(2);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Creation failed";
      setErrorMsg(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const retryOrganizationContext = async () => {
    if (!createdOrganization) return;
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const switched = await setActiveOrg(createdOrganization);
      if (!switched) {
        throw new Error("Workspace selection failed. Review the workspace context error and retry.");
      }
      await refreshWorkspace();
      setCurrentStep(2);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Unable to select the created organization.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleStep2Project = (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectName.trim()) {
      setErrorMsg("Project name is required.");
      return;
    }
    setErrorMsg(null);
    setCurrentStep(3);
  };

  const handleStep3Environment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!envName.trim()) {
      setErrorMsg("Environment name is required.");
      return;
    }
    if (!createdOrgId) {
      setErrorMsg("Organization context missing.");
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    try {
      // Create project with initial environment
      const projRes = await fetch(`/api/proxy/organizations/${createdOrgId}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: projectName.trim(),
          slug: projectSlug.trim() || undefined,
          description: projectDescription.trim() || undefined,
          initial_environment_name: envName.trim(),
          initial_environment_type: envType,
          initial_environment_description: envDescription.trim(),
        }),
      });

      if (!projRes.ok) {
        const err = await projRes.json().catch(() => ({ detail: "Failed to create project" }));
        throw new Error(err.detail || "Failed to create project");
      }

      const projData = await projRes.json();
      setCreatedProjectId(projData.id);
      setCreatedEnvId(projData.initial_environment?.id || null);

      // Refresh authentication token context via switch-context
      const contextResponse = await fetch("/api/auth/switch-context", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          organization_id: createdOrgId,
          project_id: projData.id,
          environment_id: projData.initial_environment?.id,
        }),
      });
      if (!contextResponse.ok) {
        const body = await contextResponse.json().catch(() => null);
        throw new Error(body?.detail || `Unable to select the new workspace (${contextResponse.status}).`);
      }

      await refreshWorkspace();
      setCurrentStep(4);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Environment setup failed";
      setErrorMsg(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAcceptInvite = async (token: string) => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await fetch(`/api/proxy/invitations/${token}/accept`, {
        method: "POST",
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Failed to accept invitation" }));
        throw new Error(err.detail || "Failed to accept invitation");
      }
      setSuccessMsg("Invitation accepted! Welcome to the organization.");
      await refreshWorkspace();
      setTimeout(() => {
        router.push("/operations");
      }, 1000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Acceptance failed";
      setErrorMsg(msg);
      setIsLoading(false);
    }
  };

  const handleSelectExistingOrg = async (org: ExistingOrg) => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const switched = await switchOrg(org.id);
      if (!switched) {
        throw new Error(`Unable to select ${org.name}. Review the workspace context error and retry.`);
      }
      await refreshWorkspace();
      router.push("/operations");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Unable to select this organization.");
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
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
          width: "100%",
          maxWidth: "580px",
          background: "#0f172a",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          borderRadius: "16px",
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.7), 0 0 40px rgba(16, 185, 129, 0.1)",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div style={{ background: "rgba(16, 185, 129, 0.08)", borderBottom: "1px solid rgba(255, 255, 255, 0.08)", padding: "28px 32px 20px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "linear-gradient(135deg, #10b981 0%, #047857 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: "800",
                fontSize: "13px",
                color: "#ffffff",
              }}
            >
              AO
            </div>
            <span style={{ fontSize: "11px", fontFamily: "'DM Mono', monospace", color: "#34d399", textTransform: "uppercase" }}>
              AgentOps Onboarding
            </span>
          </div>
          <h1 style={{ fontSize: "22px", fontWeight: "800", margin: "0 0 6px 0", letterSpacing: "-0.02em" }}>
            Welcome to AgentOps
          </h1>
          <p style={{ margin: 0, fontSize: "13px", color: "#94a3b8" }}>
            {userEmail ? `Signed in as ${userEmail}. ` : ""}
            Set up your organization, project & environment, or join an existing organization by invitation.
          </p>

          {/* Step Wizard Indicator */}
          {mode === "create" && currentStep < 4 && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "20px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span
                  style={{
                    width: "24px",
                    height: "24px",
                    borderRadius: "50%",
                    background: currentStep >= 1 ? "#10b981" : "rgba(255, 255, 255, 0.1)",
                    color: "#ffffff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "12px",
                    fontWeight: "700",
                  }}
                >
                  1
                </span>
                <span style={{ fontSize: "12px", fontWeight: currentStep === 1 ? "700" : "500", color: currentStep === 1 ? "#34d399" : "#94a3b8" }}>
                  Organization
                </span>
              </div>
              <div style={{ flex: 1, height: "1px", background: "rgba(255, 255, 255, 0.1)", margin: "0 10px" }} />
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span
                  style={{
                    width: "24px",
                    height: "24px",
                    borderRadius: "50%",
                    background: currentStep >= 2 ? "#10b981" : "rgba(255, 255, 255, 0.1)",
                    color: "#ffffff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "12px",
                    fontWeight: "700",
                  }}
                >
                  2
                </span>
                <span style={{ fontSize: "12px", fontWeight: currentStep === 2 ? "700" : "500", color: currentStep === 2 ? "#34d399" : "#94a3b8" }}>
                  Project
                </span>
              </div>
              <div style={{ flex: 1, height: "1px", background: "rgba(255, 255, 255, 0.1)", margin: "0 10px" }} />
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span
                  style={{
                    width: "24px",
                    height: "24px",
                    borderRadius: "50%",
                    background: currentStep >= 3 ? "#10b981" : "rgba(255, 255, 255, 0.1)",
                    color: "#ffffff",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "12px",
                    fontWeight: "700",
                  }}
                >
                  3
                </span>
                <span style={{ fontSize: "12px", fontWeight: currentStep === 3 ? "700" : "500", color: currentStep === 3 ? "#34d399" : "#94a3b8" }}>
                  Environment
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Mode Switch Tabs */}
        {currentStep === 1 && (
          <div style={{ display: "flex", borderBottom: "1px solid rgba(255, 255, 255, 0.08)" }}>
            <button
              type="button"
              onClick={() => setMode("create")}
              style={{
                flex: 1,
                padding: "14px",
                border: "none",
                background: mode === "create" ? "rgba(255, 255, 255, 0.04)" : "transparent",
                borderBottom: mode === "create" ? "2px solid #10b981" : "none",
                color: mode === "create" ? "#34d399" : "#94a3b8",
                fontWeight: 700,
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Setup New Workspace
            </button>
            <button
              type="button"
              onClick={() => setMode("join")}
              style={{
                flex: 1,
                padding: "14px",
                border: "none",
                background: mode === "join" ? "rgba(255, 255, 255, 0.04)" : "transparent",
                borderBottom: mode === "join" ? "2px solid #10b981" : "none",
                color: mode === "join" ? "#34d399" : "#94a3b8",
                fontWeight: 700,
                fontSize: "13px",
                cursor: "pointer",
              }}
            >
              Join via Invitation {pendingInvitations.length > 0 && `(${pendingInvitations.length})`}
            </button>
          </div>
        )}

        {/* Content Body */}
        <div style={{ padding: "28px 32px" }}>
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
              {createdOrganization && currentStep === 1 && <button type="button" className="btn btn-secondary" disabled={isLoading} onClick={() => void retryOrganizationContext()}>Retry workspace selection</button>}
            </div>
          )}
          {workspaceError && !workspaceError.toLowerCase().includes("tenant context") && (
            <p role="alert" className="data-note warning">{workspaceError}</p>
          )}

          {successMsg && (
            <div
              style={{
                padding: "12px 14px",
                background: "rgba(16, 185, 129, 0.15)",
                border: "1px solid #10b981",
                borderRadius: "8px",
                color: "#6ee7b7",
                fontSize: "13px",
                marginBottom: "20px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <span>✓</span>
              <span>{successMsg}</span>
            </div>
          )}

          {mode === "create" ? (
            <>
              {/* Step 1 of 3: Create Organization */}
              {currentStep === 1 && (
                <form onSubmit={handleStep1Org}>
                  <div style={{ marginBottom: "18px" }}>
                    <span style={{ fontSize: "11px", color: "#34d399", fontFamily: "'DM Mono', monospace" }}>
                      STEP 1 OF 3
                    </span>
                    <h2 style={{ fontSize: "18px", fontWeight: "700", margin: "4px 0" }}>
                      Create your organization
                    </h2>
                    <p style={{ fontSize: "12px", color: "#94a3b8", margin: 0 }}>
                      As the creator, you will automatically become the <strong>Organization Owner</strong>.
                    </p>
                  </div>

                  <div style={{ display: "grid", gap: "16px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", color: "#cbd5e1", marginBottom: "6px" }}>
                        Organization Name *
                      </label>
                      <input
                        type="text"
                        id="org-name-input"
                        placeholder="e.g. Acme Corporation"
                        value={orgName}
                        onChange={(e) => {
                          setOrgName(e.target.value);
                          if (!orgSlug) {
                            setOrgSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
                          }
                        }}
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
                      <label style={{ display: "block", fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", color: "#cbd5e1", marginBottom: "6px" }}>
                        Organization Slug
                      </label>
                      <input
                        type="text"
                        id="org-slug-input"
                        placeholder="e.g. acme-corporation"
                        value={orgSlug}
                        onChange={(e) => setOrgSlug(e.target.value)}
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
                      <span style={{ fontSize: "11px", color: "#64748b", marginTop: "4px", display: "block" }}>
                        Unique URL-friendly tenant identifier.
                      </span>
                    </div>

                    <div>
                      <label style={{ display: "block", fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", color: "#cbd5e1", marginBottom: "6px" }}>
                        Description (Optional)
                      </label>
                      <textarea
                        rows={2}
                        placeholder="Primary enterprise tenant for autonomous cloud engineering workloads"
                        value={orgDescription}
                        onChange={(e) => setOrgDescription(e.target.value)}
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
                      id="step1-submit-btn"
                      disabled={isLoading}
                      style={{
                        padding: "12px",
                        background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "8px",
                        fontWeight: "700",
                        fontSize: "14px",
                        cursor: isLoading ? "wait" : "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "8px",
                        marginTop: "8px",
                      }}
                    >
                      {isLoading ? "Creating Organization..." : "Create Organization & Continue →"}
                    </button>
                  </div>
                </form>
              )}

              {/* Step 2 of 3: Create Project */}
              {currentStep === 2 && (
                <form onSubmit={handleStep2Project}>
                  <div style={{ marginBottom: "18px" }}>
                    <span style={{ fontSize: "11px", color: "#34d399", fontFamily: "'DM Mono', monospace" }}>
                      STEP 2 OF 3
                    </span>
                    <h2 style={{ fontSize: "18px", fontWeight: "700", margin: "4px 0" }}>
                      Create your first Project
                    </h2>
                    <p style={{ fontSize: "12px", color: "#94a3b8", margin: 0 }}>
                      Belonging to organization: <strong style={{ color: "#ffffff" }}>{orgName}</strong>
                    </p>
                  </div>

                  <div style={{ display: "grid", gap: "16px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", color: "#cbd5e1", marginBottom: "6px" }}>
                        Project Name *
                      </label>
                      <input
                        type="text"
                        id="project-name-input"
                        placeholder="e.g. Production AI Platform"
                        value={projectName}
                        onChange={(e) => {
                          setProjectName(e.target.value);
                          if (!projectSlug) {
                            setProjectSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, "-"));
                          }
                        }}
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
                      <label style={{ display: "block", fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", color: "#cbd5e1", marginBottom: "6px" }}>
                        Project Slug
                      </label>
                      <input
                        type="text"
                        id="project-slug-input"
                        placeholder="e.g. production-ai-platform"
                        value={projectSlug}
                        onChange={(e) => setProjectSlug(e.target.value)}
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
                      <label style={{ display: "block", fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", color: "#cbd5e1", marginBottom: "6px" }}>
                        Description (Optional)
                      </label>
                      <textarea
                        rows={2}
                        placeholder="Autonomous agent workflows and infrastructure observability"
                        value={projectDescription}
                        onChange={(e) => setProjectDescription(e.target.value)}
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
                      id="step2-submit-btn"
                      style={{
                        padding: "12px",
                        background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "8px",
                        fontWeight: "700",
                        fontSize: "14px",
                        cursor: "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "8px",
                        marginTop: "8px",
                      }}
                    >
                      Continue to Environment Setup →
                    </button>
                  </div>
                </form>
              )}

              {/* Step 3 of 3: Create Environment */}
              {currentStep === 3 && (
                <form onSubmit={handleStep3Environment}>
                  <div style={{ marginBottom: "18px" }}>
                    <span style={{ fontSize: "11px", color: "#34d399", fontFamily: "'DM Mono', monospace" }}>
                      STEP 3 OF 3
                    </span>
                    <h2 style={{ fontSize: "18px", fontWeight: "700", margin: "4px 0" }}>
                      Configure your initial Environment
                    </h2>
                    <p style={{ fontSize: "12px", color: "#94a3b8", margin: 0 }}>
                      Scoping runtime agents, telemetry, and FinOps analytics.
                    </p>
                  </div>

                  <div style={{ display: "grid", gap: "16px" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", color: "#cbd5e1", marginBottom: "6px" }}>
                        Environment Name *
                      </label>
                      <input
                        type="text"
                        id="env-name-input"
                        placeholder="e.g. Production"
                        value={envName}
                        onChange={(e) => setEnvName(e.target.value)}
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
                      <label style={{ display: "block", fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", color: "#cbd5e1", marginBottom: "6px" }}>
                        Environment Type *
                      </label>
                      <select
                        id="env-type-select"
                        value={envType}
                        onChange={(e) => setEnvType(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "10px 12px",
                          borderRadius: "8px",
                          border: "1px solid rgba(255, 255, 255, 0.15)",
                          background: "#1e293b",
                          color: "#ffffff",
                          fontSize: "13px",
                          outline: "none",
                        }}
                      >
                        <option value="Production">Production</option>
                        <option value="Staging">Staging</option>
                        <option value="Development">Development</option>
                        <option value="QA">QA</option>
                        <option value="UAT">UAT</option>
                      </select>
                    </div>

                    <div>
                      <label style={{ display: "block", fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", color: "#cbd5e1", marginBottom: "6px" }}>
                        Description (Optional)
                      </label>
                      <textarea
                        rows={2}
                        placeholder="Primary operational environment with zero-trust guardrails"
                        value={envDescription}
                        onChange={(e) => setEnvDescription(e.target.value)}
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
                      id="step3-submit-btn"
                      disabled={isLoading}
                      style={{
                        padding: "12px",
                        background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                        color: "#ffffff",
                        border: "none",
                        borderRadius: "8px",
                        fontWeight: "700",
                        fontSize: "14px",
                        cursor: isLoading ? "wait" : "pointer",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        gap: "8px",
                        marginTop: "8px",
                      }}
                    >
                      {isLoading ? "Provisioning Hierarchy..." : "Complete Setup & Launch AgentOps →"}
                    </button>
                  </div>
                </form>
              )}

              {/* Step 4: Setup Complete */}
              {currentStep === 4 && (
                <div style={{ textAlign: "center", padding: "16px 0" }}>
                  <div
                    style={{
                      width: "60px",
                      height: "60px",
                      borderRadius: "50%",
                      background: "rgba(16, 185, 129, 0.2)",
                      border: "2px solid #10b981",
                      color: "#34d399",
                      fontSize: "28px",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      margin: "0 auto 16px",
                    }}
                  >
                    ✓
                  </div>
                  <h2 style={{ fontSize: "24px", fontWeight: "800", margin: "0 0 8px 0" }}>
                    Welcome to AgentOps!
                  </h2>
                  <p style={{ fontSize: "14px", color: "#94a3b8", maxWidth: "420px", margin: "0 auto 24px", lineHeight: 1.5 }}>
                    Your organization, project, and environment have been created and selected for this workspace.
                  </p>

                  <div
                    style={{
                      background: "rgba(255, 255, 255, 0.03)",
                      border: "1px solid rgba(255, 255, 255, 0.1)",
                      borderRadius: "10px",
                      padding: "16px",
                      textAlign: "left",
                      fontSize: "12px",
                      marginBottom: "24px",
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                      <span style={{ color: "#94a3b8" }}>Organization:</span>
                      <strong>{orgName}</strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                      <span style={{ color: "#94a3b8" }}>Project:</span>
                      <strong>{projectName}</strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px" }}>
                      <span style={{ color: "#94a3b8" }}>Environment:</span>
                      <strong style={{ color: "#34d399" }}>{envName} ({envType})</strong>
                    </div>
                    <div style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ color: "#94a3b8" }}>Your Role:</span>
                      <span style={{ background: "#f59e0b", color: "#1e293b", padding: "1px 6px", borderRadius: "4px", fontWeight: "800", fontSize: "10px" }}>
                        ORGANIZATION OWNER
                      </span>
                    </div>
                  </div>

                  <Link
                    href="/operations"
                    id="go-to-console-btn"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "8px",
                      padding: "14px 28px",
                      background: "linear-gradient(135deg, #10b981 0%, #059669 100%)",
                      color: "#ffffff",
                      borderRadius: "8px",
                      fontWeight: "700",
                      fontSize: "14px",
                      textDecoration: "none",
                      boxShadow: "0 4px 14px rgba(16, 185, 129, 0.35)",
                    }}
                  >
                    <span>Enter AgentOps Console</span>
                    <span>→</span>
                  </Link>
                </div>
              )}
            </>
          ) : (
            /* Mode: Join via Invitation */
            <div>
              {pendingInvitations.length > 0 ? (
                <div>
                  <h3 style={{ fontSize: "14px", fontWeight: "700", marginBottom: "12px" }}>
                    Pending Invitations for Your Account
                  </h3>
                  <div style={{ display: "grid", gap: "10px", marginBottom: "24px" }}>
                    {pendingInvitations.map((inv) => (
                      <div
                        key={inv.id}
                        style={{
                          border: "1px solid rgba(255, 255, 255, 0.12)",
                          borderRadius: "8px",
                          padding: "14px",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          background: "rgba(255, 255, 255, 0.03)",
                        }}
                      >
                        <div>
                          <div style={{ fontSize: "13px", fontWeight: "700" }}>
                            Organization: {inv.organization_id}
                          </div>
                          <div style={{ fontSize: "11px", color: "#94a3b8", marginTop: "3px" }}>
                            Assigned Role: <span style={{ color: "#34d399", fontWeight: "700" }}>{inv.role}</span>
                            {inv.project_id && ` · Project: ${inv.project_id}`}
                            {inv.environment_id && ` · Env: ${inv.environment_id}`}
                          </div>
                        </div>
                        <button
                          type="button"
                          className="btn btn-primary"
                          onClick={() => handleAcceptInvite(inv.token)}
                          disabled={isLoading}
                        >
                          Accept & Join
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div style={{ textAlign: "center", padding: "16px 0 20px" }}>
                  <p style={{ fontSize: "13px", color: "#94a3b8" }}>
                    No pending invitations were automatically detected for your email.
                  </p>
                </div>
              )}

              <div style={{ borderTop: "1px solid rgba(255, 255, 255, 0.1)", paddingTop: "20px" }}>
                <label style={{ display: "block", fontSize: "11px", fontWeight: "700", fontFamily: "'DM Mono', monospace", color: "#cbd5e1", marginBottom: "6px" }}>
                  Have an Invitation Token?
                </label>
                <div style={{ display: "flex", gap: "8px" }}>
                  <input
                    type="text"
                    placeholder="Paste secure invitation token..."
                    value={tokenInput}
                    onChange={(e) => setTokenInput(e.target.value)}
                    style={{
                      flex: 1,
                      padding: "10px 12px",
                      borderRadius: "8px",
                      border: "1px solid rgba(255, 255, 255, 0.15)",
                      background: "rgba(255, 255, 255, 0.05)",
                      color: "#ffffff",
                      fontSize: "13px",
                      outline: "none",
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => tokenInput && handleAcceptInvite(tokenInput.trim())}
                    disabled={!tokenInput.trim() || isLoading}
                    style={{
                      padding: "10px 18px",
                      background: "rgba(255, 255, 255, 0.1)",
                      border: "1px solid rgba(255, 255, 255, 0.2)",
                      borderRadius: "8px",
                      color: "#ffffff",
                      fontWeight: "600",
                      fontSize: "13px",
                      cursor: "pointer",
                    }}
                  >
                    Accept
                  </button>
                </div>
              </div>

              {existingOrgs.length > 0 && (
                <div style={{ marginTop: "24px", borderTop: "1px solid rgba(255, 255, 255, 0.1)", paddingTop: "20px" }}>
                  <h4 style={{ fontSize: "12px", fontWeight: "700", textTransform: "uppercase", color: "#94a3b8", marginBottom: "10px" }}>
                    Your Existing Organizations
                  </h4>
                  <div style={{ display: "grid", gap: "8px" }}>
                    {existingOrgs.map((org) => (
                      <div
                        key={org.id}
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          padding: "10px 14px",
                          background: "rgba(255, 255, 255, 0.03)",
                          border: "1px solid rgba(255, 255, 255, 0.08)",
                          borderRadius: "8px",
                        }}
                      >
                        <span style={{ fontWeight: "600" }}>{org.name}</span>
                        <button
                          type="button"
                          onClick={() => handleSelectExistingOrg(org)}
                          style={{
                            padding: "6px 12px",
                            background: "rgba(16, 185, 129, 0.15)",
                            border: "1px solid rgba(16, 185, 129, 0.3)",
                            borderRadius: "6px",
                            color: "#34d399",
                            fontSize: "12px",
                            fontWeight: "600",
                            cursor: "pointer",
                          }}
                        >
                          Select & Enter Console →
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "14px 32px",
            background: "rgba(255, 255, 255, 0.02)",
            borderTop: "1px solid rgba(255, 255, 255, 0.08)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "11px",
            color: "#64748b",
          }}
        >
          <span style={{ fontFamily: "'DM Mono', monospace" }}>
            Zero-Trust Tenancy Isolation Enforced
          </span>
          <Link href="/home" style={{ color: "#34d399", textDecoration: "none", fontWeight: "600" }}>
            Skip to Dashboard →
          </Link>
        </div>
      </div>
    </div>
  );
}
