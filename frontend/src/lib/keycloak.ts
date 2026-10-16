import Keycloak from "keycloak-js";

// Preferred environment variables or default fallbacks as specified
const keycloakUrl =
  process.env.NEXT_PUBLIC_KEYCLOAK_URL ||
  process.env.VITE_KEYCLOAK_URL ||
  "http://localhost:8080";

const keycloakRealm =
  process.env.NEXT_PUBLIC_KEYCLOAK_REALM ||
  process.env.VITE_KEYCLOAK_REALM ||
  "agent-ops";

const keycloakClientId =
  process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID ||
  process.env.VITE_KEYCLOAK_CLIENT_ID ||
  "agent-ops-frontend";

const keycloakConfig = {
  url: keycloakUrl,
  realm: keycloakRealm,
  clientId: keycloakClientId,
};

let keycloakInstance: Keycloak | null = null;
let initPromise: Promise<boolean> | null = null;

export function getKeycloakInstance(): Keycloak {
  if (typeof window === "undefined") {
    return {} as Keycloak;
  }
  if (!keycloakInstance) {
    keycloakInstance = new Keycloak(keycloakConfig);
  }
  return keycloakInstance;
}

export function initKeycloak(): Promise<boolean> {
  if (typeof window === "undefined") {
    return Promise.resolve(false);
  }
  if (initPromise) {
    return initPromise;
  }

  const instance = getKeycloakInstance();
  initPromise = instance
    .init({
      onLoad: "check-sso",
      pkceMethod: "S256",
      silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
    })
    .catch((err) => {
      console.error("Keycloak initialization failed gracefully:", err);
      return false;
    });

  return initPromise;
}

export const login = (redirectUri?: string): Promise<void> => {
  const instance = getKeycloakInstance();
  return instance.login({
    redirectUri: redirectUri || window.location.origin,
  });
};

export const logout = (redirectUri?: string): Promise<void> => {
  const instance = getKeycloakInstance();
  return instance.logout({
    redirectUri: redirectUri || window.location.origin,
  });
};

export const isAuthenticated = (): boolean => {
  const instance = getKeycloakInstance();
  return Boolean(instance.authenticated);
};

export const getToken = (): string | undefined => {
  const instance = getKeycloakInstance();
  return instance.token;
};

export const updateToken = (minValidity: number = 30): Promise<boolean> => {
  const instance = getKeycloakInstance();
  if (!instance.authenticated) {
    return Promise.resolve(false);
  }
  return instance.updateToken(minValidity).catch((err) => {
    console.error("Failed to update Keycloak token:", err);
    return false;
  });
};
