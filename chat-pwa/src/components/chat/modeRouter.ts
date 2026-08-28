import type { ChatEngine, ChatMessage, ChatTurnMetadata } from '../../lib/api';

export type AssistantMode = 'chat' | 'vision' | 'web' | 'deep_research' | 'agent' | 'rag';

export interface TurnRouteDecision extends Omit<ChatTurnMetadata, 'mode' | 'collections'> {
  mode: AssistantMode;
}

export interface RouteContext {
  history?: ChatMessage[];
  hasImage?: boolean;
  hasDocuments?: boolean;
  webMode?: boolean;
  researchMode?: boolean;
  agentMode?: boolean;
  engine?: ChatEngine;
}

export interface AgentHandoff {
  id: string;
  prompt: string;
  context: ChatMessage[];
}

const normalize = (value: string) => value
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .replace(/\s+/g, ' ')
  .trim()
  .toLowerCase();

const has = (text: string, expression: RegExp) => expression.test(text);

const EXPLICIT_AGENT = /\b(?:modo agente|agente trinax|usa(?:r)? el agente|agent mode|use the agent)\b/i;
const EXPLICIT_WEB = /\b(?:modo busqueda|busqueda web|web search|search mode)\b|\b(?:busca|buscar|consulta|investiga|verifica|search|look up|check)\b.{0,35}\b(?:internet|web|online|en linea)\b|\b(?:internet|web|online|en linea)\b.{0,35}\b(?:busca|buscar|consulta|investiga|verifica|search|check)\b/i;
const DIRECT_LOOKUP = /\b(?:busca|buscar|buscame|búscame|buscalo|búscalo|search|look up|find out)\b\s+(?!como\b|how\b)\S+/i;
const CURRENT_INFO = /\b(?:actual|actualmente|ahora|hoy|ultima|ultimo|ultimas|ultimos|reciente|noticias|novedades|temporada|precio|cotizacion|version actual|latest|current|today|recent|news|season|price|schedule|weather|clima)\b/i;
const DEEP = /\b(?:investiga a fondo|investigacion profunda|investigacion compleja|modo investigacion|analisis exhaustivo|estudio exhaustivo|analisis comparativo|revision de varias fuentes|informe detallado|compara varias fuentes|multiples fuentes|distintas perspectivas|deep\s*research|research thoroughly|complex research|comprehensive research|multiple sources|detailed report|comparative analysis)\b/i;
const LOCAL_GROUNDING = /\b(?:modo rag|rag mode|mis archivos|mis documentos|mi proyecto|mi repo|repositorio|documentos indexados|base de conocimiento|indexed documents|my files|my documents|my project|my repo|knowledge base)\b/i;
const PERSONAL_KNOWLEDGE = /\b(?:he hecho|hice|he creado|mis programas|mis proyectos|mi trabajo|mi codigo|mis aplicaciones|cuando hice|lo que hice|lo que he hecho|proyectos que hice|proyectos hice|i made|i created|what i made|what i built|my projects|my work|my code|my apps|projects i made)\b/i;
const EDUCATIONAL_ONLY = /\b(?:explica(?:me|r)?|como|ejemplo|ensena(?:me|r)?|explain|how to|example|teach)\b.{0,100}\b(?:editar|modificar|corregir|ejecutar|instalar|crear|construir|disenar|desarrollar|edit|modify|fix|run|install|create|build|design|develop)\b/i;
const EXPLICIT_NEGATION = /\b(?:no|sin|never|don't|do not|solo|just)\b.{0,40}\b(?:modificar|editar|ejecutar|instalar|modify|edit|run|install)\b/i;

function decision(
  mode: AssistantMode,
  source: TurnRouteDecision['source'],
  reason: string,
  options: Partial<Pick<TurnRouteDecision, 'webSearch' | 'depth' | 'announce'>> = {},
): TurnRouteDecision {
  return {
    mode,
    source,
    reason,
    webSearch: options.webSearch ?? false,
    depth: options.depth ?? 1,
    announce: options.announce ?? source === 'rule',
  };
}

export function decideAssistantMode(prompt: string, context: RouteContext = {}): TurnRouteDecision {
  const current = normalize(prompt);

  if (context.hasImage) return decision('vision', 'manual', 'image_attached', { announce: false });
  if (context.agentMode || has(current, EXPLICIT_AGENT)) return decision('agent', context.agentMode ? 'manual' : 'rule', context.agentMode ? 'manual_agent' : 'explicit_agent', { announce: false });
  const localGrounding = has(current, LOCAL_GROUNDING) || has(current, PERSONAL_KNOWLEDGE);
  const directLookup = has(current, DIRECT_LOOKUP);
  const explicitWeb = has(current, EXPLICIT_WEB);
  const ragRequested = context.engine === 'rag' || localGrounding;
  const educationalOnly = has(current, EDUCATIONAL_ONLY) || has(current, EXPLICIT_NEGATION);
  // Search is an available tool, not a higher-priority route. An explicit RAG
  // engine or a question about local knowledge must stay grounded unless the
  // user explicitly asks for current/public web information.
  if (ragRequested && !explicitWeb && !has(current, CURRENT_INFO)) {
    return decision(
      'rag',
      context.engine === 'rag' ? 'manual' : 'rule',
      context.engine === 'rag' ? 'manual_rag' : 'local_grounding',
      { announce: context.engine !== 'rag' },
    );
  }
  if (directLookup
    && !explicitWeb
    && !educationalOnly
    && !localGrounding
    && !has(current, DEEP)
    && context.engine !== 'rag'
    && !context.webMode
    && !context.researchMode) {
    return decision('web', 'rule', 'direct_lookup', { webSearch: true });
  }
  if (context.webMode && context.researchMode) {
    return decision('deep_research', 'manual', 'manual_web_research', { webSearch: true, depth: 3, announce: false });
  }
  if (context.webMode) return decision('web', 'manual', 'manual_web', { webSearch: true, announce: false });
  if (context.researchMode) {
    return decision('deep_research', 'manual', 'manual_research', { depth: 2, announce: false });
  }
  if (explicitWeb) return decision('web', 'rule', 'explicit_web', { webSearch: true });

  if (has(current, DEEP)) {
    const local = localGrounding && !has(current, EXPLICIT_WEB) && !has(current, CURRENT_INFO);
    return decision('deep_research', 'rule', local ? 'deep_local' : 'deep_web', {
      webSearch: !local,
      depth: 3,
    });
  }
  if (localGrounding) return decision('rag', 'rule', 'local_grounding');
  if (context.engine === 'rag') return decision('rag', 'manual', 'manual_rag', { announce: false });
  return decision('chat', 'rule', 'ordinary_chat', { announce: false });
}

export function compactAgentContext(messages: ChatMessage[]): ChatMessage[] {
  let remaining = 6000;
  const compacted: ChatMessage[] = [];
  for (const message of messages.filter((item) => item.role === 'user' || item.role === 'assistant').slice(-8).reverse()) {
    if (remaining <= 0) break;
    const visible = (message.displayContent ?? message.content).replace(/\s+/g, ' ').trim();
    if (!visible) continue;
    const content = visible.slice(-Math.min(1200, remaining));
    remaining -= content.length;
    compacted.push({ role: message.role, content });
  }
  return compacted.reverse();
}

export function newHandoffId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `agent-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
}

export function persistTurnDecision(
  route: TurnRouteDecision,
  collections: string[],
): ChatTurnMetadata {
  return { ...route, collections: [...collections] };
}

export function restoreTurnDecision(turn?: ChatTurnMetadata): TurnRouteDecision | null {
  if (!turn) return null;
  return {
    mode: turn.mode,
    source: turn.source,
    reason: turn.reason,
    webSearch: turn.webSearch,
    depth: turn.depth,
    announce: false,
  };
}
