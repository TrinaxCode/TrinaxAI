import { systemRequestHeaders } from './authHeaders';
import { apiJson, RAG_BASE } from './api_http';
import type { ChatEngine, ChatMessage } from './api_types';

// ── Usage Stats ──
export interface UsageStats {
  messages_total: number;
  messages_by_engine: Record<string, number>;
  tokens_estimated: number;
  top_collections: Array<{ id: string; count: number }>;
  top_models: Array<{ model: string; count: number }>;
  index_runs: number;
  first_seen: number;
  last_seen: number;
}
export async function getUsageStats(signal?: AbortSignal): Promise<UsageStats> {
  return apiJson(`${RAG_BASE}/v1/stats`, { signal });
}
function estimateUsageTokens(messages: ChatMessage[], answer: string): number {
  const chars = messages.reduce((sum, msg) => sum + (msg.content?.length ?? 0), 0) + answer.length;
  return Math.max(1, Math.round(chars / 4));
}

export function recordUsage(engine: ChatEngine | 'ollama-vision', model: string, messages: ChatMessage[], answer: string, collections?: string[]): void {
  if (!answer.trim()) return;
  void fetch(`${RAG_BASE}/v1/usage`, {
    method: 'POST',
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      engine,
      model,
      collections: collections || [],
      est_tokens: estimateUsageTokens(messages, answer),
    }),
    keepalive: true,
  }).catch(() => undefined);
}

export async function resetSharedAppState(): Promise<void> {
  await apiJson(`${RAG_BASE}/app-state`, {
    method: 'DELETE',
    headers: { 'X-TrinaxAI-Confirm': 'reset-app-state' },
  });
}
