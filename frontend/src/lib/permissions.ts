"use client";

export type PlatformRole = "ADMIN" | "WRITE" | "READ" | "OWNER" | "platform-admin" | "operator" | "developer" | "viewer" | string;

export interface UserSessionContext {
  subject: string;
  email: string;
  role: PlatformRole;
  roles: string[];
  permissions: string[];
  tenant_id: string;
  organization_id?: string;
  project_id?: string;
  environment_id?: string;
  is_owner?: boolean;
}

const ROLE_ALIASES: Record<string, string> = {
  DEVELOPER: "DEVELOPER",
  READER: "READ",
  MEMBER: "WRITE",
  OPERATOR: "WRITE",
  "PROJECT MEMBER": "WRITE",
  PROJECT_MEMBER: "WRITE",
  "ENVIRONMENT OPERATOR": "WRITE",
  ENVIRONMENT_OPERATOR: "WRITE",
  VIEWER: "READ",
  "PROJECT VIEWER": "READ",
  PROJECT_VIEWER: "READ",
  "ENVIRONMENT VIEWER": "READ",
  ENVIRONMENT_VIEWER: "READ",
  "PROJECT ADMIN": "ADMIN",
  PROJECT_ADMIN: "ADMIN",
  "ENVIRONMENT ADMIN": "ADMIN",
  ENVIRONMENT_ADMIN: "ADMIN",
  "PLATFORM-ADMIN": "ADMIN",
};

function normalizeRole(role: string): string {
  const normalized = role.trim().toUpperCase();
  return ROLE_ALIASES[normalized] ?? normalized;
}

export const ROLE_PERMISSIONS: Record<string, string[]> = {
  ADMIN: [
    "organization.read", "organization.write", "organization.update", "organization.delete",
    "member.read", "member.invite", "member.remove", "member.role_change",
    "project.read", "project.create", "project.update", "project.delete", "project.manage", "project.member_manage",
    "environment.read", "environment.create", "environment.update", "environment.delete", "environment.manage", "environment.member_manage",
    "agents.read", "agents.run",
    "data.read", "data.write",
    "ai.read", "ai.query", "ai.execute", "ai.admin",
    "audit.read",
    "incidents.read", "incidents.write", "incidents.investigate",
    "inventory.read", "finops.read", "finops.write", "changes.read", "changes.write",
    "remediation.read", "remediation.execute", "remediation.verify",
    "rag.read", "rag.write", "llm.read", "llm.invoke", "llm.write", "llm.evaluate",
    "learning.read", "learning.write", "approvals.read", "approvals.approve",
    "security.read", "security.write", "security.investigate", "governance.manage",
    "cloud.read", "cloud.manage", "observability.read",
  ],
  WRITE: [
    "organization.read",
    "project.read", "environment.read",
    "environment.create",
    "agents.read", "agents.run",
    "data.read", "data.write",
    "ai.read", "ai.query", "ai.execute", "rag.read", "rag.write",
    "incidents.read", "incidents.write", "incidents.investigate",
    "inventory.read", "finops.read", "finops.write", "changes.read", "changes.write",
    "remediation.read", "remediation.execute", "remediation.verify",
    "llm.read", "llm.invoke", "llm.write", "learning.read", "learning.write",
    "cloud.read", "observability.read",
    "dashboard.read", "report.read",
  ],
  DEVELOPER: [
    "organization.read",
    "project.read", "environment.read",
    "environment.create",
    "agents.read", "agents.run",
    "data.read", "data.write",
    "ai.read", "ai.query", "ai.execute", "rag.read", "rag.write",
    "incidents.read", "incidents.write", "incidents.investigate",
    "inventory.read", "finops.read", "finops.write", "changes.read", "changes.write",
    "remediation.read", "remediation.execute", "remediation.verify",
    "llm.read", "llm.invoke", "llm.write", "learning.read", "learning.write",
    "cloud.read", "observability.read",
    "dashboard.read", "report.read",
  ],
  READ: [
    "organization.read",
    "project.read",
    "environment.read",
    "agents.read", "rag.read", "tools.read", "tools:read",
    "data.read",
    "secrets.metadata.read", "secrets:metadata:read",
    "dashboard.read", "report.read",
    "ai.read", "incidents.read", "inventory.read", "finops.read", "changes.read",
    "remediation.read", "llm.read", "learning.read", "cloud.read", "observability.read",
  ],
  READER: [
    "organization.read",
    "project.read",
    "environment.read",
    "agents.read", "rag.read",
    "data.read",
    "dashboard.read", "report.read",
    "ai.read", "incidents.read", "inventory.read", "finops.read", "changes.read",
    "remediation.read", "llm.read", "learning.read", "cloud.read", "observability.read",
  ],
  OWNER: [
    "organization.read", "organization.write", "organization.update", "organization.delete",
    "member.read", "member.invite", "member.remove", "member.role_change",
    "project.read", "project.create", "project.update", "project.delete", "project.manage", "project.member_manage",
    "environment.read", "environment.create", "environment.update", "environment.delete", "environment.manage", "environment.member_manage",
    "agents.read", "agents.run",
    "data.read", "data.write",
    "ai.read", "ai.query", "ai.execute", "ai.admin",
    "audit.read",
    "organization.transfer_ownership",
    "incidents.read", "incidents.write", "incidents.investigate",
    "inventory.read", "finops.read", "finops.write", "changes.read", "changes.write",
    "remediation.read", "remediation.execute", "remediation.verify",
    "rag.read", "rag.write", "llm.read", "llm.invoke", "llm.write", "llm.evaluate",
    "learning.read", "learning.write", "approvals.read", "approvals.approve",
    "security.read", "security.write", "security.investigate", "governance.manage",
    "cloud.read", "cloud.manage", "observability.read",
  ],
};

export class PermissionEngine {
  private userRole: string;
  private customPermissions: Set<string>;
  private isOwner: boolean;
  private isReadOnlyDemo: boolean;

  constructor(session?: { role?: string; roles?: string[]; permissions?: string[]; is_owner?: boolean; read_only_demo?: boolean }) {
    this.userRole = normalizeRole(session?.role || session?.roles?.[0] || "READ");
    this.isOwner = Boolean(session?.is_owner);
    this.isReadOnlyDemo = Boolean(session?.read_only_demo);

    const basePermissions = ROLE_PERMISSIONS[this.userRole] || ROLE_PERMISSIONS.READ;
    this.customPermissions = new Set(basePermissions);

    if (this.isReadOnlyDemo) {
      ["security.read", "security:read", "audit.read", "audit:read"].forEach((permission) =>
        this.customPermissions.add(permission),
      );
    }

    // Merge any explicit permissions
    if (session?.permissions && !this.isReadOnlyDemo) {
      session.permissions.forEach((p) => this.customPermissions.add(p));
    }

    // Platform-admin bypass
    if (session?.roles?.includes("platform-admin") || this.userRole === "PLATFORM-ADMIN") {
      this.customPermissions = new Set(ROLE_PERMISSIONS.ADMIN);
    }
  }

  hasPermission(permission: string): boolean {
    const dotted = permission.replace(":", ".");
    const coloned = permission.replace(".", ":");
    const action = permission.split(/[.:]/).at(-1)?.toLowerCase();
    if (this.isReadOnlyDemo && action !== "read") {
      return false;
    }
    return (
      this.isOwner ||
      this.customPermissions.has(dotted) ||
      this.customPermissions.has(coloned) ||
      this.userRole === "ADMIN" ||
      this.userRole === "OWNER" ||
      this.userRole === "PLATFORM-ADMIN"
    );
  }

  canView(_resource?: string): boolean {
    return this.hasPermission("data.read") || this.hasPermission("project.read") || this.hasPermission("environment.read");
  }

  canWrite(_resource?: string): boolean {
    return [
      "rag:write", "agents:run", "incidents:write", "finops:write",
      "changes:write", "remediation:execute", "llm:write", "learning:write",
    ].some((permission) => this.hasPermission(permission));
  }

  canManageMembers(_resource?: string): boolean {
    return !this.isReadOnlyDemo && (
      this.hasPermission("member.invite") || this.hasPermission("member.remove") || this.userRole === "ADMIN"
    );
  }

  canManageProject(_resource?: string): boolean {
    return !this.isReadOnlyDemo && (
      this.hasPermission("project.manage") || this.hasPermission("project.create") || this.userRole === "ADMIN"
    );
  }

  canManageEnvironment(_resource?: string): boolean {
    return !this.isReadOnlyDemo && (
      this.hasPermission("environment.manage") || this.hasPermission("environment.create") || this.userRole === "ADMIN"
    );
  }

  canAskAI(_resource?: string): boolean {
    return !this.isReadOnlyDemo && this.hasPermission("ai.query") && this.userRole !== "READ";
  }

  canDeleteProject(_resource?: string): boolean {
    return !this.isReadOnlyDemo && (
      this.hasPermission("project.delete") || this.userRole === "ADMIN"
    );
  }

  canDeleteOrganization(_resource?: string): boolean {
    return !this.isReadOnlyDemo && this.isOwner;
  }

  canManageOrganization(_resource?: string): boolean {
    return !this.isReadOnlyDemo && (
      this.hasPermission("organization.write") || this.isOwner || this.userRole === "ADMIN" || this.userRole === "OWNER"
    );
  }
}

export function createPermissionEngine(session?: { role?: string; roles?: string[]; permissions?: string[]; is_owner?: boolean; read_only_demo?: boolean }) {
  return new PermissionEngine(session);
}

export function canManageMembers(roleOrEngine?: string | PermissionEngine): boolean {
  if (!roleOrEngine) return false;
  if (typeof roleOrEngine === "string") {
    return createPermissionEngine({ role: roleOrEngine }).canManageMembers();
  }
  return roleOrEngine.canManageMembers();
}

export function canManageOrganization(roleOrEngine?: string | PermissionEngine): boolean {
  if (!roleOrEngine) return false;
  if (typeof roleOrEngine === "string") {
    return createPermissionEngine({ role: roleOrEngine }).canManageOrganization();
  }
  return roleOrEngine.canManageOrganization();
}

export function canManageProject(roleOrEngine?: string | PermissionEngine): boolean {
  if (!roleOrEngine) return false;
  if (typeof roleOrEngine === "string") {
    return createPermissionEngine({ role: roleOrEngine }).canManageProject();
  }
  return roleOrEngine.canManageProject();
}

export function canManageEnvironment(roleOrEngine?: string | PermissionEngine): boolean {
  if (!roleOrEngine) return false;
  if (typeof roleOrEngine === "string") {
    return createPermissionEngine({ role: roleOrEngine }).canManageEnvironment();
  }
  return roleOrEngine.canManageEnvironment();
}

export function canAskAI(roleOrEngine?: string | PermissionEngine): boolean {
  if (!roleOrEngine) return false;
  if (typeof roleOrEngine === "string") {
    return createPermissionEngine({ role: roleOrEngine }).canAskAI();
  }
  return roleOrEngine.canAskAI();
}

export function canView(_roleOrEngine?: string | PermissionEngine): boolean {
  if (!_roleOrEngine) return false;
  if (typeof _roleOrEngine === "string") {
    return createPermissionEngine({ role: _roleOrEngine }).canView();
  }
  return _roleOrEngine.canView();
}

export function canWrite(roleOrEngine?: string | PermissionEngine): boolean {
  if (!roleOrEngine) return false;
  if (typeof roleOrEngine === "string") {
    return createPermissionEngine({ role: roleOrEngine }).canWrite();
  }
  return roleOrEngine.canWrite();
}
