import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";

function isSecureRequest(request: NextRequest): boolean {
  const host = request.headers.get("host") || "";
  if (host.includes("localhost") || host.includes("127.0.0.1")) {
    return false;
  }
  const forwardedProto = request.headers.get("x-forwarded-proto");
  if (forwardedProto) {
    return forwardedProto.startsWith("https");
  }
  return request.nextUrl.protocol.startsWith("https");
}

function formatErrorDetail(err: unknown, fallback: string): string {
  if (!err || typeof err !== "object") return fallback;
  const errorObj = err as Record<string, unknown>;
  if (typeof errorObj.detail === "string") return errorObj.detail;
  if (typeof errorObj.error === "string") return errorObj.error;
  if (Array.isArray(errorObj.detail)) {
    return errorObj.detail
      .map((d: unknown) =>
        typeof d === "string"
          ? d
          : typeof d === "object" && d !== null && "msg" in d
          ? String((d as Record<string, unknown>).msg)
          : JSON.stringify(d)
      )
      .join("; ");
  }
  if (typeof errorObj.detail === "object" && errorObj.detail !== null) {
    return JSON.stringify(errorObj.detail);
  }
  return fallback;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    let backendBaseUrl =
      process.env.INTERNAL_API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://localhost:8000/api/v1";

    let res: Response;
    try {
      res = await fetch(`${backendBaseUrl}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
    } catch (fetchErr) {
      if (backendBaseUrl.includes("api:8000")) {
        backendBaseUrl = "http://127.0.0.1:8000/api/v1";
        res = await fetch(`${backendBaseUrl}/auth/signup`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } else {
        throw fetchErr;
      }
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Unable to create account. Please try again." }));
      return NextResponse.json(
        { error: formatErrorDetail(err, "Unable to create account. Please try again.") },
        { status: res.status }
      );
    }

    const data = await res.json();
    const { access_token, expires_in, user } = data;

    const userSession = {
      subject: user.subject,
      email: user.email,
      roles: [user.effective_role || "READ"],
      tenant_id: user.active_organization_id || "",
      tenant_memberships: [],
      has_organization: user.has_organization,
      expires_at: Date.now() + (expires_in || 1800) * 1000,
      project_id: user.active_project_id,
      environment_id: user.active_environment_id,
    };

    const response = NextResponse.json({
      success: true,
      user,
    });

    const isSecure = isSecureRequest(request);

    // Store HTTP-only access token
    response.cookies.set("platform_access_token", access_token, {
      httpOnly: true,
      secure: isSecure,
      sameSite: "lax",
      path: "/",
      maxAge: expires_in || 1800,
    });

    // Store session metadata for client
    response.cookies.set("platform_session", JSON.stringify(userSession), {
      httpOnly: true,
      secure: isSecure,
      sameSite: "lax",
      path: "/",
      maxAge: expires_in || 1800,
    });

    return response;
  } catch (err: unknown) {
    const isFetchFailed =
      err instanceof Error &&
      (err.message.includes("fetch failed") ||
        err.message.includes("ECONNREFUSED") ||
        err.message.includes("ENOTFOUND"));
    const message = isFetchFailed
      ? "Unable to connect to the AgentOps API. Please verify that the backend server is running on port 8000."
      : err instanceof Error
      ? err.message
      : "Unable to create account. Please try again.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function GET(request: NextRequest) {
  const keycloakUrl =
    process.env.KEYCLOAK_URL ||
    process.env.KEYCLOAK_BASE_URL ||
    process.env.NEXT_PUBLIC_KEYCLOAK_URL;
  const realm =
    process.env.KEYCLOAK_REALM || process.env.NEXT_PUBLIC_KEYCLOAK_REALM;
  const clientId =
    process.env.KEYCLOAK_CLIENT_ID || process.env.NEXT_PUBLIC_KEYCLOAK_CLIENT_ID;
  const redirectUri =
    process.env.KEYCLOAK_REDIRECT_URI ||
    process.env.NEXTAUTH_REDIRECT_URI ||
    "http://localhost:3000/api/auth/callback";

  if (!keycloakUrl || !realm || !clientId || !redirectUri) {
    const errorMsg =
      "Keycloak authentication is not configured. Check KEYCLOAK_URL, KEYCLOAK_REALM, KEYCLOAK_CLIENT_ID and KEYCLOAK_REDIRECT_URI.";
    return NextResponse.redirect(
      new URL(`/signup?error=${encodeURIComponent(errorMsg)}`, request.url)
    );
  }

  // Generate PKCE code verifier and challenge
  const codeVerifier = crypto.randomBytes(32).toString("base64url");
  const codeChallenge = crypto
    .createHash("sha256")
    .update(codeVerifier)
    .digest("base64url");

  const state = crypto.randomBytes(16).toString("hex");

  // Keycloak OIDC registrations endpoint
  const authUrl = new URL(`${keycloakUrl}/realms/${realm}/protocol/openid-connect/registrations`);
  authUrl.searchParams.set("client_id", clientId);
  authUrl.searchParams.set("redirect_uri", redirectUri);
  authUrl.searchParams.set("response_type", "code");
  authUrl.searchParams.set("scope", "openid email profile platform-permissions");
  authUrl.searchParams.set("code_challenge", codeChallenge);
  authUrl.searchParams.set("code_challenge_method", "S256");
  authUrl.searchParams.set("state", state);

  const response = NextResponse.redirect(authUrl.toString());

  const isSecure = isSecureRequest(request);

  response.cookies.set("oidc_code_verifier", codeVerifier, {
    httpOnly: true,
    secure: isSecure,
    sameSite: "lax",
    path: "/",
    maxAge: 600,
  });

  response.cookies.set("oidc_auth_state", state, {
    httpOnly: true,
    secure: isSecure,
    sameSite: "lax",
    path: "/",
    maxAge: 600,
  });

  return response;
}
