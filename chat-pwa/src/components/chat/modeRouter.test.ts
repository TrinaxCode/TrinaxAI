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
    expect(decideAssistantMode('Quiero crear una página web para mi negocio').mode).toBe('chat');
    expect(decideAssistantMode('Quiero crear una pagina web para mi negocio').mode).toBe('chat');
    expect(decideAssistantMode('Explícame cómo diseñar una página web').mode).toBe('chat');
    expect(decideAssistantMode('Explícame cómo funciona Internet').mode).toBe('chat');
  });

  it('routes current information and explicit web requests to web search', () => {
    expect(decideAssistantMode('¿En qué temporada está Fortnite actualmente?').mode).toBe('chat');
    expect(decideAssistantMode('Busca en Internet la versión actual de React').webSearch).toBe(true);
    expect(decideAssistantMode('Busca quién es TrinaxCode')).toMatchObject({ mode: 'web', reason: 'direct_lookup', webSearch: true });
    expect(decideAssistantMode('Busca qué es una tecnología')).toMatchObject({ mode: 'web', webSearch: true });
    expect(decideAssistantMode('Busca en mis documentos el contrato').mode).toBe('rag');
    expect(decideAssistantMode('Activa el modo búsqueda para esta pregunta').mode).toBe('web');
  });

  it('routes public lookups to web and personal project history to RAG', () => {
    expect(decideAssistantMode('Busca cuándo fue el último partido del Real Madrid')).toMatchObject({ mode: 'web', webSearch: true });
    expect(decideAssistantMode('Dime qué programas Python he hecho')).toMatchObject({ mode: 'rag', webSearch: false });
    expect(decideAssistantMode('Qué proyectos hice')).toMatchObject({ mode: 'rag', webSearch: false });
    expect(decideAssistantMode('Busca cuándo hice el proyecto Tal')).toMatchObject({ mode: 'rag', webSearch: false });
    expect(decideAssistantMode('Cómo crear un programa en Python').mode).toBe('chat');
  });

  it('does not inherit local grounding from an unrelated previous turn', () => {
    expect(decideAssistantMode('Quiero crear una página web para mi negocio', {
      history: [
        { role: 'user', content: 'Dime qué programas Python he hecho' },
        { role: 'assistant', content: 'RAG result' },
      ],
    }).mode).toBe('chat');
  });

  it('routes multi-source work to deep research', () => {
    const route = decideAssistantMode('Investiga a fondo este tema usando múltiples fuentes y perspectivas');
    expect(route.mode).toBe('deep_research');
    expect(route.webSearch).toBe(true);
    expect(route.depth).toBe(3);
    expect(decideAssistantMode('Usa deepresearch para comparar este tema').mode).toBe('deep_research');
    expect(decideAssistantMode('Haz una investigación compleja sobre este tema')).toMatchObject({ mode: 'deep_research', webSearch: true, depth: 3 });
  });

  it('keeps workspace actions in chat until agent mode is explicitly enabled', () => {
    expect(decideAssistantMode('Corrige el bug en los archivos del proyecto y ejecuta las pruebas').mode).toBe('chat');
    expect(decideAssistantMode('Corrige el bug en los archivos del proyecto y ejecuta las pruebas', { agentMode: true })).toMatchObject({
      mode: 'agent', source: 'manual', reason: 'manual_agent',
    });
    expect(decideAssistantMode('Dame un ejemplo de código para corregir un bug').mode).toBe('chat');
    expect(decideAssistantMode('Explícame cómo editar un archivo').mode).toBe('chat');
  });

  it('does not promote mixed evidence or implementation wording to agent mode', () => {
    expect(decideAssistantMode('Compara lo que dicen mis documentos con información web reciente').mode).not.toBe('agent');
    expect(decideAssistantMode('Investiga a fondo X y luego modifica el archivo de resultados').mode).not.toBe('agent');
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

  it('keeps local questions on RAG when web search is enabled', () => {
    expect(decideAssistantMode('¿Qué dice mi proyecto sobre la configuración?', {
      webMode: true,
      engine: 'ollama',
    })).toMatchObject({ mode: 'rag', webSearch: false });
    expect(decideAssistantMode('Una pregunta', { webMode: true, engine: 'rag' }).mode).toBe('rag');
    expect(decideAssistantMode('Busca en Internet la versión actual de React', {
      webMode: true,
      engine: 'rag',
    }).mode).toBe('web');
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
