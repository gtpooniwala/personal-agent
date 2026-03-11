/** @jest-environment node */

import { proxyAgentRequest, __testOnly__ } from '@/lib/agentProxy';

describe('agent proxy helpers', () => {
  test('maps browser routes onto current backend routes', () => {
    expect(__testOnly__.backendPathForSegments(['conversations'])).toBe('/api/v1/conversations');
    expect(__testOnly__.backendPathForSegments(['documents', 'upload'])).toBe('/api/v1/documents/upload');
    expect(__testOnly__.backendPathForSegments(['observability', 'summary'])).toBe('/api/v1/observability/summary');
    expect(__testOnly__.backendPathForSegments(['chat'])).toBe('/chat');
    expect(__testOnly__.backendPathForSegments(['runs', 'run-1', 'stream'])).toBe('/runs/run-1/stream');
    expect(__testOnly__.backendPathForSegments(['scheduler', 'tasks'])).toBeNull();
  });

  test('rejects unsafe dot-segments before building an upstream path', async () => {
    const fetchImpl = jest.fn();

    const response = await proxyAgentRequest(
      new Request('http://localhost:3000/api/agent/conversations/../admin', { method: 'GET' }),
      ['conversations', '..', 'admin'],
      {
        env: {
          API_BASE_URL: 'http://127.0.0.1:8000',
          AGENT_API_KEY: 'server-token',
        },
        fetchImpl,
      },
    );

    expect(fetchImpl).not.toHaveBeenCalled();
    expect(response.status).toBe(400);
    await expect(response.json()).resolves.toEqual({
      detail: 'Unsafe agent proxy route.',
    });
  });

  test('returns a clear error when API_BASE_URL is missing', async () => {
    const response = await proxyAgentRequest(
      new Request('http://localhost:3000/api/agent/chat', { method: 'POST', body: '{}' }),
      ['chat'],
      { env: { AGENT_API_KEY: 'token' }, fetchImpl: jest.fn() },
    );

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      detail: 'API_BASE_URL must be configured for the Next.js agent proxy.',
    });
  });

  test('returns a clear error when AGENT_API_KEY is missing', async () => {
    const response = await proxyAgentRequest(
      new Request('http://localhost:3000/api/agent/chat', { method: 'POST', body: '{}' }),
      ['chat'],
      { env: { API_BASE_URL: 'http://127.0.0.1:8000' }, fetchImpl: jest.fn() },
    );

    expect(response.status).toBe(500);
    await expect(response.json()).resolves.toEqual({
      detail: 'AGENT_API_KEY must be configured for the Next.js agent proxy.',
    });
  });

  test('forwards JSON requests with query params and server-side auth injection', async () => {
    const fetchImpl = jest.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: {
          'content-type': 'application/json',
          'x-request-id': 'req-123',
        },
      }),
    );

    const request = new Request('http://localhost:3000/api/agent/runs/run-1/events?after=evt-1&limit=4', {
      method: 'GET',
      headers: {
        Authorization: 'Bearer browser-token',
        Accept: 'application/json',
      },
    });

    const response = await proxyAgentRequest(request, ['runs', 'run-1', 'events'], {
      env: {
        API_BASE_URL: 'http://127.0.0.1:8000',
        AGENT_API_KEY: 'server-token',
      },
      fetchImpl,
    });

    expect(fetchImpl).toHaveBeenCalledTimes(1);
    const [url, options] = fetchImpl.mock.calls[0];
    expect(url.toString()).toBe('http://127.0.0.1:8000/runs/run-1/events?after=evt-1&limit=4');
    expect(options.method).toBe('GET');
    expect(options.headers.get('Authorization')).toBe('Bearer server-token');
    expect(options.headers.get('Accept')).toBe('application/json');
    expect(options.body).toBeUndefined();
    expect(options.signal).toBe(request.signal);
    expect(response.status).toBe(200);
    expect(response.headers.get('content-type')).toBe('application/json');
    expect(response.headers.get('x-request-id')).toBe('req-123');
    await expect(response.json()).resolves.toEqual({ ok: true });
  });

  test('forwards multipart uploads without reusing the incoming content-type boundary', async () => {
    const fetchImpl = jest.fn().mockResolvedValue(
      new Response(JSON.stringify({ document_id: 'doc-1' }), {
        status: 201,
        headers: { 'content-type': 'application/json' },
      }),
    );
    const formData = new FormData();
    formData.append('file', new Blob(['pdf-bytes'], { type: 'application/pdf' }), 'contract.pdf');

    const request = new Request('http://localhost:3000/api/agent/documents/upload', {
      method: 'POST',
      body: formData,
    });

    const response = await proxyAgentRequest(request, ['documents', 'upload'], {
      env: {
        API_BASE_URL: 'http://127.0.0.1:8000',
        AGENT_API_KEY: 'server-token',
      },
      fetchImpl,
    });

    const [, options] = fetchImpl.mock.calls[0];
    expect(options.headers.get('Authorization')).toBe('Bearer server-token');
    expect(options.headers.has('content-type')).toBe(false);
    expect(options.body).toBeInstanceOf(FormData);
    expect(response.status).toBe(201);
    await expect(response.json()).resolves.toEqual({ document_id: 'doc-1' });
  });

  test('passes through SSE streams and allowlisted headers', async () => {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode('event: heartbeat\n\n'));
        controller.close();
      },
    });
    const fetchImpl = jest.fn().mockResolvedValue(
      new Response(stream, {
        status: 200,
        headers: {
          'content-type': 'text/event-stream',
          'cache-control': 'no-cache',
          'x-request-id': 'req-stream',
          connection: 'keep-alive',
        },
      }),
    );

    const response = await proxyAgentRequest(
      new Request('http://localhost:3000/api/agent/runs/run-1/stream', {
        method: 'GET',
        headers: { Accept: 'text/event-stream' },
      }),
      ['runs', 'run-1', 'stream'],
      {
        env: {
          API_BASE_URL: 'http://127.0.0.1:8000',
          AGENT_API_KEY: 'server-token',
        },
        fetchImpl,
      },
    );

    expect(response.status).toBe(200);
    expect(response.headers.get('content-type')).toBe('text/event-stream');
    expect(response.headers.get('cache-control')).toBe('no-cache');
    expect(response.headers.get('connection')).toBeNull();
    await expect(response.text()).resolves.toContain('event: heartbeat');
  });

  test('passes through redirect targets when using manual redirect mode', async () => {
    const fetchImpl = jest.fn().mockResolvedValue(
      new Response(null, {
        status: 307,
        headers: {
          location: 'http://127.0.0.1:8000/api/v1/conversations?after=next',
        },
      }),
    );

    const response = await proxyAgentRequest(
      new Request('http://localhost:3000/api/agent/conversations', {
        method: 'GET',
      }),
      ['conversations'],
      {
        env: {
          API_BASE_URL: 'http://127.0.0.1:8000',
          AGENT_API_KEY: 'server-token',
        },
        fetchImpl,
      },
    );

    expect(response.status).toBe(307);
    expect(response.headers.get('location')).toBe('/api/agent/conversations?after=next');
  });

  test('rewrites chat subpath redirects onto the proxy contract', () => {
    expect(
      __testOnly__.rewriteLocationHeader(
        'http://127.0.0.1:8000/chat/session-123?resume=1',
        'http://127.0.0.1:8000',
      ),
    ).toBe('/api/agent/chat/session-123?resume=1');
  });

  test('preserves external redirect targets', () => {
    expect(
      __testOnly__.rewriteLocationHeader(
        'https://accounts.google.com/o/oauth2/v2/auth?client_id=test',
        'http://127.0.0.1:8000',
      ),
    ).toBe('https://accounts.google.com/o/oauth2/v2/auth?client_id=test');
  });

  test('drops same-backend redirect targets that do not map onto the proxy contract', async () => {
    const fetchImpl = jest.fn().mockResolvedValue(
      new Response(null, {
        status: 302,
        headers: {
          location: 'http://127.0.0.1:8000/internal/admin',
        },
      }),
    );

    const response = await proxyAgentRequest(
      new Request('http://localhost:3000/api/agent/conversations', {
        method: 'GET',
      }),
      ['conversations'],
      {
        env: {
          API_BASE_URL: 'http://127.0.0.1:8000',
          AGENT_API_KEY: 'server-token',
        },
        fetchImpl,
      },
    );

    expect(response.status).toBe(302);
    expect(response.headers.get('location')).toBeNull();
  });

  test('passes through backend failures and auth headers', async () => {
    const fetchImpl = jest.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Unauthorized' }), {
        status: 401,
        headers: {
          'content-type': 'application/json',
          'www-authenticate': 'Bearer',
        },
      }),
    );

    const response = await proxyAgentRequest(
      new Request('http://localhost:3000/api/agent/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ message: 'hello' }),
      }),
      ['chat'],
      {
        env: {
          API_BASE_URL: 'http://127.0.0.1:8000',
          AGENT_API_KEY: 'server-token',
        },
        fetchImpl,
      },
    );

    expect(response.status).toBe(401);
    expect(response.headers.get('www-authenticate')).toBe('Bearer');
    await expect(response.json()).resolves.toEqual({ detail: 'Unauthorized' });
  });

  test('returns a stable 502 when the backend cannot be reached', async () => {
    const fetchImpl = jest.fn().mockRejectedValue(new Error('connect ECONNREFUSED'));

    const response = await proxyAgentRequest(
      new Request('http://localhost:3000/api/agent/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ message: 'hello' }),
      }),
      ['chat'],
      {
        env: {
          API_BASE_URL: 'http://127.0.0.1:8000',
          AGENT_API_KEY: 'server-token',
        },
        fetchImpl,
      },
    );

    expect(response.status).toBe(502);
    await expect(response.json()).resolves.toEqual({
      detail: 'Agent proxy could not reach the backend service.',
    });
  });

  test('returns a stable 504 when upstream aborts before the client signal is aborted', async () => {
    const abortError = new Error('timed out');
    abortError.name = 'AbortError';
    const fetchImpl = jest.fn().mockRejectedValue(abortError);

    const response = await proxyAgentRequest(
      new Request('http://localhost:3000/api/agent/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ message: 'hello' }),
      }),
      ['chat'],
      {
        env: {
          API_BASE_URL: 'http://127.0.0.1:8000',
          AGENT_API_KEY: 'server-token',
        },
        fetchImpl,
      },
    );

    expect(response.status).toBe(504);
    await expect(response.json()).resolves.toEqual({
      detail: 'Agent proxy upstream request timed out.',
    });
  });

  test('returns a stable 499 when the client request has already been aborted', async () => {
    const controller = new AbortController();
    controller.abort();
    const abortError = new Error('aborted');
    abortError.name = 'AbortError';
    const fetchImpl = jest.fn().mockRejectedValue(abortError);

    const response = await proxyAgentRequest(
      new Request('http://localhost:3000/api/agent/chat', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ message: 'hello' }),
        signal: controller.signal,
      }),
      ['chat'],
      {
        env: {
          API_BASE_URL: 'http://127.0.0.1:8000',
          AGENT_API_KEY: 'server-token',
        },
        fetchImpl,
      },
    );

    expect(response.status).toBe(499);
    await expect(response.json()).resolves.toEqual({
      detail: 'Agent proxy request was cancelled.',
    });
  });
});
