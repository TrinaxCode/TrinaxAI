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
const CURRENT_INFO = /\b(?:actual|actualmente|ahora|hoy|ultima|ultimo|ultimas|ultimos|reciente|noticias|novedades|temporada|precio|cotizacion|version actual|latest|current|today|recent|news|season|price|schedule|weather|clima)\b/i;
const DEEP = /\b(?:investiga a fondo|investigacion profunda|modo investigacion|analisis exhaustivo|informe detallado|compara varias fuentes|multiples fuentes|distintas perspectivas|deep\s*research|research thoroughly|comprehensive research|multiple sources|detailed report)\b/i;
const LOCAL_GROUNDING = /\b(?:modo rag|rag mode|mis archivos|mis documentos|mi proyecto|mi repo|repositorio|documentos indexados|base de conocimiento|indexed documents|my files|my documents|my project|my repo|knowledge base)\b/i;
const AGENT_ACTION = /\b(?:modifica|edita|corrige|implementa|agrega|anade|elimina|refactoriza|ejecuta|instala|actualiza|crea|arregla|aplica|modify|edit|fix|implement|add|delete|remove|refactor|run|execute|install|update|create|apply)\b/i;
const AGENT_TARGET = /\b(?:archivo|archivos|proyecto|repo|repositorio|codigo fuente|componente|tests?|pruebas|comando|terminal|dependencias|package\.json|file|files|project|repository|codebase|component|command|dependencies)\b/i;

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
  const recentTopic = normalize((context.history ?? [])
    .filter((message) => message.role === 'user')
    .slice(-2)
    .map((message) => message.displayContent ?? message.content)
    .join(' '));
  const contextual = `${recentTopic} ${current}`.trim();

  if (context.hasImage) return decision('vision', 'manual', 'image_attached', { announce: false });
  if (has(current, EXPLICIT_AGENT)) return decision('agent', 'rule', 'explicit_agent');
  if (context.webMode && context.researchMode) {
    return decision('deep_research', 'manual', 'manual_web_research', { webSearch: true, depth: 3, announce: false });
  }
  if (context.webMode) return decision('web', 'manual', 'manual_web', { webSearch: true, announce: false });
  if (context.researchMode) {
    return decision('deep_research', 'manual', 'manual_research', { depth: 2, announce: false });
  }
  if (has(current, EXPLICIT_WEB)) return decision('web', 'rule', 'explicit_web', { webSearch: true });

  const agentTask = has(current, AGENT_ACTION) && has(contextual, AGENT_TARGET);
  if (agentTask && !context.hasDocuments) return decision('agent', 'rule', 'workspace_action');

  if (has(current, DEEP)) {
    const local = has(contextual, LOCAL_GROUNDING) && !has(current, EXPLICIT_WEB) && !has(current, CURRENT_INFO);
    return decision('deep_research', 'rule', local ? 'deep_local' : 'deep_web', {
      webSearch: !local,
      depth: 3,
    });
  }
  if (has(current, CURRENT_INFO)) return decision('web', 'rule', 'current_information', { webSearch: true });
  if (has(current, LOCAL_GROUNDING)) return decision('rag', 'rule', 'local_grounding');
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
