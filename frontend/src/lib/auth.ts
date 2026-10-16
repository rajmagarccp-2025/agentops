export type AuthSession = {
  userId: string;
  displayName: string;
  tenantId: string;
  roles: string[];
};

export interface AuthProvider {
  getSession(): Promise<AuthSession | null>;
  signOut(): Promise<void>;
}

export class OidcAuthProvider implements AuthProvider {
  async getSession(): Promise<AuthSession | null> {
    return null;
  }

  async signOut(): Promise<void> {
    return Promise.resolve();
  }
}
