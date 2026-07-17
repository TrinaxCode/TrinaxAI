import { describe, expect, it } from 'vitest';

import { parseRagSseLine } from './api';

describe('SSE stream parser', () => {
  it('parses a regular content token', () => {
    const result = parseRagSseLine('data: {"choices":[{"delta":{"content":"Hello"}}]}');
    expect(result).toEqual({ token: 'Hello' });
  });

  it('parses model/project meta', () => {
    const result = parseRagSseLine('data: {"trinaxai":{"model":"qwen2.5","project":"my-app"}}');
    expect(result).toEqual({ meta: { model: 'qwen2.5', project: 'my-app' } });
  });

  it('detects [DONE] signal', () => {
    expect(parseRagSseLine('data: [DONE]')).toEqual({ done: true });
  });

  it('returns empty object for empty/missing data prefix', () => {
    expect(parseRagSseLine('')).toEqual({});
    expect(parseRagSseLine('not-data: x')).toEqual({});
    expect(parseRagSseLine(': heartbeat')).toEqual({});
  });

  it('returns empty object for malformed JSON', () => {
    expect(parseRagSseLine('data: {broken')).toEqual({});
    expect(parseRagSseLine('data:   ')).toEqual({});
  });

  it('handles Unicode content', () => {
    const result = parseRagSseLine('data: {"choices":[{"delta":{"content":"🚀 Hola"}}]}');
    expect(result).toEqual({ token: '🚀 Hola' });
  });

  it('parses trinaxai_sources', () => {
    const line = 'data: {"trinaxai_sources":[{"file":"a.py","project":"x","snippet":"p"}]}';
    const result = parseRagSseLine(line);
    expect(result.meta?.sources).toHaveLength(1);
    expect(result.meta?.sources?.[0].file).toBe('a.py');
  });

  it('parses retrieval decisions from preview and final metadata', () => {
    expect(parseRagSseLine('data: {"trinaxai":{"model":"qwen","project":null,"mode":"knowledge","rag_used":true,"collections":["docs"]}}')).toEqual({
      meta: {
        model: 'qwen',
        project: null,
        mode: 'knowledge',
        rag_used: true,
        collections: ['docs'],
      },
    });
    expect(parseRagSseLine('data: {"trinaxai_sources":[],"trinaxai_retrieval":{"mode":"knowledge","rag_used":true,"result_count":4,"collections":["docs"]}}')).toEqual({
      meta: {
        sources: [],
        mode: 'knowledge',
        rag_used: true,
        result_count: 4,
        collections: ['docs'],
      },
    });
  });

  it('handles empty content token', () => {
    expect(parseRagSseLine('data: {"choices":[{"delta":{"content":""}}]}')).toEqual({});
  });

  it('surfaces backend stream errors', () => {
    expect(parseRagSseLine('data: {"trinaxai_error":"model failed"}')).toEqual({
      error: 'model failed',
    });
  });
});
