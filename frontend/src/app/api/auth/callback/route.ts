import { NextRequest, NextResponse } from "next/server";

function isSecureRequest(request: NextRequest): boolean {
  const proto = request.headers.get("x-forwarded-proto") || request.nextUrl.protocol;
  return proto.includes("https");
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");
  const state = searchParams.get("state");
  const error = searchParams.get("error");
  const errorDescription = searchParams.get("error_description");

  if (error) {
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(errorDescription || error)}`, request.url)
    );
  }

  const storedState = request.cookies.get("oidc_auth_state")?.value;
  const codeVerifier = request.cookies.get("oidc_code_verifier")?.value;

  if (!code || !state || !storedState || state !== storedState || !codeVerifier) {
    return NextResponse.redirect(
      new URL("/login?error=invalid_state_or_missing_verifier", request.url)
    );
  }

  const keycloakUrl =
    process.env.KEYCLOAK_URL ||
    process.env.KEYCLOAK_BASE_URL ||
    process.env.NEXT_PUBLIC_KEYCLOAK_URL ||
    "http://localhost:8080";
  const internalKeycloakUrl = process.env.INTERNAL_KEYCLOAK_URL || keycloakUrl;
  const realm =
    process.env.KEYCLOAK_REALM || process.env.NEXT_PUBLIC_KEYCLOAK_REALM || "agentops";
  const clientId =
    process.env.KEYCLOAK_CLIENT_ID || process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID || "agentops-web";
  const redirectUri =
    process.env.KEYCLOAK_REDIRECT_URI ||
    process.env.NEXTAUTH_REDIRECT_URI ||
    "http://localhost:3000/api/auth/callback";

  try {
    const tokenEndpoint = `${internalKeycloakUrl}/realms/${realm}/protocol/openid-connect/token`;
    const tokenParams = new URLSearchParams({
      grant_type: "authorization_code",
      client_id: clientId,
      code,
      redirect_uri: redirectUri,
      code_verifier: codeVerifier,
    });

    const tokenRes = await fetch(tokenEndpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: tokenParams.toString(),
      cache: "no-store",
    });

    if (!tokenRes.ok) {
      const errBody = await tokenRes.text();
      return NextResponse.redirect(
        new URL(`/login?error=token_exchange_failed&details=${encodeURIComponent(errBody)}`, request.url)
      );
    }

    const tokenData = await tokenRes.json();
    const accessToken = tokenData.access_token;
    const refreshToken = tokenData.refresh_token;
    const expiresIn = tokenData.expires_in || 1800;

    let claims: Record<string, unknown> = {};
    if (accessToken) {
      try {
        const parts = accessToken.split(".");
        if (parts.length === 3) {
          claims = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf-8")) as Record<string, unknown>;
        }
      } catch {
        // ignore parse error
      }
    }

    const subject = (claims.sub as string) || "keycloak-user";
    const email = (claims.email as string) || (claims.preferred_username as string) || "user@enterprise.com";
    const realmAccess = claims.realm_access as { roles?: string[] } | undefined;
    const keycloakRoles = realmAccess?.roles || (claims.roles as string[]) || ["READ"];

    // 6 & 7: Verify and synchronize principal context with FastAPI backend
    const backendBaseUrl =
      process.env.INTERNAL_API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://localhost:8000/api/v1";

    const rawMemberships = claims.tenant_memberships as Array<{ tenant_id: string; roles: string[] }> | undefined;
    const claimTenant = (claims.tenant_id as string) || (rawMemberships?.[0]?.tenant_id) || "";

    let userSession = {
      subject,
      email,
      roles: keycloakRoles,
      tenant_id: claimTenant,
      tenant_memberships: rawMemberships || [],
      has_organization: Boolean(claimTenant),
      read_only_demo: false,
      expires_at: Date.now() + expiresIn * 1000,
    };

    try {
      // Validate the genuine Keycloak token directly with backend /auth/me
      const backendRes = await fetch(`${backendBaseUrl}/auth/me`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${accessToken}`,
          "Accept": "application/json",
        },
        cache: "no-store",
      });

      if (backendRes.ok) {
        const principalData = await backendRes.json();
        userSession = {
          subject: principalData.subject || subject,
          email: principalData.email || email,
          roles: principalData.roles || keycloakRoles,
          tenant_id: principalData.tenant_id || claimTenant,
          tenant_memberships: principalData.tenant_memberships || rawMemberships || [],
          has_organization: Boolean(principalData.tenant_id || claimTenant),
          read_only_demo: false,
          expires_at: Date.now() + expiresIn * 1000,
        };
      }
    } catch {
      // Fallback to Keycloak claims if backend call is deferred
    }

    const validationResponse = await fetch(`${backendBaseUrl}/onboarding/status`, {
      method: "GET",
      headers: {
          "Authorization": `Bearer ${accessToken}`,
        "Accept": "application/json",
      },
      cache: "no-store",
    });
    if (!validationResponse.ok) {
      return NextResponse.redirect(new URL("/login?error=session_validation_failed", request.url));
    }
    const onboardingStatus = await validationResponse.json();
    const organizations = Array.isArray(onboardingStatus.organizations) ? onboardingStatus.organizations : [];
    const resolvedTenant = organizations.some((org: { id?: string }) => org.id === claims.tenant_id)
      ? String(claims.tenant_id)
      : organizations[0]?.id || "";
    userSession = {
      subject: onboardingStatus.user?.subject || subject,
      email: onboardingStatus.user?.email || email,
      roles: keycloakRoles,
      tenant_id: resolvedTenant,
      tenant_memberships: rawMemberships || [],
      has_organization: organizations.length > 0,
      read_only_demo: false,
      expires_at: Date.now() + expiresIn * 1000,
    };

    const requestedRedirect = request.cookies.get("oidc_post_login_redirect")?.value || "/operations";
    let postLoginRedirect = "/operations";
    if (
      requestedRedirect.startsWith("/") &&
      !requestedRedirect.startsWith("//") &&
      !requestedRedirect.includes("\\") &&
      requestedRedirect !== "/"
    ) {
      const target = new URL(requestedRedirect, request.nextUrl.origin);
      if (target.origin === request.nextUrl.origin) {
        postLoginRedirect = `${target.pathname}${target.search}${target.hash}`;
      }
    }
    const response = NextResponse.redirect(new URL(postLoginRedirect, request.nextUrl.origin));
    const isSecure = isSecureRequest(request);

    // Securely set the authentic Keycloak access token in HTTP-only cookie
    response.cookies.set("platform_access_token", accessToken, {
      httpOnly: true,
      secure: isSecure,
      sameSite: "lax",
      path: "/",
      maxAge: expiresIn,
    });

    if (refreshToken) {
      response.cookies.set("platform_refresh_token", refreshToken, {
        httpOnly: true,
        secure: isSecure,
        sameSite: "lax",
        path: "/",
        maxAge: 86400 * 7,
      });
    }

    response.cookies.set("platform_session", JSON.stringify(userSession), {
      httpOnly: true,
      secure: isSecure,
      sameSite: "lax",
      path: "/",
      maxAge: expiresIn,
    });

    response.cookies.delete("oidc_code_verifier");
    response.cookies.delete("oidc_auth_state");
    response.cookies.delete("oidc_post_login_redirect");

    return response;
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "internal_error";
    return NextResponse.redirect(
      new URL(`/login?error=${encodeURIComponent(message)}`, request.url)
    );
  }
}
