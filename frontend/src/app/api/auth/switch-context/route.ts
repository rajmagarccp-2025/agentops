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
    const body = await request.json();
    let backendBaseUrl =
      process.env.INTERNAL_API_BASE_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      "http://localhost:8000/api/v1";

    const accessToken = request.cookies.get("platform_access_token")?.value;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    if (accessToken) {
      headers["Authorization"] = `Bearer ${accessToken}`;
    }

    let res: Response;
    try {
      res = await fetch(`${backendBaseUrl}/auth/switch-context`, {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });
    } catch (fetchErr) {
      if (backendBaseUrl.includes("api:8000")) {
        backendBaseUrl = "http://127.0.0.1:8000/api/v1";
        res = await fetch(`${backendBaseUrl}/auth/switch-context`, {
          method: "POST",
          headers,
          body: JSON.stringify(body),
        });
      } else {
        throw fetchErr;
      }
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Failed to switch context" }));
      return NextResponse.json({ error: err.detail || "Context switch failed" }, { status: res.status });
    }

    const data = await res.json();
    const newAccessToken = data.access_token;
    const activeContext = data.active_context;

    const response = NextResponse.json({
      success: true,
      active_context: activeContext,
    });

    const isSecure = isSecureRequest(request);

    if (newAccessToken) {
      response.cookies.set("platform_access_token", newAccessToken, {
        httpOnly: true,
        secure: isSecure,
        sameSite: "lax",
        path: "/",
        maxAge: 1800,
      });

      // Update session cookie with new tenant_id, project_id, environment_id
      const sessionCookie = request.cookies.get("platform_session")?.value;
      if (sessionCookie) {
        try {
          const session = JSON.parse(sessionCookie);
          session.tenant_id = activeContext.organization_id;
          session.project_id = activeContext.project_id;
          session.environment_id = activeContext.environment_id;
          session.roles = [activeContext.role];
          response.cookies.set("platform_session", JSON.stringify(session), {
            httpOnly: true,
            secure: isSecure,
            sameSite: "lax",
            path: "/",
            maxAge: 1800,
          });
        } catch {
          // ignore parse error
        }
      }
    }

    return response;
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Context switch error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
