"use client";

import { useWorkspace } from "../state/workspace-context";

export function HierarchySwitcher() {
  const {
    organizations,
    activeOrg,
    projects,
    activeProject,
    environments,
    activeEnvironment,
    setActiveOrg,
    setActiveProject,
    setActiveEnvironment,
    isLoading,
    workspaceError,
  } = useWorkspace();

  return (
    <section className="workspace-switcher" aria-label="Workspace scope">
      <div className="workspace-switcher-heading">
        <span className="eyebrow">Active context</span>
        <span className="workspace-role" aria-label={`Role: ${activeEnvironment?.role || activeProject?.role || activeOrg?.role || "Unavailable"}`}>
          {activeEnvironment?.role || activeProject?.role || activeOrg?.role || "No role"}
        </span>
      </div>
      <p className="workspace-path" aria-live="polite">
        <span>{activeOrg?.name || "Select organization"}</span>
        <span aria-hidden="true">›</span>
        <span>{activeProject?.name || "Select project"}</span>
        <span aria-hidden="true">›</span>
        <span>{activeEnvironment?.name || "Select environment"}</span>
      </p>
      <label className="workspace-field">
        <span>Organization</span>
        <select
          aria-label="Active organization"
          value={activeOrg?.id ?? ""}
          disabled={isLoading || organizations.length === 0}
          onChange={(event) => {
            const org = organizations.find((item) => item.id === event.target.value);
            if (org) void setActiveOrg(org);
          }}
        >
          <option value="" disabled>Select organization</option>
          {organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}
        </select>
      </label>
      <label className="workspace-field">
        <span>Project</span>
        <select
          aria-label="Active project"
          value={activeProject?.id ?? ""}
          disabled={isLoading || !activeOrg || projects.length === 0}
          onChange={(event) => {
            const project = projects.find((item) => item.id === event.target.value);
            if (project) void setActiveProject(project);
          }}
        >
          <option value="" disabled>{projects.length ? "Select project" : "No projects"}</option>
          {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
      </label>
      <label className="workspace-field">
        <span>Environment</span>
        <select
          aria-label="Active environment"
          value={activeEnvironment?.id ?? ""}
          disabled={isLoading || !activeProject || environments.length === 0}
          onChange={(event) => {
            const environment = environments.find((item) => item.id === event.target.value);
            if (environment) void setActiveEnvironment(environment);
          }}
        >
          <option value="" disabled>{environments.length ? "Select environment" : "No environments"}</option>
          {environments.map((environment) => (
            <option key={environment.id} value={environment.id}>{environment.name} · {environment.type}</option>
          ))}
        </select>
      </label>
      {workspaceError && <p className="workspace-switcher-error" role="alert">{workspaceError}</p>}
    </section>
  );
}
