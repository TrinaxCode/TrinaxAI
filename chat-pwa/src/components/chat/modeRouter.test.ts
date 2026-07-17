import { describe, expect, it } from 'vitest';
import {
  compactAgentContext,
  decideAssistantMode,
  persistTurnDecision,
  restoreTurnDecision,
} from './modeRouter';

describe('assistant mode router', () => {
  it('keeps stable general questions in ordinary chat', () => {
    expect(decideAssistantMode('¿Qué es Fortnite?').mode).toBe('chat');
    expect(decideAssistantMode('Diseña una página web responsive').mode).toBe('chat');
    expect(decideAssistantMode('Explícame cómo funciona Internet').mode).toBe('chat');
  });

  it('routes current information and explicit web requests to web search', () => {
    expect(decideAssistantMode('¿En qué temporada está Fortnite actualmente?').mode).toBe('web');
    expect(decideAssistantMode('Busca en Internet la versión actual de React').webSearch).toBe(true);
    expect(decideAssistantMode('Activa el modo búsqueda para esta pregunta').mode).toBe('web');
  });

  it('routes multi-source work to deep research', () => {
    const route = decideAssistantMode('Investiga a fondo este tema usando múltiples fuentes y perspectivas');
    expect(route.mode).toBe('deep_research');
    expect(route.webSearch).toBe(true);
    expect(route.depth).toBe(3);
    expect(decideAssistantMode('Usa deepresearch para comparar este tema').mode).toBe('deep_research');
  });

  it('routes only explicit workspace actions to agent mode', () => {
    expect(decideAssistantMode('Corrige el bug en los archivos del proyecto y ejecuta las pruebas').mode).toBe('agent');
    expect(decideAssistantMode('Dame un ejemplo de código para corregir un bug').mode).toBe('chat');
  });

  it('gives attached images and manual modes precedence', () => {
    expect(decideAssistantMode('¿Qué ves?', { hasImage: true, webMode: true }).mode).toBe('vision');
    expect(decideAssistantMode('Una pregunta', { webMode: true }).mode).toBe('web');
    expect(decideAssistantMode('Una pregunta', { webMode: true, researchMode: true })).toMatchObject({
      mode: 'deep_research', webSearch: true, depth: 3,
    });
  });

  it('can select indexed knowledge without changing the permanent engine', () => {
    expect(decideAssistantMode('Respóndeme usando el modo RAG').mode).toBe('rag');
  });

  it('persists and restores the original mode and collection scope', () => {
    const original = decideAssistantMode('Busca en Internet la versión actual de React');
    const persisted = persistTurnDecision(original, ['docs', 'code']);

    expect(persisted.collections).toEqual(['docs', 'code']);
    expect(restoreTurnDecision(persisted)).toMatchObject({
      mode: 'web',
      webSearch: true,
      announce: false,
    });
  });

  it('compacts agent context without attachment payload fields', () => {
    const context = compactAgentContext([
      { role: 'user', content: 'Pregunta anterior', image: 'data:image/png;base64,large' },
      { role: 'assistant', content: 'Respuesta anterior' },
    ]);
    expect(context).toEqual([
      { role: 'user', content: 'Pregunta anterior' },
      { role: 'assistant', content: 'Respuesta anterior' },
    ]);
  });
});
