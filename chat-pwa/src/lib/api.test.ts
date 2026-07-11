import { describe, expect, it } from 'vitest';

import {
  generateTitle,
  compactChatContext,
  detectTurnLanguage,
  indexableFilesFrom,
  nextActiveCollections,
  normalizeActiveCollections,
  parseOllamaJsonLine,
  parseRagSseLine,
  routeOllamaModel,
} from './api';

describe('api helpers', () => {
  it('routes code prompts to the code model', () => {
    expect(routeOllamaModel('fix this python traceback')).toBe('qwen2.5-coder:3b');
  });

  it('keeps the warm coder for an ambiguous follow-up', () => {
    expect(routeOllamaModel('hazlo más corto', [
      { role: 'user', content: 'fix this python traceback' },
      { role: 'assistant', content: '...', model: 'qwen2.5-coder:3b' },
      { role: 'user', content: 'hazlo más corto' },
    ])).toBe('qwen2.5-coder:3b');
  });

  it('switches between everyday chat and code only on clear intent', () => {
    const codeChat = [
      { role: 'assistant' as const, content: '...', model: 'qwen2.5-coder:3b' },
    ];
    expect(routeOllamaModel('cambiando de tema, dame una receta', codeChat)).toBe('qwen3:4b-instruct-2507-q4_K_M');
    expect(routeOllamaModel('crea una función en Python', [
      { role: 'assistant', content: '...', model: 'qwen3:4b-instruct-2507-q4_K_M' },
    ])).toBe('qwen2.5-coder:3b');
  });

  it('does not send generic analysis to the large deep model', () => {
    expect(routeOllamaModel('analiza la historia de México con una explicación clara')).toBe('qwen3:4b-instruct-2507-q4_K_M');
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

  it('accepts modern PowerPoint files for document handling', () => {
    const files = [
      new File(['demo'], 'deck.pptx'),
      new File(['demo'], 'legacy.ppt'),
    ];
    expect(indexableFilesFrom(files).map((file) => file.name)).toEqual(['deck.pptx']);
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

  it('supports explicit multi-context RAG collection selection', () => {
    expect(nextActiveCollections(['default'], 'prueba')).toEqual(['prueba']);
    expect(nextActiveCollections(['prueba'], 'default')).toEqual(['prueba', 'default']);
    expect(nextActiveCollections(['prueba', 'default'], 'default')).toEqual(['prueba']);
    expect(nextActiveCollections(['prueba'], 'docs')).toEqual(['prueba', 'docs']);
    expect(normalizeActiveCollections(['default', 'prueba'])).toEqual(['default', 'prueba']);
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
});
