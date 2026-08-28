import { APP_CONFIG } from './config';
import { systemRequestHeaders } from './authHeaders';
import { ApiError, apiErrorFromPayload } from './api_errors';
import { apiJson, RAG_BASE } from './api_http';
import { readStreamLines } from './api_streams';
import type { ErrorCategory } from './api_errors';
import type { ChatMessage } from './api_types';

// ── TrinaxAI Agent (file/shell tool-use over a workspace) ──

/** Default workspace root for the agent (user-overridable in Settings). */
function isBroadAgentWorkspace(value: string): boolean {
  const normalized = value.replace(/\\/g, '/').replace(/\/+$/, '');
  return normalized === '~' || normalized === '~/Documents' || normalized.endsWith('/Documents');
}

export function agentWorkspaceRoot(): string {
  try {
    const v = localStorage.getItem('tc-agent-workspace')?.trim();
    if (v && !isBroadAgentWorkspace(v)) return v;
  } catch { /* localStorage unavailable */ }
  const configured = APP_CONFIG.defaultIndexDir.trim();
  return isBroadAgentWorkspace(configured) ? '' : configured;
}

/** One event emitted by the agent SSE stream. */
export type AgentEvent =
  | { type: 'start'; session_id: string; workspace: string; model: string }
  | { type: 'status'; state: 'running'; elapsed_seconds: number; idle_seconds: number; current_tool: string | null; steps: number; last_activity: number }
  | { type: 'tool_start'; tool: string; dangerous: boolean; args: Record<string, string> }
  | { type: 'tool_result'; tool: string; result: string }
  | { type: 'approval_request'; approval_id: string; tool: string; args: Record<string, string> }
  | { type: 'approval_timeout'; approval_id: string }
  | { type: 'token'; content: string }
  | { type: 'done'; answer: string; finish_reason?: string; completion_status?: string }
  | { type: 'error'; error: string; category?: ErrorCategory; code?: string; recoverable?: boolean; finish_reason?: string; completion_status?: string };

function parseAgentSseLine(line: string): AgentEvent | { done: true } | null {
  const trimmed = line.trim();
  if (!trimmed || !trimmed.startsWith('data: ')) return null;
  const data = trimmed.slice(6);
  if (data === '[DONE]') return { done: true };
  try {
    const parsed = JSON.parse(data);
    return parsed && typeof parsed.type === 'string' ? (parsed as AgentEvent) : null;
  } catch {
    return null;
  }
}

/**
 * Run the agent for one turn, streaming events. Dangerous actions arrive as
 * `approval_request` events; call {@link approveAgentAction} with the id to let
 * them proceed (or reject). The returned promise resolves when the stream ends.
 */
export async function runAgent(
  messages: ChatMessage[],
  onEvent: (event: AgentEvent) => void,
  opts: { workspace?: string; model?: string; maxSteps?: number; yolo?: boolean; webSearch?: boolean; knowledgeSearch?: boolean; deepResearch?: boolean; signal?: AbortSignal } = {},
): Promise<void> {
  const response = await fetch(`${RAG_BASE}/v1/agent`, {
    method: 'POST',
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
      workspace: opts.workspace ?? agentWorkspaceRoot(),
      model: opts.model,
      max_steps: opts.maxSteps ?? 25,
      yolo: opts.yolo ?? false,
      web_search: opts.webSearch ?? false,
      knowledge_search: opts.knowledgeSearch ?? false,
      deep_research: opts.deepResearch ?? false,
    }),
    signal: opts.signal,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw apiErrorFromPayload(response.status, detail);
  }
  let terminal = false;
  await readStreamLines(response, opts.signal, (line) => {
    const event = parseAgentSseLine(line);
    if (!event) return;
    if ('done' in event) return;
    if (event.type === 'done') terminal = true;
    if (event.type === 'error') {
      terminal = true;
      throw apiErrorFromPayload(503, event);
    }
    onEvent(event);
  });
  if (!terminal && !opts.signal?.aborted) throw new ApiError('', 503, 'tool_timeout');
}

/** Approve or reject a pending dangerous agent action by its approval id. */
export async function approveAgentAction(sessionId: string, approvalId: string, approved: boolean): Promise<void> {
  await apiJson<{ ok: boolean }>(`${RAG_BASE}/v1/agent/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, approval_id: approvalId, approved }),
  });
}

export async function cancelAgentRun(sessionId: string): Promise<void> {
  await apiJson<{ ok: boolean }>(`${RAG_BASE}/v1/agent/cancel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export interface DirectoryEntry {
  name: string;
  path: string;
  readable: boolean;
}

export interface DirectoryListing {
  path: string;
  parent: string | null;
  home: string;
  directories: DirectoryEntry[];
}

/** List sub-directories of a host path so the user can pick the agent workspace. */
export async function browseDirectories(path?: string, signal?: AbortSignal): Promise<DirectoryListing> {
  const query = path ? `?path=${encodeURIComponent(path)}` : '';
  return apiJson<DirectoryListing>(`${RAG_BASE}/v1/agent/browse${query}`, {
    method: 'GET',
    headers: systemRequestHeaders(),
    signal,
  });
}
