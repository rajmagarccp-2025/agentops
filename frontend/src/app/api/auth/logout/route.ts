import { NextRequest, NextResponse } from "next/server";

export async function POST(_request: NextRequest) {
  const keycloakUrl = process.env.KEYCLOAK_BASE_URL || "http://localhost:8080";
  const realm = process.env.KEYCLOAK_REALM || "agentops";
  const clientId = process.env.KEYCLOAK_CLIENT_ID || "agentops-web";
  const postLogoutRedirectUri = process.env.NEXTAUTH_LOGOUT_REDIRECT_URI || "http://localhost:3000/";

  const keycloakLogoutUrl = `${keycloakUrl}/realms/${realm}/protocol/openid-connect/logout?client_id=${encodeURIComponent(
    clientId
  )}&post_logout_redirect_uri=${encodeURIComponent(postLogoutRedirectUri)}`;

  const response = NextResponse.json({
    success: true,
    redirect_url: process.env.KEYCLOAK_BASE_URL ? keycloakLogoutUrl : "/",
  });

  // Clear all platform auth cookies
  response.cookies.delete("platform_access_token");
  response.cookies.delete("platform_refresh_token");
  response.cookies.delete("platform_session");
  response.cookies.delete("oidc_code_verifier");
  response.cookies.delete("oidc_auth_state");

  return response;
}

export async function GET(request: NextRequest) {
  const keycloakUrl = process.env.KEYCLOAK_BASE_URL || "http://localhost:8080";
  const realm = process.env.KEYCLOAK_REALM || "agentops";
  const clientId = process.env.KEYCLOAK_CLIENT_ID || "agentops-web";
  const postLogoutRedirectUri = new URL("/", request.url).toString();

  const logoutRedirect = process.env.KEYCLOAK_BASE_URL
    ? `${keycloakUrl}/realms/${realm}/protocol/openid-connect/logout?client_id=${encodeURIComponent(
        clientId
      )}&post_logout_redirect_uri=${encodeURIComponent(postLogoutRedirectUri)}`
    : new URL("/", request.url).toString();

  const response = NextResponse.redirect(logoutRedirect);

  // Clear all platform auth cookies
  response.cookies.delete("platform_access_token");
  response.cookies.delete("platform_refresh_token");
  response.cookies.delete("platform_session");
  response.cookies.delete("oidc_code_verifier");
  response.cookies.delete("oidc_auth_state");

  return response;
}

