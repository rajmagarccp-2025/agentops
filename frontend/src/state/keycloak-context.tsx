"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import Keycloak from "keycloak-js";
import {
  getKeycloakInstance,
  initKeycloak,
  login as kcLogin,
  logout as kcLogout,
  getToken as kcGetToken,
  updateToken as kcUpdateToken,
} from "../lib/keycloak";

export interface KeycloakUserInfo {
  sub?: string;
  email?: string;
  name?: string;
  preferred_username?: string;
  given_name?: string;
  family_name?: string;
  roles?: string[];
  [key: string]: unknown;
}

interface KeycloakAuthContextValue {
  isAuthenticated: boolean;
  isInitialized: boolean;
  user: KeycloakUserInfo | null;
  token: string | undefined;
  keycloak: Keycloak | null;
  error: string | null;
  login: (redirectUri?: string) => Promise<void>;
  logout: (redirectUri?: string) => Promise<void>;
  getToken: () => string | undefined;
  updateToken: (minValidity?: number) => Promise<boolean>;
}

const KeycloakAuthContext = createContext<KeycloakAuthContextValue | undefined>(undefined);

export function KeycloakAuthProvider({ children }: { children: React.ReactNode }) {
  const [isInitialized, setIsInitialized] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState<KeycloakUserInfo | null>(null);
  const [token, setToken] = useState<string | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [kcInstance, setKcInstance] = useState<Keycloak | null>(null);

  useEffect(() => {
    let isMounted = true;
    const kc = getKeycloakInstance();
    setKcInstance(kc);

    initKeycloak()
      .then((auth) => {
        if (!isMounted) return;
        setAuthenticated(Boolean(auth));
        setIsInitialized(true);

        if (auth && kc.token) {
          setToken(kc.token);
          if (kc.tokenParsed) {
            const parsed = kc.tokenParsed as Record<string, unknown>;
            const realmAccess = parsed.realm_access as { roles?: string[] } | undefined;
            setUser({
              sub: parsed.sub as string,
              email: parsed.email as string,
              name: parsed.name as string,
              preferred_username: parsed.preferred_username as string,
              given_name: parsed.given_name as string,
              family_name: parsed.family_name as string,
              roles: realmAccess?.roles || [],
              ...parsed,
            });
          }
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        console.error("Keycloak auth provider initialization failed:", err);
        setError("Failed to initialize Keycloak identity provider.");
        setIsInitialized(true);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleLogin = async (redirectUri?: string) => {
    try {
      await kcLogin(redirectUri);
    } catch (err) {
      console.error("Keycloak login error:", err);
      setError("Login failed. Please try again.");
    }
  };

  const handleLogout = async (redirectUri?: string) => {
    try {
      await kcLogout(redirectUri);
    } catch (err) {
      console.error("Keycloak logout error:", err);
      setError("Logout failed. Please try again.");
    }
  };

  const value: KeycloakAuthContextValue = {
    isAuthenticated: authenticated,
    isInitialized,
    user,
    token,
    keycloak: kcInstance,
    error,
    login: handleLogin,
    logout: handleLogout,
    getToken: () => kcGetToken() || token,
    updateToken: kcUpdateToken,
  };

  return (
    <KeycloakAuthContext.Provider value={value}>
      {children}
    </KeycloakAuthContext.Provider>
  );
}

export function useKeycloakAuth(): KeycloakAuthContextValue {
  const context = useContext(KeycloakAuthContext);
  if (!context) {
    throw new Error("useKeycloakAuth must be used within a KeycloakAuthProvider");
  }
  return context;
}
