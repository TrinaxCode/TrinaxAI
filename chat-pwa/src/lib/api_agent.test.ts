import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  agentWorkspaceRoot,
  approveAgentAction,
  browseDirectories,
  cancelAgentRun,
  runAgent,
} from './api_agent';

function sseResponse(body: string): Response {
  return new Response(new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body));
      controller.close();
    },
  }), { status: 200 });
}

afterEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  vi.unstubAllGlobals();
});

describe('agent API', () => {
  it('streams valid events and sends all run options', async () => {
    const fetchMock = vi.fn().mockResolvedValue(sseResponse([
      'ignored',
      'data: not-json',
      'data: {"type":"token","content":"hello"}',
      'data: {"type":"done","answer":"hello"}',
      'data: [DONE]',
      '',
    ].join('\n')));
    vi.stubGlobal('fetch', fetchMock);
    const events: unknown[] = [];

    await runAgent(
      [{ role: 'user', content: 'go', image: 'not-forwarded' }],
      (event) => events.push(event),
      {
        workspace: '/tmp/work', model: 'agent-model', maxSteps: 4, yolo: true,
        webSearch: true, knowledgeSearch: true, deepResearch: true,
      },
    );

    expect(events).toEqual([
      { type: 'token', content: 'hello' },
      { type: 'done', answer: 'hello' },
    ]);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/v1\/agent$/);
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({
      messages: [{ role: 'user', content: 'go' }],
      workspace: '/tmp/work',
      model: 'agent-model',
      max_steps: 4,
      yolo: true,
      web_search: true,
      knowledge_search: true,
      deep_research: true,
    });
  });

  it('normalizes HTTP and streamed errors', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: { code: 'invalid_credential' } }), { status: 401 }),
    ).mockResolvedValueOnce(sseResponse(
      'data: {"type":"error","error":"failed","category":"tool_timeout","recovery":"retry","recoverable":true}\n',
    )));

    await expect(runAgent([], vi.fn())).rejects.toMatchObject({ status: 401, category: 'authentication_failed' });
    await expect(runAgent([], vi.fn())).rejects.toMatchObject({
      status: 503, category: 'tool_timeout', recovery: 'retry', retryable: true,
    });
  });

  it('rejects an incomplete stream but permits an aborted one', async () => {
    const controller = new AbortController();
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(sseResponse('data: {"type":"token","content":"partial"}\n'))
      .mockImplementationOnce(async () => {
        controller.abort();
        return sseResponse('data: {"type":"token","content":"partial"}\n');
      }));

    await expect(runAgent([], vi.fn())).rejects.toMatchObject({ category: 'tool_timeout' });
    await expect(runAgent([], vi.fn(), { signal: controller.signal })).resolves.toBeUndefined();
  });

  it('uses a narrow stored workspace and rejects broad Documents roots', () => {
    localStorage.setItem('tc-agent-workspace', '/work/project/');
    expect(agentWorkspaceRoot()).toBe('/work/project/');
    localStorage.setItem('tc-agent-workspace', 'C:\\Users\\me\\Documents\\');
    expect(agentWorkspaceRoot()).toBe('');
  });

  it('calls approval, cancellation, and encoded directory endpoints', async () => {
    const listing = { path: '/a b', parent: '/', home: '/home/me', directories: [] };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json({ ok: true }))
      .mockResolvedValueOnce(Response.json({ ok: true }))
      .mockResolvedValueOnce(Response.json(listing));
    vi.stubGlobal('fetch', fetchMock);
    const signal = new AbortController().signal;

    await approveAgentAction('session', 'approval', false);
    await cancelAgentRun('session');
    await expect(browseDirectories('/a b', signal)).resolves.toEqual(listing);

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      session_id: 'session', approval_id: 'approval', approved: false,
    });
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ session_id: 'session' });
    expect(fetchMock.mock.calls[2][0]).toMatch(/\/v1\/agent\/browse\?path=%2Fa%20b$/);
    expect(fetchMock.mock.calls[2][1].signal).toBe(signal);
  });
});
