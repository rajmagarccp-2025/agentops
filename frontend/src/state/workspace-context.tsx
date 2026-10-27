"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { createPermissionEngine, PermissionEngine } from "../lib/permissions";

export interface OrganizationItem {
  id: string;
  name: string;
  slug: string;
  description?: string;
  logo_url?: string;
  role: string;
  is_owner: boolean;
}

export interface ProjectItem {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description?: string;
  role: string;
  environments_count?: number;
}

export interface EnvironmentItem {
  id: string;
  project_id: string;
  organization_id: string;
  name: string;
  slug: string;
  type: string;
  role: string;
  description?: string;
}

export type MissingContextType = "organization" | "project" | "environment" | null;

interface WorkspaceContextValue {
  user: {
    subject: string;
    email: string;
    roles: string[];
    permissions?: string[];
    read_only_demo?: boolean;
    tenant_id: string;
    project_id?: string;
    environment_id?: string;
    display_name?: string;
  } | null;
  organizations: OrganizationItem[];
  activeOrg: OrganizationItem | null;
  currentOrg: OrganizationItem | null;
  projects: ProjectItem[];
  activeProject: ProjectItem | null;
  currentProject: ProjectItem | null;
  environments: EnvironmentItem[];
  activeEnvironment: EnvironmentItem | null;
  currentEnv: EnvironmentItem | null;
  effectiveRole: string;
  userEmail: string;
  permissions: PermissionEngine;
  isLoading: boolean;
  workspaceError: string | null;
  isContextComplete: boolean;
  missingContext: MissingContextType;
  setActiveOrg: (org: OrganizationItem) => Promise<boolean>;
  switchOrg: (orgId: string) => Promise<boolean>;
  setActiveProject: (proj: ProjectItem) => Promise<void>;
  switchProject: (projectId: string) => Promise<void>;
  setActiveEnvironment: (env: EnvironmentItem) => Promise<void>;
  switchEnvironment: (envId: string) => Promise<void>;
  refreshWorkspace: () => Promise<void>;
}

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

export function WorkspaceProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<{
    subject: string;
    email: string;
    roles: string[];
    permissions?: string[];
    read_only_demo?: boolean;
    tenant_id: string;
    project_id?: string;
    environment_id?: string;
    display_name?: string;
  } | null>(null);
  const [organizations, setOrganizations] = useState<OrganizationItem[]>([]);
  const [activeOrg, setActiveOrgState] = useState<OrganizationItem | null>(null);
  const [projects, setProjects] = useState<ProjectItem[]>([]);
  const [activeProject, setActiveProjectState] = useState<ProjectItem | null>(null);
  const [environments, setEnvironments] = useState<EnvironmentItem[]>([]);
  const [activeEnvironment, setActiveEnvironmentState] = useState<EnvironmentItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [workspaceError, setWorkspaceError] = useState<string | null>(null);

  useEffect(() => {
    fetchSessionAndOrgs();
  }, []);

  const syncBackendContext = async (orgId: string, projId?: string | null, envId?: string | null) => {
    const response = await fetch("/api/auth/switch-context", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        organization_id: orgId,
        project_id: projId || undefined,
        environment_id: envId || undefined,
      }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(
        typeof body?.error === "string"
          ? body.error
          : typeof body?.detail === "string"
            ? body.detail
            : `Unable to switch workspace context (${response.status}).`,
      );
    }
  };

  const fetchSessionAndOrgs = async () => {
    setIsLoading(true);
    setWorkspaceError(null);
    try {
      const sessionRes = await fetch("/api/auth/session");
      if (!sessionRes.ok) {
        if (sessionRes.status !== 401) {
          throw new Error(`Unable to verify your session (${sessionRes.status}).`);
        }
        setUser(null);
        setOrganizations([]);
        setActiveOrgState(null);
        setProjects([]);
        setActiveProjectState(null);
        setEnvironments([]);
        setActiveEnvironmentState(null);
        return;
      }
      const sessionData = await sessionRes.json();
      if (sessionData.authenticated && sessionData.user) {
        setUser(sessionData.user);

        const orgsRes = await fetch("/api/proxy/organizations");
        if (!orgsRes.ok) {
          throw new Error(`Unable to load your organizations (${orgsRes.status}).`);
        }
        const orgsData: OrganizationItem[] = await orgsRes.json();
        setOrganizations(orgsData);

        if (orgsData.length > 0) {
          const savedOrgId = typeof window !== "undefined" ? localStorage.getItem("agentops_active_org") : null;
          const matchedOrg =
            (savedOrgId && orgsData.find((o) => o.id === savedOrgId)) ||
            orgsData.find((o) => o.id === sessionData.user.tenant_id || o.slug === sessionData.user.tenant_id) ||
            orgsData[0];

          await syncBackendContext(matchedOrg.id);
          setActiveOrgState(matchedOrg);
          if (typeof window !== "undefined") {
            localStorage.setItem("agentops_active_org", matchedOrg.id);
          }
          await loadProjectsForOrg(matchedOrg.id, sessionData.user.project_id, sessionData.user.environment_id);
        } else {
          setActiveOrgState(null);
          setProjects([]);
          setEnvironments([]);
          setActiveProjectState(null);
          setActiveEnvironmentState(null);
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Unable to load workspace context.";
      if (!msg.toLowerCase().includes("tenant context")) {
        setWorkspaceError(msg);
      }
    } finally {
      setIsLoading(false);
    }
  };

  const loadProjectsForOrg = async (orgId: string, preferredProjId?: string | null, preferredEnvId?: string | null) => {
    const projRes = await fetch(`/api/proxy/organizations/${orgId}/projects`);
    if (!projRes.ok) {
      throw new Error(`Unable to load projects (${projRes.status}).`);
    }
    const projData: ProjectItem[] = await projRes.json();
    setProjects(projData);

    if (projData.length > 0) {
      const savedProjId = typeof window !== "undefined" ? localStorage.getItem(`agentops_proj_${orgId}`) : null;
      const matchedProj =
        (savedProjId && projData.find((p) => p.id === savedProjId)) ||
        (preferredProjId && projData.find((p) => p.id === preferredProjId)) ||
        projData[0];

      await syncBackendContext(orgId, matchedProj.id);
      setActiveProjectState(matchedProj);
      if (typeof window !== "undefined") {
        localStorage.setItem(`agentops_proj_${orgId}`, matchedProj.id);
      }
      await loadEnvironmentsForProject(orgId, matchedProj.id, preferredEnvId);
    } else {
      setActiveProjectState(null);
      setEnvironments([]);
      setActiveEnvironmentState(null);
    }
  };

  const loadEnvironmentsForProject = async (orgId: string, projectId: string, preferredEnvId?: string | null) => {
    const envRes = await fetch(`/api/proxy/projects/${projectId}/environments`);
    if (!envRes.ok) {
      throw new Error(`Unable to load environments (${envRes.status}).`);
    }
    const envData: EnvironmentItem[] = await envRes.json();
    setEnvironments(envData);
    if (envData.length > 0) {
      const savedEnvId = typeof window !== "undefined" ? localStorage.getItem(`agentops_env_${projectId}`) : null;
      const matchedEnv =
        (savedEnvId && envData.find((e) => e.id === savedEnvId)) ||
        (preferredEnvId && envData.find((e) => e.id === preferredEnvId)) ||
        envData.find((e) => e.type === "Production") ||
        envData[0];

      await syncBackendContext(orgId, projectId, matchedEnv.id);
      setActiveEnvironmentState(matchedEnv);
      if (typeof window !== "undefined") {
        localStorage.setItem(`agentops_env_${projectId}`, matchedEnv.id);
      }
    } else {
      setActiveEnvironmentState(null);
      await syncBackendContext(orgId, projectId);
    }
  };

  const setActiveOrg = async (org: OrganizationItem) => {
    setWorkspaceError(null);
    setIsLoading(true);
    try {
      await syncBackendContext(org.id);
      setActiveOrgState(org);
      setActiveProjectState(null);
      setActiveEnvironmentState(null);
      setProjects([]);
      setEnvironments([]);
      if (typeof window !== "undefined") {
        localStorage.setItem("agentops_active_org", org.id);
      }
      await loadProjectsForOrg(org.id);
      return true;
    } catch (err) {
      setWorkspaceError(err instanceof Error ? err.message : "Unable to switch organization.");
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const switchOrg = async (orgId: string): Promise<boolean> => {
    const found = organizations.find((o) => o.id === orgId);
    if (found) {
      return await setActiveOrg(found);
    }
    return false;
  };

  const setActiveProject = async (proj: ProjectItem) => {
    if (!activeOrg || proj.organization_id !== activeOrg.id) {
      setWorkspaceError("Project is not available in the active organization.");
      return;
    }
    setWorkspaceError(null);
    setIsLoading(true);
    try {
      await syncBackendContext(activeOrg.id, proj.id);
      setActiveProjectState(proj);
      setActiveEnvironmentState(null);
      setEnvironments([]);
      if (typeof window !== "undefined") {
        localStorage.setItem(`agentops_proj_${activeOrg.id}`, proj.id);
      }
      await loadEnvironmentsForProject(activeOrg.id, proj.id);
    } catch (err) {
      setWorkspaceError(err instanceof Error ? err.message : "Unable to switch project.");
    } finally {
      setIsLoading(false);
    }
  };

  const switchProject = async (projectId: string) => {
    const found = projects.find((p) => p.id === projectId);
    if (found) {
      await setActiveProject(found);
    }
  };

  const setActiveEnvironment = async (env: EnvironmentItem) => {
    if (
      !activeOrg ||
      !activeProject ||
      env.organization_id !== activeOrg.id ||
      env.project_id !== activeProject.id
    ) {
      setWorkspaceError("Environment is not available in the active project.");
      return;
    }
    setWorkspaceError(null);
    setIsLoading(true);
    try {
      await syncBackendContext(activeOrg.id, activeProject.id, env.id);
      setActiveEnvironmentState(env);
      if (typeof window !== "undefined") {
        localStorage.setItem(`agentops_env_${activeProject.id}`, env.id);
      }
    } catch (err) {
      setWorkspaceError(err instanceof Error ? err.message : "Unable to switch environment.");
    } finally {
      setIsLoading(false);
    }
  };

  const switchEnvironment = async (envId: string) => {
    const found = environments.find((e) => e.id === envId);
    if (found) {
      await setActiveEnvironment(found);
    }
  };

  const isContextComplete = Boolean(activeOrg && activeProject && activeEnvironment);
  const missingContext: MissingContextType = !activeOrg
    ? "organization"
    : !activeProject
    ? "project"
    : !activeEnvironment
    ? "environment"
    : null;

  const effectiveRole =
    activeEnvironment?.role ||
    activeProject?.role ||
    activeOrg?.role ||
    user?.roles?.[0] ||
    "READ";

  const permissions = createPermissionEngine({
    role: effectiveRole,
    roles: user?.roles,
    permissions: user?.permissions,
    is_owner: activeOrg?.is_owner,
    read_only_demo: user?.read_only_demo,
  });

  return (
    <WorkspaceContext.Provider
      value={{
        user,
        organizations,
        activeOrg,
        currentOrg: activeOrg,
        projects,
        activeProject,
        currentProject: activeProject,
        environments,
        activeEnvironment,
        currentEnv: activeEnvironment,
        effectiveRole,
        userEmail: user?.email || "",
        permissions,
        isLoading,
        workspaceError,
        isContextComplete,
        missingContext,
        setActiveOrg,
        switchOrg,
        setActiveProject,
        switchProject,
        setActiveEnvironment,
        switchEnvironment,
        refreshWorkspace: fetchSessionAndOrgs,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspace must be used within a WorkspaceProvider");
  }
  return context;
}
