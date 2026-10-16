import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = [
  "/",
  "/capabilities",
  "/contact",
  "/login",
  "/multi-tenancy",
  "/rbac",
  "/security",
  "/security-rbac",
  "/signup",
  "/forgot-password",
  "/demo",
  "/auth/callback",
  "/api/auth/login",
  "/api/auth/signup",
  "/api/auth/callback",
  "/api/auth/logout",
  "/api/auth/session",
  "/api/auth/demo",
  "/api/proxy/auth/demo-token",
  "/api/proxy/health",
];

const hasAuthSession = (request: NextRequest) =>
  Boolean(request.cookies.get("platform_access_token")?.value && request.cookies.get("platform_session")?.value);

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow static files, Next.js internal routes, images, and public /demo routes
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api/auth/") ||
    pathname.startsWith("/api/proxy/") ||
    pathname.startsWith("/public/") ||
    pathname.startsWith("/demo") ||
    pathname.includes(".") || // static files like hero-illustration.jpg, favicon.ico
    PUBLIC_PATHS.includes(pathname)
  ) {
    // If authenticated user visits login or signup, redirect them to operations
    if (pathname === "/login" || pathname === "/signup") {
      if (hasAuthSession(request)) {
        return NextResponse.redirect(new URL("/operations", request.url));
      }
    }
    return NextResponse.next();
  }

  // Check for authentication tokens/session
  const accessToken = request.cookies.get("platform_access_token")?.value;
  const sessionCookie = request.cookies.get("platform_session")?.value;

  if (!accessToken || !sessionCookie) {
    // User is unauthenticated, redirect to login
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Validate session expiration if available
  try {
    const session = JSON.parse(sessionCookie);
    if (session.expires_at && session.expires_at < Date.now()) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("error", "session_expired");
      const res = NextResponse.redirect(loginUrl);
      res.cookies.delete("platform_access_token");
      res.cookies.delete("platform_session");
      return res;
    }
  } catch {
    // ignore parse errors
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
