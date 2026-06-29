import { describe, expect, it } from 'vitest';

import { generateTitle, parseRagSseLine, routeOllamaModel } from './api';

describe('api helpers', () => {
  it('routes code prompts to the code model', () => {
    expect(routeOllamaModel('fix this python traceback')).toBe('qwen2.5-coder:3b');
  });

  it('generates compact chat titles', () => {
    const title = generateTitle('Explain this project in detail and include examples');
    expect(title).toMatch(/^Explain this project/);
    expect(title.length).toBeLessThanOrEqual(48);
  });

  it('parses RAG SSE stream lines', () => {
    expect(parseRagSseLine('data: {"choices":[{"delta":{"content":"hola"}}]}')).toEqual({ token: 'hola' });
    expect(parseRagSseLine('data: {"trinaxai":{"model":"m","project":"p"}}')).toEqual({
      meta: { model: 'm', project: 'p' },
    });
    expect(parseRagSseLine('data: [DONE]')).toEqual({ done: true });
  });
});
