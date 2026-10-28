import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';

/**
 * Regression test: found live while verifying DELETE /accounts/{id} through
 * the dashboard — the backend correctly returns 204 No Content, but
 * `new NextResponse(text, { status: 204 })` throws
 * "TypeError: Response constructor: Invalid response status code 204"
 * because the Fetch spec forbids a body on null-body statuses (204/205/304),
 * even an empty string. Every real delete 500'd until this was fixed.
 */

const originalEnv = process.env.NEXT_PUBLIC_API_BASE_URL;

beforeEach(() => {
  // route.ts reads NEXT_PUBLIC_API_BASE_URL into a module-level constant at
  // import time, so each test needs a fresh module evaluation to see the
  // env value it sets — otherwise a later test could silently observe a
  // BACKEND_URL cached from an earlier test's import.
  vi.resetModules();
  process.env.NEXT_PUBLIC_API_BASE_URL = 'http://backend.test';
});

afterEach(() => {
  process.env.NEXT_PUBLIC_API_BASE_URL = originalEnv;
  vi.restoreAllMocks();
});

describe('backend proxy route', () => {
  it('does not throw and forwards a bare 204 for null-body statuses', async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));

    const { DELETE } = await import('./route');
    const request = new NextRequest('http://localhost/api/backend/accounts/abc');

    const response = await DELETE(request, { params: Promise.resolve({ path: ['accounts', 'abc'] }) });

    expect(response.status).toBe(204);
    expect(await response.text()).toBe('');
  });

  it('still forwards a normal JSON body and status for non-204 responses', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), { status: 200, headers: { 'content-type': 'application/json' } }),
    );

    const { GET } = await import('./route');
    const request = new NextRequest('http://localhost/api/backend/health');

    const response = await GET(request, { params: Promise.resolve({ path: ['health'] }) });

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: 'ok' });
  });
});

/**
 * Regression coverage for a live incident where the dashboard's /connect
 * calls kept returning 422 while a direct POST to FastAPI succeeded. The
 * proxy itself turned out not to be at fault (the real cause was a stale
 * in-memory AccountManager session plus a stale NEXT_PUBLIC_API_BASE_URL
 * pointing at a leftover process on the wrong port) — but that was only
 * provable by first ruling the proxy out. These tests pin down exactly what
 * "ruling it out" means: status codes, JSON bodies, the POST body, and the
 * resolved target URL must all pass through this layer unchanged, with
 * exactly one upstream fetch per incoming request.
 */
describe('backend proxy route — status/body/URL fidelity for POST /connect-shaped calls', () => {
  it('forwards an upstream 202 (connecting) unchanged', async () => {
    const upstreamBody = { account_id: 'abc', db_status: 'active', live: { state: 'connecting' } };
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(upstreamBody), { status: 202, headers: { 'content-type': 'application/json' } }),
    );

    const { POST } = await import('./route');
    const request = new NextRequest('http://localhost/api/backend/accounts/abc/connect', { method: 'POST' });

    const response = await POST(request, { params: Promise.resolve({ path: ['accounts', 'abc', 'connect'] }) });

    expect(response.status).toBe(202);
    expect(await response.json()).toEqual(upstreamBody);
  });

  it('forwards an upstream 422 (validation failure) unchanged, not silently mapped to 202', async () => {
    const upstreamBody = { detail: 'app_id is not set; pack_name is not set' };
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(upstreamBody), { status: 422, headers: { 'content-type': 'application/json' } }),
    );

    const { POST } = await import('./route');
    const request = new NextRequest('http://localhost/api/backend/accounts/abc/connect', { method: 'POST' });

    const response = await POST(request, { params: Promise.resolve({ path: ['accounts', 'abc', 'connect'] }) });

    expect(response.status).toBe(422);
    expect(await response.json()).toEqual(upstreamBody);
  });

  it('forwards the POST body to the upstream backend unchanged', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    global.fetch = fetchMock;

    const { POST } = await import('./route');
    const request = new NextRequest('http://localhost/api/backend/accounts/link/verify', {
      method: 'POST',
      body: JSON.stringify({ challenge_id: 'c-1', code: '123456' }),
      headers: { 'content-type': 'application/json' },
    });

    await POST(request, { params: Promise.resolve({ path: ['accounts', 'link', 'verify'] }) });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body as string)).toEqual({ challenge_id: 'c-1', code: '123456' });
    expect(init.method).toBe('POST');
  });

  it('makes exactly one upstream request per incoming request — no automatic retry/duplication', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 202 }));
    global.fetch = fetchMock;

    const { POST } = await import('./route');
    const request = new NextRequest('http://localhost/api/backend/accounts/abc/connect', { method: 'POST' });

    await POST(request, { params: Promise.resolve({ path: ['accounts', 'abc', 'connect'] }) });

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('resolves the target URL from NEXT_PUBLIC_API_BASE_URL plus the forwarded path and query string', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    global.fetch = fetchMock;

    const { GET } = await import('./route');
    const request = new NextRequest('http://localhost/api/backend/accounts/abc/status?limit=5');

    await GET(request, { params: Promise.resolve({ path: ['accounts', 'abc', 'status'] }) });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [targetUrl] = fetchMock.mock.calls[0];
    expect(targetUrl).toBe('http://backend.test/accounts/abc/status?limit=5');
  });

  it('returns 500 with a clear message when NEXT_PUBLIC_API_BASE_URL is not configured, instead of guessing a URL', async () => {
    process.env.NEXT_PUBLIC_API_BASE_URL = '';
    const fetchMock = vi.fn();
    global.fetch = fetchMock;

    const { GET } = await import('./route');
    const request = new NextRequest('http://localhost/api/backend/health');

    const response = await GET(request, { params: Promise.resolve({ path: ['health'] }) });

    expect(response.status).toBe(500);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});


describe('backend proxy route — security boundaries', () => {
  it('marks proxied API responses as non-cacheable', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ email: 'member@example.test' }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      }),
    );

    const { GET } = await import('./route');
    const request = new NextRequest('http://localhost/api/backend/auth/me');
    const response = await GET(request, { params: Promise.resolve({ path: ['auth', 'me'] }) });

    expect(response.headers.get('cache-control')).toBe('no-store');
  });

  it('rejects oversized request bodies before contacting the backend', async () => {
    const fetchMock = vi.fn();
    global.fetch = fetchMock;

    const { POST } = await import('./route');
    const request = new NextRequest('http://localhost/api/backend/accounts/link/verify', {
      method: 'POST',
      body: JSON.stringify({ data: 'x'.repeat(1_000_001) }),
      headers: { 'content-type': 'application/json' },
    });

    const response = await POST(request, { params: Promise.resolve({ path: ['accounts', 'link', 'verify'] }) });

    expect(response.status).toBe(413);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
