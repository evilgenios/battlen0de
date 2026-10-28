/**
 * Low-level HTTP client. Every call goes to `/api/backend/*` — a same-origin
 * Next.js Route Handler (see src/app/api/backend/[...path]/route.ts) that
 * forwards to the FastAPI backend server-side.
 *
 * Why a proxy instead of calling the backend directly from the browser: the
 * FastAPI service (service/app/main.py) has no CORS middleware configured,
 * and this stage's instructions are explicit — treat that API as a fixed
 * contract, do not modify the backend. Routing through our own server
 * avoids needing any CORS change there at all (server-to-server requests
 * aren't subject to CORS, only browser-to-cross-origin ones are), while keeping the backend origin server-side in the route handler rather than
 * hardcoding it into browser code.
 */

export type Detail = string | string[] | Array<{ msg?: string; loc?: unknown[] }>;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: Detail | null;

  constructor(status: number, detail: Detail | null, message?: string) {
    super(message ?? summarizeDetail(detail) ?? `Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }

  /** True for the capacity/service-unavailable class of error (503). */
  get isServiceUnavailable(): boolean {
    return this.status === 503;
  }
}

/** FastAPI's `detail` field varies by error source: a plain string for
 * HTTPException(detail=...), a list of strings for our own
 * WarpathCredentials.validation_errors() (used on 422 from /connect), or
 * Pydantic's own `[{msg, loc, ...}]` shape for request-body validation
 * failures. Normalize all three into one human-readable string. */
function summarizeDetail(detail: Detail | null | undefined): string | null {
  if (detail == null) return null;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    if (detail.length === 0) return null;
    const parts = detail.map((item) => (typeof item === 'string' ? item : item.msg ?? JSON.stringify(item)));
    return parts.join('; ');
  }
  return null;
}

export { summarizeDetail };

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
}

/** Reads the dashboard_csrf cookie (deliberately non-HttpOnly — see
 * service/app/api/auth.py) so mutating requests can echo it back as a
 * header (double-submit cookie pattern). Returns '' before login / when
 * dashboard auth isn't configured, in which case the backend's
 * require_dashboard_auth doesn't check it either. */
function readCsrfCookie(): string {
  if (typeof document === 'undefined') return '';
  const match = document.cookie.match(/(?:^|;\s*)dashboard_csrf=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal } = options;
  const requestIdentity = readCsrfCookie();

  const headers: Record<string, string> = {};
  if (body !== undefined) headers['content-type'] = 'application/json';
  if (method !== 'GET') {
    const csrfToken = readCsrfCookie();
    if (csrfToken) headers['x-csrf-token'] = csrfToken;
  }

  let response: Response;
  try {
    response = await fetch(`/api/backend${path}`, {
      method,
      headers: Object.keys(headers).length > 0 ? headers : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal,
      cache: 'no-store',
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, null, 'Could not reach the dashboard server. Check your network connection.');
  }

  const text = await response.text();
  const data = text ? safeJsonParse(text) : null;

  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login' && path !== '/auth/me'
        && requestIdentity === readCsrfCookie() && typeof window !== 'undefined') {
      window.dispatchEvent(new Event('warpath-auth-expired'));
    }
    const detail: Detail | null = data && typeof data === 'object' && 'detail' in data
      ? (data as { detail: Detail }).detail
      : null;
    throw new ApiError(response.status, detail);
  }

  return data as T;
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}
