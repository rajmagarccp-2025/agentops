import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return handleProxy(request, await params);
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return handleProxy(request, await params);
}

export async function PUT(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return handleProxy(request, await params);
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return handleProxy(request, await params);
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return handleProxy(request, await params);
}

export async function HEAD(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return handleProxy(request, await params);
}

export async function OPTIONS(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  return handleProxy(request, await params);
}

async function handleProxy(request: NextRequest, params: { path: string[] }) {
  if (params.path.join("/") === "auth/demo-token") {
    return NextResponse.json(
      { detail: "Demo tokens are available only through the HttpOnly demo sign-in flow." },
      { status: 404 },
    );
  }

  const backendBaseUrl =
    process.env.INTERNAL_API_BASE_URL ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    (process.env.NODE_ENV === "production" ? "http://api:8000/api/v1" : "http://127.0.0.1:8000/api/v1");
  const apiPath = "/" + (params.path || []).join("/");
  const url = new URL(request.url);
  const targetUrl = `${backendBaseUrl}${apiPath}${url.search}`;

  // Retrieve HTTP-only access token from cookie
  const accessToken = request.cookies.get("platform_access_token")?.value;

  const headers = new Headers();
  headers.set("Accept", "application/json");
  if (request.headers.get("content-type")) {
    headers.set("Content-Type", request.headers.get("content-type")!);
  }

  // Inject Bearer access token into backend/gateway request
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  } else if (request.headers.get("authorization")) {
    headers.set("Authorization", request.headers.get("authorization")!);
  }

  // Forward tenant & environment context headers
  const contextHeaders = [
    "x-tenant-id",
    "x-project-id",
    "x-environment-id",
    "x-request-id",
    "x-correlation-id",
    "x-confirm-production-environment",
  ];
  for (const h of contextHeaders) {
    const val = request.headers.get(h);
    if (val) {
      headers.set(h, val);
    }
  }

  let body: ArrayBuffer | undefined = undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.arrayBuffer();
  }

  try {
    let upstreamRes: Response;
    try {
      upstreamRes = await fetch(targetUrl, {
        method: request.method,
        headers,
        body,
        cache: "no-store",
      });
    } catch (fetchErr) {
      if (backendBaseUrl.includes("api:8000")) {
        const fallbackTargetUrl = targetUrl.replace("http://api:8000", "http://127.0.0.1:8000");
        upstreamRes = await fetch(fallbackTargetUrl, {
          method: request.method,
          headers,
          body,
          cache: "no-store",
        });
      } else {
        throw fetchErr;
      }
    }

    const contentType = upstreamRes.headers.get("content-type") || "application/json";

    // If streaming SSE (Server-Sent Events), pipe stream directly
    if (contentType.includes("text/event-stream") && upstreamRes.body) {
      return new NextResponse(upstreamRes.body as unknown as ReadableStream, {
        status: upstreamRes.status,
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        },
      });
    }

    const responseData = await upstreamRes.arrayBuffer();
    return new NextResponse(responseData, {
      status: upstreamRes.status,
      headers: {
        "Content-Type": contentType,
      },
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "upstream error";
    return NextResponse.json(
      { error: "upstream_gateway_error", message },
      { status: 502 }
    );
  }
}
