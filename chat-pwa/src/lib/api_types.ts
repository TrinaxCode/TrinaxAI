/** Shared browser API contracts and chat metadata. */

export type ChatEngine = 'ollama' | 'rag';

/** Fuente citada por el RAG (archivo, proyecto, fragmento). */
export interface Source {
  file: string;
  url?: string | null;
  search_url?: string | null;
  title?: string | null;
  kind?: 'local' | 'web' | string;
  provider?: string | null;
  authority?: 'primary' | 'secondary' | string | null;
  content_scope?: string | null;
  fetch_error?: string | null;
  canonical_url?: string | null;
  author?: string | null;
  published_at?: string | null;
  project: string;
  collection_id?: string;
  collection?: string;
  page?: string | number | null;
  snippet: string;
  score: number | null;
}
export interface WebSearchSettings {
  enabled: boolean;
  preferred_provider: 'auto' | 'duckduckgo' | 'brave' | 'searxng' | 'disabled';
  active_provider: string;
  source: 'default' | 'managed' | 'environment';
  externally_managed: Record<string, boolean>;
  providers: Record<string, {
    available: boolean;
    configured: boolean;
    requires_api_key: boolean;
    base_url?: string | null;
  }>;
}

/** Metadatos que el backend emite durante el stream (modelo, proyecto, fuentes). */
export interface StreamMeta {
  model?: string;
  project?: string | null;
  mode?: 'auto' | 'knowledge' | 'model';
  rag_used?: boolean;
  result_count?: number;
  collections?: string[];
  errorCode?: string;
  sources?: Source[];
  totalMs?: number;
  thinkingDurationMs?: number;
  finishReason?: string;
  completionStatus?: 'complete' | 'cancelled' | 'interrupted' | 'pending' | 'error' | string;
  canContinue?: boolean;
  continuationCount?: number;
  maxContinuations?: number;
}

export interface StreamOptions {
  collections?: string[];
  mode?: 'auto' | 'knowledge' | 'model';
  /** Avoid analytics/usage writes for an in-memory temporary chat. */
  temporary?: boolean;
  thinking?: boolean;
  onThinking?: (token: string) => void;
  onThinkingDuration?: (durationMs: number) => void;
}

export interface ChatDocumentAttachment {
  id?: string;
  name: string;
  size: number;
  mimeType?: string;
  storageKey?: string;
  kind?: 'image' | 'document';
  truncated?: boolean;
  localOnly?: boolean;
}

/** Persisted routing intent used by edit/regenerate for a stable turn mode. */
export interface ChatTurnMetadata {
  mode: 'chat' | 'vision' | 'web' | 'deep_research' | 'agent' | 'rag';
  source: 'manual' | 'rule';
  reason: string;
  webSearch: boolean;
  depth: 1 | 2 | 3;
  announce: boolean;
  collections?: string[];
}

/** Research evidence retained with an assistant turn so exports stay auditable. */
export interface ChatResearchMetadata {
  search_query?: string;
  sub_questions?: string[];
  passes?: number;
  web_search?: boolean;
  web_provider?: string | null;
  degraded?: boolean;
  error_code?: string;
  error_detail?: string;
  failure_reason?: string;
  failure_message?: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  // Texto corto que se muestra al usuario cuando `content` incluye contexto interno.
  displayContent?: string;
  // Imagen adjunta (data URL base64) — para análisis con modelo de visión.
  image?: string;
  documentAttachments?: ChatDocumentAttachment[];
  inputMode?: 'text' | 'voice';
  // Solo en respuestas del asistente (RAG): de dónde salió la info.
  sources?: Source[];
  model?: string;
  project?: string | null;
  /** Routing intent associated with this user turn/assistant response. */
  turn?: ChatTurnMetadata;
  research?: ChatResearchMetadata;
  /** Internal UI marker so regeneration replaces, rather than repeats, it. */
  routerNotice?: boolean;
  /** Provider-supplied reasoning, kept separate from the final answer. */
  thinking?: string;
  thinkingDurationMs?: number;
  finishReason?: string;
  completionStatus?: 'complete' | 'cancelled' | 'interrupted' | 'pending' | 'error' | string;
  canContinue?: boolean;
  continuationCount?: number;
  maxContinuations?: number;
}

export const THINKING_MODE_KEY = 'tc-thinking-mode';
export const THINKING_MODE_DEFAULT = true;

export function thinkingModeEnabled(): boolean {
  try {
    const stored = localStorage.getItem(THINKING_MODE_KEY);
    return stored === null ? THINKING_MODE_DEFAULT : stored === '1';
  } catch {
    return THINKING_MODE_DEFAULT;
  }
}
