import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const sessionCookie = request.cookies.get("platform_session")?.value;
  const tokenCookie = request.cookies.get("platform_access_token")?.value;

  if (!sessionCookie || !tokenCookie) {
    return NextResponse.json({ authenticated: false, user: null }, { status: 401 });
  }

  try {
    const session = JSON.parse(sessionCookie);
    if (session.expires_at && session.expires_at < Date.now()) {
      return NextResponse.json({ authenticated: false, error: "session_expired" }, { status: 401 });
    }

    return NextResponse.json({
      authenticated: true,
      user: {
        subject: session.subject,
        email: session.email,
        roles: session.roles,
        permissions: session.permissions,
        tenant_id: session.tenant_id,
        tenant_memberships: session.tenant_memberships,
        read_only_demo: session.read_only_demo === true,
      },
    });
  } catch {
    return NextResponse.json({ authenticated: false, error: "invalid_session" }, { status: 401 });
  }
}
