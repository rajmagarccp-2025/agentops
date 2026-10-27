import { NextRequest, NextResponse } from "next/server";

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

export async function POST(request: NextRequest) {
  try {
    let backendBaseUrl =
      process.env.INTERNAL_API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://localhost:8000/api/v1";

    let res: Response;
    try {
      res = await fetch(`${backendBaseUrl}/auth/demo`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        cache: "no-store",
      });
    } catch (fetchErr) {
      if (backendBaseUrl.includes("api:8000")) {
        backendBaseUrl = "http://127.0.0.1:8000/api/v1";
        res = await fetch(`${backendBaseUrl}/auth/demo`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          cache: "no-store",
        });
      } else {
        throw fetchErr;
      }
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Demo authentication is disabled." }));
      return NextResponse.json(
        { error: err.detail || "Demo authentication failed." },
        { status: res.status }
      );
    }

    const data = await res.json();
    const { access_token, expires_in, user } = data;

    const userSession = {
      subject: user.subject,
      email: user.email,
      roles: [user.effective_role || "READ"],
      permissions:
        user.read_only_demo === true
          ? ["security:read", "security.read", "audit:read", "audit.read"]
          : [],
      tenant_id: user.active_organization_id || "",
      tenant_memberships: [],
      has_organization: user.has_organization,
      read_only_demo: user.read_only_demo === true,
      expires_at: Date.now() + (expires_in || 1800) * 1000,
      project_id: user.active_project_id,
      environment_id: user.active_environment_id,
    };

    const response = NextResponse.json({
      success: true,
      user,
    });

    const isSecure = isSecureRequest(request);

    response.cookies.set("platform_access_token", access_token, {
      httpOnly: true,
      secure: isSecure,
      sameSite: "lax",
      path: "/",
      maxAge: expires_in || 1800,
    });

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
      : "Demo login failed. Please try again.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
