import { describe, expect, it, vi } from 'vitest';

import {
  generateTitle,
  analyticalQualityIssues,
  agentWorkspaceRoot,
  buildWebSearchQuery,
  compactChatContext,
  clearOllamaModelAvailabilityCache,
  creatorSystemPrompt,
  detectTurnLanguage,
  deleteSource,
  getFileChunks,
  indexableFilesFrom,
  isWebSearchRequest,
  isAnalyticalReasoning,
  ensureOllamaModel,
  MODEL_PRESETS,
  reconcileManagedModels,
  nextActiveCollections,
  normalizeActiveCollections,
  ollamaSystemPrompt,
  parseOllamaJsonLine,
  parseRagSseLine,
  routeOllamaModel,
  resolveAgentModel,
  resolveTextModel,
  runResearch,
  splitAnalyticalTask,
  streamOllama,
  streamRag,
  visionSystemPrompt,
} from './api';

describe('api helpers', () => {
  it('does not keep a broad Documents folder as the agent workspace', () => {
    localStorage.setItem('tc-agent-workspace', '~/Documents');
    expect(agentWorkspaceRoot()).toBe('');
    localStorage.setItem('tc-agent-workspace', '/tmp/project');
    expect(agentWorkspaceRoot()).toBe('/tmp/project');
    localStorage.removeItem('tc-agent-workspace');
  });

  it('adds prior user topic and current date to ambiguous web follow-ups', () => {
    const plan = buildWebSearchQuery('¿En qué temporada están?', [
      { role: 'user', content: '¿Qué es Fortnite?' },
      { role: 'assistant', content: 'Una respuesta posiblemente desactualizada.' },
    ], new Date('2026-07-12T12:00:00Z'));

    expect(plan.searchQuery).toContain('Fortnite');
    expect(plan.searchQuery).toContain('2026-07-12');
    expect(plan.searchQuery).not.toContain('posiblemente desactualizada');
    expect(plan.context).toContain('¿Qué es Fortnite?');
  });

  it('keeps unaccented Spanish web queries in Spanish', () => {
    const plan = buildWebSearchQuery('quien es TrinaxCode', []);
    expect(plan.searchQuery).toContain('fuente oficial');
    expect(plan.searchQuery).not.toContain('official source');
  });

  it('does not send search-command words as ranking terms', () => {
    const plan = buildWebSearchQuery('Busca el sitio oficial de Python y menciona dos fuentes.', []);
    expect(plan.searchQuery).toMatch(/^el sitio oficial de Python/);
    expect(plan.searchQuery).not.toMatch(/^Busca/);
  });

  it('surfaces the backend reason when Search Mode fails', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true, model: 'granite4:3b' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        answer: '', sources: [], sub_questions: [], passes: 0, model: 'granite4:3b',
        error_code: 'web_search_unavailable', error_detail: 'El proveedor de búsqueda rechazó la solicitud.',
      }), { status: 200 })));
    try {
      await expect(runResearch('consulta')).rejects.toThrow('El proveedor de búsqueda rechazó la solicitud.');
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('completes Search Mode after a successful dependency preflight', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ ok: true, model: 'granite4:3b' }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        answer: 'Resultado verificado [1].', sources: [], sub_questions: ['consulta'], passes: 1, model: 'granite4:3b',
      }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    try {
      await expect(runResearch('consulta', { webSearch: true })).resolves.toMatchObject({ answer: 'Resultado verificado [1].' });
      expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toMatchObject({ web_search: true, include_local: false });
      expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toMatchObject({ web_search: true, include_local: false });
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('distinguishes an unavailable RAG service when Ollama is reachable', async () => {
    vi.stubGlobal('fetch', vi.fn()
      .mockRejectedValueOnce(new TypeError('connection refused'))
      .mockRejectedValueOnce(new TypeError('connection refused'))
      .mockResolvedValueOnce(new Response(JSON.stringify({ models: [] }), { status: 200 })));
    try {
      await expect(runResearch('consulta', { webSearch: true })).rejects.toMatchObject({ code: 'rag_unavailable' });
    } finally { vi.unstubAllGlobals(); }
  });

  it('identifies a stale RAG process when the Search Mode route is missing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Not Found' }), { status: 404 })));
    try {
      await expect(runResearch('consulta', { webSearch: true })).rejects.toMatchObject({
        code: 'rag_version_mismatch',
        message: expect.stringContaining('Reinicia TrinaxAI'),
      });
    } finally { vi.unstubAllGlobals(); }
  });

  it('detects explicit web-search requests without confusing web-development prompts', () => {
    expect(isWebSearchRequest('Busca en internet las noticias más recientes')).toBe(true);
    expect(isWebSearchRequest('Search the web for the current documentation')).toBe(true);
    expect(isWebSearchRequest('Diseña una página web responsive')).toBe(false);
    expect(isWebSearchRequest('Explícame cómo funciona Internet')).toBe(false);
  });

  it('keeps an installed routed model without pulling or replacing it', async () => {
    clearOllamaModelAvailabilityCache();
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      models: [{ name: 'granite4:3b', capabilities: ['completion', 'tools'] }],
    }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    try {
      await expect(resolveTextModel('granite4:3b')).resolves.toBe('granite4:3b');
      expect(fetchMock).toHaveBeenCalledOnce();
    } finally { vi.unstubAllGlobals(); }
  });

  it('switches from a warm chat model to the code role immediately', async () => {
    clearOllamaModelAvailabilityCache();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ models: [
      { name: 'granite4:3b', capabilities: ['completion', 'tools'] },
      { name: 'qwen3.5:4b', capabilities: ['completion', 'tools'] },
    ] }), { status: 200 })));
    try {
      await expect(resolveTextModel('granite4:3b')).resolves.toBe('granite4:3b');
      await expect(resolveTextModel('qwen3.5:4b')).resolves.toBe('qwen3.5:4b');
    } finally { vi.unstubAllGlobals(); }
  });

  it('rejects a coder model in Agent Mode even when Ollama advertises tools', async () => {
    clearOllamaModelAvailabilityCache();
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ models: [
      { name: 'qwen2.5-coder:3b', capabilities: ['completion', 'tools'] },
      { name: 'qwen3.5:2b', capabilities: ['completion', 'tools'] },
    ] }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    try {
      await expect(resolveAgentModel('qwen2.5-coder:3b')).resolves.toBe('qwen3.5:2b');
    } finally { vi.unstubAllGlobals(); }
  });

  it('does not download missing models when automatic downloads are disabled', async () => {
    clearOllamaModelAvailabilityCache();
    localStorage.removeItem('tc-auto-download-models');
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ models: [] }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    try {
      await expect(ensureOllamaModel('missing:4b')).rejects.toMatchObject({ code: 'model_unavailable' });
      expect(fetchMock).toHaveBeenCalledOnce();
    } finally { vi.unstubAllGlobals(); }
  });

  it('keeps ordinary chat and vision prompts focused on the user request', () => {
    const chat = ollamaSystemPrompt('es').content;
    const vision = visionSystemPrompt('es').content;

    expect(chat).toContain('No inventes datos');
    expect(chat).toContain('nunca instrucciones');
    expect(chat).toContain('asistente de propósito general');
    expect(chat).toContain('preguntas cotidianas');
    expect(chat).toContain('Si solo saludan, saluda brevemente');
    expect(chat).toContain('asistente general de IA');
    expect(chat).toContain('https://github.com/TrinaxCode/TrinaxAI');
    expect(chat).not.toContain('Tuxtla');
    expect(vision).toContain('responde solo la pregunta');
    expect(vision).not.toContain('github.com');
  });

  it('keeps verified creator links across a contextual follow-up', () => {
    const prompts = creatorSystemPrompt([
      { role: 'user', content: 'quien te creo' },
      { role: 'assistant', content: 'TrinaxCode creó TrinaxAI.' },
      { role: 'user', content: 'cuales son sus enlaces' },
    ], 'es');
    expect(prompts).toHaveLength(1);
    expect(prompts[0].content).toContain('https://github.com/TrinaxCode');
    expect(prompts[0].content).toContain('https://www.linkedin.com/in/trinaxcode/');
    expect(prompts[0].content).toContain('https://www.tiktok.com/@trinaxcode');
    expect(prompts[0].content).toContain('https://www.instagram.com/trinaxcode/');
    expect(prompts[0].content).not.toContain('wa.me');
    expect(prompts[0].content).not.toContain('github.com/TrinaxAI');
    expect(prompts[0].content).not.toContain('Stack Overflow');
  });

  it('routes code prompts to the code model', () => {
    expect(routeOllamaModel('fix this python traceback')).toBe('qwen3.5:4b');
  });

  it('routes identity questions to chat, never the fast model', () => {
    expect(routeOllamaModel('quién te creó')).toBe('qwen3.5:4b');
  });

  it('keeps vision presets sized for each hardware profile', () => {
    expect(MODEL_PRESETS.low['tc-models-vision']).toBe('qwen3.5:2b');
    expect(MODEL_PRESETS.balanced['tc-models-vision']).toBe('qwen3.5:4b');
    expect(MODEL_PRESETS.max['tc-models-vision']).toBe('qwen3.5:9b');
    expect(MODEL_PRESETS.ultra['tc-models-vision']).toBe('qwen3.5:35b');
  });

  it('removes only previously managed profile models before pulling the new profile', async () => {
    localStorage.setItem('tc-managed-ollama-models', JSON.stringify(['granite4:3b', 'bge-m3']));
    const requests: Array<[string, RequestInit | undefined]> = [];
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
      requests.push([url, init]);
      return Promise.resolve(new Response('{}', { status: 200 }));
    }));

    await reconcileManagedModels(['qwen3.5:2b', 'bge-m3']);

    expect(requests.some(([url, init]) => url.endsWith('/api/delete')
      && init?.method === 'DELETE' && String(init.body).includes('granite4:3b'))).toBe(true);
    expect(requests.some(([url, init]) => url.endsWith('/api/delete')
      && String(init.body).includes('bge-m3'))).toBe(false);
    expect(JSON.parse(localStorage.getItem('tc-managed-ollama-models') || '[]')).toEqual([
      'bge-m3', 'qwen3.5:2b',
    ]);
    vi.unstubAllGlobals();
  });

  it('keeps the warm coder for an ambiguous follow-up', () => {
    expect(routeOllamaModel('hazlo más corto', [
      { role: 'user', content: 'fix this python traceback' },
      { role: 'assistant', content: '...', model: 'qwen3.5:4b' },
      { role: 'user', content: 'hazlo más corto' },
    ])).toBe('qwen3.5:4b');
  });

  it('switches between everyday chat and code only on clear intent', () => {
    const codeChat = [
      { role: 'assistant' as const, content: '...', model: 'qwen3.5:4b' },
    ];
    expect(routeOllamaModel('cambiando de tema, dame una receta', codeChat)).toBe('qwen3.5:4b');
    expect(routeOllamaModel('crea una función en Python', [
      { role: 'assistant', content: '...', model: 'qwen3.5:9b' },
    ])).toBe('qwen3.5:4b');
  });

  it('does not send generic analysis to the large deep model', () => {
    expect(routeOllamaModel('analiza la historia de México con una explicación clara')).toBe('qwen3.5:4b');
  });

  it('routes math/analytical prompts to the general instruct model, not a coder', () => {
    // A math exam mentions "algoritmo"/"grafo" and may use inline `code` ticks,
    // but must stay on the general instruct model (which answers math well) —
    // never a coder nor the un-installable 30B deep model.
    expect(routeOllamaModel('Resuelve la integral de x^2 y explica cada paso del algoritmo'))
      .toBe('qwen3.5:4b');
    expect(routeOllamaModel('Dado un grafo, calcula el número de aristas y demuéstralo con una `variable` n'))
      .toBe('qwen3.5:4b');
    // A long, multi-part analytical prompt still stays on the general model,
    // never the 30B coder (which is not installed on a 16GB CPU box).
    expect(routeOllamaModel(`Analiza a fondo este examen de matemáticas. ${'x'.repeat(1500)}`))
      .toBe('qwen3.5:4b');
  });

  it('routes a mixed maths exam with a Python fence to Qwen3.5, not the coder', () => {
    const exam = `# Examen de Matemáticas y Algoritmos
Resuelve el sistema de ecuaciones por eliminación de Gauss.
Calcula el determinante, la integral y el límite.
Demuestra por inducción y aplica Dijkstra a un grafo ponderado.
Analiza la recurrencia con el Teorema Maestro y P vs NP.
\`\`\`python
def mystery(A):
    return mystery(A[:len(A)//2])
\`\`\``;
    expect(isAnalyticalReasoning(exam)).toBe(true);
    expect(routeOllamaModel(exam)).toBe('qwen3.5:4b');
  });

  it('splits a long numbered exam into stable three-question batches', () => {
    const exam = `# Examen\n${Array.from({ length: 15 }, (_, index) => `### ${index + 1}.\nPregunta ${index + 1}`).join('\n\n')}`;
    const batches = splitAnalyticalTask(exam);
    expect(batches).toHaveLength(5);
    expect(batches[0]).toContain('### 1.');
    expect(batches[0]).toContain('### 3.');
    expect(batches[0]).not.toContain('### 4.');
    expect(batches[4]).toContain('### 15.');
  });

  it('rejects analytical draft leakage and incomplete blocks before display', () => {
    const task = '### 8.\nDemuestra por inducción.\n\n### 9.\nAnaliza el grafo.';
    const bad = '### 8.\nNo, espera. Rehagamos desde cero: el resultado =';
    const good = '### 8.\nCaso base e hipótesis inductiva completos. Por tanto, se cumple.\n\n### 9.\nEl grafo tiene exactamente dos vértices impares; por ello posee camino euleriano.';
    expect(analyticalQualityIssues(bad, task)).toEqual(expect.arrayContaining([
      'contiene tanteos o autocorrecciones visibles',
      'termina en una expresión incompleta',
      'falta el ejercicio 9',
    ]));
    expect(analyticalQualityIssues(good, task)).toEqual([]);
  });

  it('detects the language of the current turn using complete words', () => {
    expect(detectTurnLanguage('¿Puedes explicar este error?')).toBe('es');
    expect(detectTurnLanguage('Can you explain this error?')).toBe('en');
    expect(detectTurnLanguage('hola como estas')).toBe('es');
    expect(detectTurnLanguage('hello how are you')).toBe('en');
  });

  it('generates compact chat titles', () => {
    const title = generateTitle('Explain this project in detail and include examples');
    expect(title).toMatch(/^Explain this project/);
    expect(title.length).toBeLessThanOrEqual(48);
  });

  it('accepts modern and legacy office files for document handling', () => {
    const files = [
      new File(['demo'], 'deck.pptx'),
      new File(['demo'], 'legacy.ppt'),
      new File(['demo'], 'budget.xlsx'),
      new File(['demo'], 'notes.odt'),
    ];
    expect(indexableFilesFrom(files).map((file) => file.name)).toEqual([
      'deck.pptx', 'legacy.ppt', 'budget.xlsx', 'notes.odt',
    ]);
  });

  it('parses RAG SSE stream lines', () => {
    expect(parseRagSseLine('data: {"choices":[{"delta":{"content":"hola"}}]}')).toEqual({ token: 'hola' });
    expect(parseRagSseLine('data: {"trinaxai":{"model":"m","project":"p"}}')).toEqual({
      meta: { model: 'm', project: 'p' },
    });
    expect(parseRagSseLine('data: [DONE]')).toEqual({ done: true });
  });

  it('surfaces Ollama errors emitted after a stream has started', () => {
    expect(parseOllamaJsonLine('{"error":"runner crashed"}')).toEqual({ error: 'runner crashed' });
    expect(parseOllamaJsonLine('{"message":{"content":"hola"}}')).toEqual({ token: 'hola' });
  });

  it('recognizes Gemma SentencePiece markers in streamed model output', () => {
    expect(parseOllamaJsonLine('{"message":{"content":"▁▁Actúa"}}')).toEqual({ token: '▁▁Actúa' });
  });

  it('extracts qwen3-vl thinking + done_reason so an empty-content turn is detectable', () => {
    // qwen3-vl streams its reasoning in a separate `thinking` field with empty
    // content; the old parser dropped it and a whole "thought away the budget"
    // turn looked like nothing happened. We now expose both signals.
    expect(parseOllamaJsonLine('{"message":{"content":"","thinking":"So the"}}')).toEqual({ thinking: 'So the' });
    expect(parseOllamaJsonLine('{"message":{"content":"rojo"},"done":false}')).toEqual({ token: 'rojo' });
    expect(parseOllamaJsonLine('{"message":{"content":""},"done":true,"done_reason":"length"}'))
      .toEqual({ doneReason: 'length' });
  });

  it('supports explicit multi-context RAG collection selection', () => {
    expect(nextActiveCollections(['default'], 'prueba')).toEqual(['prueba']);
    expect(nextActiveCollections(['prueba'], 'default')).toEqual(['prueba', 'default']);
    expect(nextActiveCollections(['prueba', 'default'], 'default')).toEqual(['prueba']);
    expect(nextActiveCollections(['prueba'], 'docs')).toEqual(['prueba', 'docs']);
    expect(normalizeActiveCollections(['default', 'prueba'])).toEqual(['default', 'prueba']);
  });

  it('scopes source chunks and deletion to the selected source root', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(new Response(JSON.stringify({
        collection: 'default',
        file: 'shared.md',
        source_id: 'alpha-root',
        total: 0,
        chunks: [],
        deleted: 1,
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })));
    vi.stubGlobal('fetch', fetchMock);
    try {
      await getFileChunks('default', 'shared.md', { sourceId: 'alpha-root' });
      await deleteSource('default', 'shared.md', 'alpha-root');

      expect(String(fetchMock.mock.calls[0][0])).toContain('source_id=alpha-root');
      expect(String(fetchMock.mock.calls[1][0])).toContain('source_id=alpha-root');
      expect(fetchMock.mock.calls[1][1]?.method).toBe('DELETE');
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('keeps the newest chat context within the local model budget', () => {
    const compacted = compactChatContext([
      { role: 'user', content: 'old context '.repeat(100) },
      { role: 'assistant', content: 'middle answer '.repeat(100) },
      { role: 'user', content: `current question ${'x'.repeat(300)}` },
    ], 500);
    const total = compacted.reduce((sum, message) => sum + message.content.length, 0);

    expect(total).toBeLessThanOrEqual(500);
    expect(compacted.at(-1)?.content).toContain('current question');
    expect(compacted.at(-1)?.content).toContain('x'.repeat(100));
  });

  it('authenticates Ollama discovery and streamed chat requests', async () => {
    clearOllamaModelAvailabilityCache();
    sessionStorage.setItem('trinaxai-admin-token', 'ollama-secret');
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/tags')) {
        return Promise.resolve(new Response(JSON.stringify({ models: [{ name: 'qwen3.5:9b' }] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }));
      }
      if (url.endsWith('/api/chat')) {
        return Promise.resolve(new Response('{"message":{"content":"hola"},"done":true}\n', { status: 200 }));
      }
      return Promise.resolve(new Response('{}', { status: 200 }));
    });
    vi.stubGlobal('fetch', fetchMock);
    try {
      const answer = await streamOllama([{ role: 'user', content: 'salúdame brevemente' }], () => undefined);
      expect(answer).toBe('hola');
      const ollamaCalls = fetchMock.mock.calls.filter(([input]) => String(input).includes('/api/ollama/'));
      expect(ollamaCalls.length).toBeGreaterThanOrEqual(2);
      ollamaCalls.forEach(([, init]) => {
        expect((init?.headers as Headers).get('X-Admin-Token')).toBe('ollama-secret');
      });
    } finally {
      sessionStorage.clear();
      vi.unstubAllGlobals();
    }
  });

  it('treats the selected RAG engine as explicit knowledge mode', async () => {
    sessionStorage.setItem('trinaxai-admin-token', 'rag-secret');
    const frames = [
      'data: {"trinaxai":{"model":"qwen","project":null,"mode":"knowledge","rag_used":true,"collections":["docs"]}}',
      'data: {"choices":[{"delta":{"content":"grounded"}}]}',
      'data: {"trinaxai_sources":[],"trinaxai_retrieval":{"mode":"knowledge","rag_used":true,"result_count":0,"collections":["docs"]}}',
      'data: [DONE]',
      '',
    ].join('\n');
    const fetchMock = vi.fn().mockResolvedValue(new Response(frames, { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const metadata: Array<Record<string, unknown>> = [];
    try {
      const answer = await streamRag(
        [{ role: 'user', content: '¿Cuál es el animal guardián de Aurora?' }],
        () => undefined,
        undefined,
        (meta) => metadata.push(meta),
        { collections: ['docs'] },
      );
      expect(answer).toBe('grounded');
      const [, init] = fetchMock.mock.calls[0];
      expect(JSON.parse(String(init?.body))).toMatchObject({
        mode: 'knowledge',
        collections: ['docs'],
      });
      expect((init?.headers as Headers).get('X-Admin-Token')).toBe('rag-secret');
      expect(metadata).toEqual(expect.arrayContaining([
        expect.objectContaining({ mode: 'knowledge', rag_used: true, collections: ['docs'] }),
        expect.objectContaining({ result_count: 0, sources: [] }),
      ]));
    } finally {
      sessionStorage.clear();
      vi.unstubAllGlobals();
    }
  });

  it('closes RAG streaming with the server error instead of a partial success', async () => {
    const frames = ['data: {"choices":[{"delta":{"content":"partial"}}]}', 'data: {"trinaxai_error":"embedding failed"}', ''].join('\n');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(frames, { status: 200 })));
    try {
      await expect(streamRag([{ role: 'user', content: 'consulta' }], () => undefined))
        .rejects.toThrow('embedding failed');
    } finally { vi.unstubAllGlobals(); }
  });
});
