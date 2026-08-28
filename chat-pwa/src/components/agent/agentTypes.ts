import type { DEFAULT_MODEL_SETTINGS } from '../../lib/api';
import type { AgentHandoff } from '../chat/modeRouter';

export interface AgentInterfaceProps {
  onBack: () => void;
  initialRequest?: AgentHandoff | null;
  onRequestConsumed?: (id: string) => void;
}

/** A tool invocation and its lifecycle, shown as a step card. */
export interface AgentStep {
  id: string;
  tool: string;
  dangerous: boolean;
  args: Record<string, string>;
  status: 'running' | 'awaiting' | 'done' | 'denied';
  result?: string;
  approvalId?: string;
  runSessionId?: string;
}

export interface AttachedAgentDocument {
  name: string;
  content: string;
  truncated: boolean;
}

export type AgentModelMode = 'auto' | 'chat' | 'deep' | 'fast';

export const AGENT_DOC_MAX_FILES = 20;
export const AGENT_DOC_MAX_CHARS = 32_000;
export const AGENT_DOC_TOTAL_MAX_CHARS = 48_000;
export const AGENT_MODEL_KEYS: Record<Exclude<AgentModelMode, 'auto'>, keyof typeof DEFAULT_MODEL_SETTINGS> = {
  chat: 'tc-models-chat',
  deep: 'tc-models-deep',
  fast: 'tc-models-fast',
};
export const HISTORY_FOCUSABLE = 'button, input, select, textarea, [href], [tabindex]:not([tabindex="-1"])';

/** A turn in the agent conversation. */
export interface AgentTurn {
  role: 'user' | 'assistant';
  content: string;
  /** Full hidden request context, including extracted attachments, for follow-ups. */
  contextContent?: string;
  steps?: AgentStep[];
  image?: string;
  documents?: Array<{ name: string; truncated: boolean; preview?: string }>;
  model?: string;
  completionStatus?: string;
  /** Observable agent activity history, kept separate from the final answer. */
  thinking?: string;
}
