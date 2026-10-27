"use client";

import React from "react";
import { WorkspaceProvider } from "../state/workspace-context";
import { KeycloakAuthProvider } from "../state/keycloak-context";
import { DemoTopBanner } from "./demo-top-banner";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <KeycloakAuthProvider>
      <WorkspaceProvider>
        <DemoTopBanner />
        {children}
      </WorkspaceProvider>
    </KeycloakAuthProvider>
  );
}
