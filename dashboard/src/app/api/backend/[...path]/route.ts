/**
 * Same-origin proxy to the FastAPI backend. See src/lib/api/client.ts for
 * why this exists (no CORS on the backend, and this stage's instructions
 * say not to add any — so the browser never talks to FastAPI directly;
 * only this server-side handler does, which isn't subject to CORS at all).
 *
 * Pure forwarding: method, path, query string, and JSON body pass through
 * unchanged, and the backend's response body/status come back verbatim
 * (including error bodies) so ApiError in client.ts sees the real FastAPI
 * error shape.
 *
 * Dashboard auth (see service/app/api/auth.py) needs two more headers
 * forwarded, in each direction:
 *  - Request: the browser's Cookie header (carries dashboard_session /
 *    dashboard_csrf) and X-CSRF-Token (the double-submit header the
 *    frontend echoes back on mutations) — both passed straight through so
 *    the backend's require_dashboard_auth can see them.
 *  - Response: the backend's Set-Cookie header(s) (login sets two cookies
 *    at once) — forwarded verbatim so the cookie appears to the browser as
 *    set by THIS origin, exactly like every other cookie in this proxy
 *    pattern. Nothing here reads or inspects the cookie value itself.
 */

import { NextRequest, NextResponse } from 'next/server';

const CONFIGURED_BACKEND_URL =
  process.env.BACKEND_API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL;
const BACKEND_URL =
  process.env.VERCEL_ENV === 'production'
    ? 'https://api.battlen0de.xyz'
    : CONFIGURED_BACKEND_URL;
const MAX_PROXY_BODY_BYTES = 1_000_000;
const BACKEND_TIMEOUT_MS = 20_000;

async function forward(request: NextRequest, path: string[]): Promise<NextResponse> {
  if (!BACKEND_URL) {
    return NextResponse.json(
      { detail: 'Backend service is not configured.' },
      { status: 500 },
    );
  }

  const base = BACKEND_URL.replace(/\/+$/, '');
  const target = `${base}/${path.join('/')}${request.nextUrl.search}`;

  const forwardedHeaders: Record<string, string> = {};
  const internalToken = process.env.INTERNAL_PROXY_TOKEN;
  if (internalToken) forwardedHeaders['x-battlenode-internal-token'] = internalToken;
  const cookie = request.headers.get('cookie');
  if (cookie) forwardedHeaders['cookie'] = cookie;
  const csrfToken = request.headers.get('x-csrf-token');
  if (csrfToken) forwardedHeaders['x-csrf-token'] = csrfToken;

  const init: RequestInit = {
    method: request.method,
    headers: forwardedHeaders,
    signal: AbortSignal.timeout(BACKEND_TIMEOUT_MS),
  };
  if (!['GET', 'HEAD'].includes(request.method)) {
    const declaredLength = Number(request.headers.get('content-length') ?? '0');
    if (Number.isFinite(declaredLength) && declaredLength > MAX_PROXY_BODY_BYTES) {
      return NextResponse.json({ detail: 'Request body is too large.' }, { status: 413 });
    }

    const body = await request.text();
    if (new TextEncoder().encode(body).byteLength > MAX_PROXY_BODY_BYTES) {
      return NextResponse.json({ detail: 'Request body is too large.' }, { status: 413 });
    }
    if (body) {
      init.body = body;
      forwardedHeaders['content-type'] = 'application/json';
    }
  }

  let response: Response;
  try {
    response = await fetch(target, init);
  } catch {
    return NextResponse.json(
      { detail: 'Could not reach the Warpath backend service.' },
      { status: 503 },
    );
  }

  const text = await response.text();

  // The Response/NextResponse constructor throws if given a body alongside
  // a null-body status (204/205/304, per the Fetch spec) — even an empty
  // string. DELETE /accounts/{id} returns 204, so this isn't a hypothetical:
  // it 500'd here on every real delete until this check was added.
  const NULL_BODY_STATUSES = new Set([204, 205, 304]);
  const setCookies = typeof response.headers.getSetCookie === 'function' ? response.headers.getSetCookie() : [];

  if (NULL_BODY_STATUSES.has(response.status)) {
    const nullResponse = new NextResponse(null, { status: response.status });
    nullResponse.headers.set('cache-control', 'no-store');
    for (const cookieValue of setCookies) nullResponse.headers.append('set-cookie', cookieValue);
    return nullResponse;
  }

  const proxied = new NextResponse(text, {
    status: response.status,
    headers: {
      'content-type': response.headers.get('content-type') ?? 'application/json',
      'cache-control': 'no-store',
    },
  });
  for (const cookieValue of setCookies) proxied.headers.append('set-cookie', cookieValue);
  return proxied;
}

type RouteContext = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, { params }: RouteContext) {
  return forward(request, (await params).path);
}

export async function POST(request: NextRequest, { params }: RouteContext) {
  return forward(request, (await params).path);
}

export async function DELETE(request: NextRequest, { params }: RouteContext) {
  return forward(request, (await params).path);
}


export async function PATCH(request: NextRequest, { params }: RouteContext) {
  return forward(request, (await params).path);
}
