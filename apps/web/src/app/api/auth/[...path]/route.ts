import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Proxy all /api/auth/* requests to the backend, preserving cookies.
 */
async function proxy(req: NextRequest, path: string[]): Promise<NextResponse> {
  const backendPath = `/auth/${path.join("/")}`;
  const backendUrl = `${BACKEND_URL}${backendPath}`;

  // Build headers to forward
  const forwardHeaders = new Headers();

  req.headers.forEach((value, key) => {
    const lower = key.toLowerCase();
    if (
      lower.startsWith("x-forwarded-") ||
      lower.startsWith("x-next-") ||
      lower === "host" ||
      lower === "connection" ||
      lower === "transfer-encoding" ||
      lower === "content-length"
    ) {
      return;
    }
    forwardHeaders.set(key, value);
  });

  // Read body
  let body: BodyInit | null = null;
  if (req.body && req.method !== "GET" && req.method !== "HEAD") {
    body = await req.text();
  }

  try {
    const res = await fetch(backendUrl, {
      method: req.method,
      headers: forwardHeaders,
      body,
    });

    // Build response, forwarding Set-Cookie and other headers
    const responseInit: ResponseInit = {
      status: res.status,
      statusText: res.statusText,
    };

    const responseHeaders = new Headers();

    res.headers.forEach((value, key) => {
      const lower = key.toLowerCase();
      if (
        lower === "set-cookie" ||
        lower === "content-type" ||
        lower === "content-length" ||
        lower === "cache-control" ||
        lower.startsWith("x-")
      ) {
        // append() not set() — multiple Set-Cookie headers
        responseHeaders.append(key, value);
      }
    });

    responseInit.headers = responseHeaders;

    const responseBody = res.status === 204 ? null : await res.text();
    return new NextResponse(responseBody, responseInit);
  } catch (error) {
    console.error("[auth-proxy] Backend unreachable:", error);
    return NextResponse.json(
      { detail: "Backend unreachable" },
      { status: 502 },
    );
  }
}

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(req, (await params).path);
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(req, (await params).path);
}

export async function PUT(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(req, (await params).path);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(req, (await params).path);
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxy(req, (await params).path);
}
