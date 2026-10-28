import { describe, expect, it, vi, afterEach } from 'vitest';
import { apiRequest, ApiError } from './client';

describe('apiRequest', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('resolves with parsed JSON on a 2xx response', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), { status: 200 }),
    );

    const result = await apiRequest<{ status: string }>('/health');
    expect(result).toEqual({ status: 'ok' });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/backend/health',
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('throws ApiError with a plain string detail (HTTPException shape)', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'account not found' }), { status: 404 }),
    );

    await expect(apiRequest('/accounts/x')).rejects.toMatchObject({
      status: 404,
      detail: 'account not found',
    });
  });

  it('normalizes a list-of-strings detail (WarpathCredentials.validation_errors shape)', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: ['app_token is not set', 'device_id is not set'] }), { status: 422 }),
    );

    try {
      await apiRequest('/accounts/x/connect', { method: 'POST' });
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.status).toBe(422);
      expect(apiError.message).toContain('app_token is not set');
      expect(apiError.message).toContain('device_id is not set');
    }
  });

  it('normalizes Pydantic-style validation error objects', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ detail: [{ loc: ['body', 'level'], msg: 'field required', type: 'missing' }] }),
        { status: 422 },
      ),
    );

    await expect(apiRequest('/accounts/x/farm', { method: 'POST', body: {} })).rejects.toMatchObject({
      status: 422,
      message: expect.stringContaining('field required'),
    });
  });

  it('wraps a network failure as a 503-free, status-0 ApiError', async () => {
    global.fetch = vi.fn().mockRejectedValue(new TypeError('fetch failed'));

    try {
      await apiRequest('/health');
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).status).toBe(0);
      expect((error as ApiError).message).toMatch(/network|reach/i);
    }
  });

  it('sends a JSON body and content-type header for POST requests', async () => {
    global.fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'ok' }), { status: 200 }));

    await apiRequest('/accounts/x/farm', { method: 'POST', body: { resource: 'gold', level: 3 } });

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/backend/accounts/x/farm',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ resource: 'gold', level: 3 }),
        headers: { 'content-type': 'application/json' },
      }),
    );
  });

  it('exposes isServiceUnavailable only for 503 responses', async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'max_concurrent_sessions reached' }), { status: 503 }),
    );

    try {
      await apiRequest('/accounts/x/connect', { method: 'POST' });
      expect.unreachable();
    } catch (error) {
      expect((error as ApiError).isServiceUnavailable).toBe(true);
    }
  });
});


describe('session expiry notifications', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.cookie = 'dashboard_csrf=; max-age=0; path=/';
  });
  it('clears the current identity on an authenticated API 401', async () => {
    const listener = vi.fn();
    window.addEventListener('warpath-auth-expired', listener);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 401 })));
    try {
      await expect(apiRequest('/accounts')).rejects.toMatchObject({ status: 401 });
      expect(listener).toHaveBeenCalledOnce();
    } finally { window.removeEventListener('warpath-auth-expired', listener); }
  });
  it('ignores a late 401 from a previous website session', async () => {
    document.cookie = 'dashboard_csrf=old-session; path=/';
    let finish!: (value: Response) => void;
    const listener = vi.fn();
    window.addEventListener('warpath-auth-expired', listener);
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { finish = resolve; })));
    const result = apiRequest('/accounts');
    document.cookie = 'dashboard_csrf=new-session; path=/';
    finish(new Response('{}', { status: 401 }));
    try {
      await expect(result).rejects.toMatchObject({ status: 401 });
      expect(listener).not.toHaveBeenCalled();
    } finally { window.removeEventListener('warpath-auth-expired', listener); }
  });
});
