/* eslint-disable no-control-regex, no-useless-escape -- exports sanitize control and Markdown syntax characters. */
import type { ChatMessage, Source } from './api';

export interface ChatExportOptions {
  title?: string;
  roleLabels?: Partial<Record<ChatMessage['role'], string>>;
  includeThinking?: boolean;
  includeMetadata?: boolean;
}

export interface ChatExportResult {
  markdown: string;
  html: string;
}

type RecordValue = Record<string, unknown>;
type ExportSource = Source | RecordValue | string;

const DEFAULT_TITLE = 'TrinaxAI Conversation';
const ROLES: Record<ChatMessage['role'], string> = { user: 'User', assistant: 'Assistant', system: 'System' };
const CONTROL_CHARS = /[\u0000-\u001f\u007f]/;
const INVALID_FILENAME_CHARS = /[<>:"|?*\\/]/;
const RESERVED_FILENAME = /^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$/i;
const SENSITIVE_KEY = /(?:token|secret|password|credential|authorization|api[_-]?key)/i;

export function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character] || character);
}

function record(value: unknown): RecordValue | undefined {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as RecordValue : undefined;
}

function value(value: unknown): string {
  if (Array.isArray(value)) return value.map((item) => valueOf(item)).join(', ');
  return valueOf(value);
}

function valueOf(item: unknown): string {
  if (item === null || item === undefined) return '';
  if (typeof item === 'object') {
    try { return JSON.stringify(item); } catch { return '[unavailable]'; }
  }
  return String(item);
}

function present(item: unknown): boolean {
  return item !== undefined && item !== null && item !== '';
}

function publicMetadataValue(item: unknown): unknown {
  if (Array.isArray(item)) {
    const values = item.map(publicMetadataValue).filter((value) => value !== undefined);
    return values.length ? values : undefined;
  }
  if (item && typeof item === 'object') {
    const output: RecordValue = {};
    for (const [key, nested] of Object.entries(item as RecordValue)) {
      if (SENSITIVE_KEY.test(key) || key === 'sources' || key === 'citations') continue;
      const cleaned = publicMetadataValue(nested);
      if (cleaned !== undefined && present(cleaned)) output[key] = cleaned;
    }
    return Object.keys(output).length ? output : undefined;
  }
  return item;
}

function md(valueToEscape: unknown): string {
  return value(valueToEscape).replace(/[\\`*_{}\[\]()#+!|<>~-]/g, '\\$&');
}

function safeUrl(candidate: unknown): string | undefined {
  if (typeof candidate !== 'string' || CONTROL_CHARS.test(candidate)) return undefined;
  try {
    const url = new URL(candidate.trim());
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : undefined;
  } catch {
    return undefined;
  }
}

function sourceRecord(source: ExportSource): RecordValue {
  return typeof source === 'string' ? { title: source } : source as RecordValue;
}

function sourceTitle(source: ExportSource): string {
  const item = sourceRecord(source);
  return String(item.title || item.name || item.file || item.url || 'Source');
}

function sourceDetails(source: ExportSource): Array<[string, unknown]> {
  const item = sourceRecord(source);
  const details: Array<[string, unknown]> = [
    ['File', item.file], ['URL', safeUrl(item.url)], ['Search URL', safeUrl(item.search_url)],
    ['Canonical URL', safeUrl(item.canonical_url)], ['Page', item.page],
    ['Collection', item.collection || item.collection_id],
    ['Project', item.project], ['Kind', item.kind], ['Provider', item.provider],
    ['Authority', item.authority], ['Scope', item.content_scope], ['Author', item.author],
    ['Published', item.published_at], ['Score', item.score], ['Snippet', item.snippet],
    ['Fetch error', item.fetch_error],
  ];
  return details.filter(([, itemValue]) => present(itemValue));
}

function messageRecord(message: ChatMessage): RecordValue {
  return message as unknown as RecordValue;
}

function researchMetadata(message: ChatMessage): unknown {
  const item = messageRecord(message);
  for (const key of ['researchMeta', 'research_metadata', 'deepResearch', 'deep_research', 'research']) {
    if (item[key] !== undefined) return item[key];
  }
  const meta = record(item.meta) || record(item.metadata);
  return meta?.researchMeta ?? meta?.research_metadata ?? meta?.deepResearch ?? meta?.deep_research ?? meta?.research;
}

function sources(message: ChatMessage): ExportSource[] {
  if (message.sources?.length) return message.sources;
  const research = record(researchMetadata(message));
  return Array.isArray(research?.sources) ? research.sources as ExportSource[] : [];
}

function citations(message: ChatMessage): ExportSource[] {
  const item = messageRecord(message);
  return Array.isArray(item.citations) ? item.citations as ExportSource[] : [];
}

function metadata(message: ChatMessage): Array<[string, unknown]> {
  const allEntries: Array<[string, unknown]> = [
    ['Model', message.model], ['Project', message.project], ['Input mode', message.inputMode],
    ['Finish reason', message.finishReason], ['Completion status', message.completionStatus],
    ['Can continue', message.canContinue], ['Continuation count', message.continuationCount],
    ['Maximum continuations', message.maxContinuations], ['Thinking duration (ms)', message.thinkingDurationMs],
    ['Mode', message.turn?.mode], ['Routing reason', message.turn?.reason],
    ['Web search', message.turn?.webSearch], ['Research depth', message.turn?.depth],
    ['Collections', message.turn?.collections],
  ];
  const entries = allEntries.filter(([, item]) => present(item));
  const research = researchMetadata(message);
  if (research !== undefined) {
    for (const [key, item] of Object.entries(record(research) || { enabled: research })) {
      if (SENSITIVE_KEY.test(key) || key === 'sources' || key === 'citations') continue;
      const cleaned = publicMetadataValue(item);
      if (cleaned !== undefined && present(cleaned)) entries.push([key, cleaned]);
    }
  }
  const item = messageRecord(message);
  if (Array.isArray(item.citations)) entries.push(['Citation count', item.citations.length]);
  return entries;
}

function attachments(message: ChatMessage): Array<[string, string]> {
  return (message.documentAttachments || []).map((attachment) => {
    const details = [attachment.kind, attachment.mimeType, Number.isFinite(attachment.size) ? `${attachment.size} bytes` : '', attachment.truncated ? 'truncated' : '', attachment.localOnly ? 'local only' : '']
      .filter(Boolean).join(' · ');
    return [attachment.name || 'attachment', details];
  });
}

function markdownSources(title: string, items: ExportSource[]): string[] {
  if (!items.length) return [];
  return [`### ${md(title)}`, '', ...items.map((source, index) => {
    const url = safeUrl(sourceRecord(source).url);
    const label = md(sourceTitle(source));
    const link = url ? `[${label}](<${url.replace(/[\\<>]/g, '\\$&')}>)` : label;
    const details = sourceDetails(source).map(([key, item]) => `${md(key)}: ${md(item)}`).join('; ');
    return `${index + 1}. ${link}${details ? ` — ${details}` : ''}`;
  }), ''];
}

function htmlSources(title: string, items: ExportSource[]): string {
  if (!items.length) return '';
  return `<h3>${escapeHtml(title)}</h3><ol>${items.map((source) => {
    const item = sourceRecord(source);
    const url = safeUrl(item.url);
    const label = escapeHtml(sourceTitle(source));
    const titleHtml = url ? `<a href="${escapeHtml(url)}" rel="noopener noreferrer">${label}</a>` : label;
    const details = sourceDetails(source).map(([key, detail]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value(detail))}</dd>`).join('');
    return `<li><strong>${titleHtml}</strong>${details ? `<dl>${details}</dl>` : ''}</li>`;
  }).join('')}</ol>`;
}

function markdownMessage(message: ChatMessage, options: ChatExportOptions): string[] {
  const role = options.roleLabels?.[message.role] || ROLES[message.role] || message.role;
  const lines = [`## ${md(role)}`, '', message.displayContent ?? (message.content || (message.image ? '[image attachment]' : ''))];
  if (options.includeThinking !== false && message.thinking) {
    lines.push('', '### Thinking', '', ...message.thinking.split(/\r?\n/).map((line) => `> ${line}`));
  }
  if (options.includeMetadata !== false) {
    const entries = metadata(message);
    if (message.turn?.mode === 'deep_research' || researchMetadata(message) !== undefined) lines.push('', '### Deep Research');
    if (entries.length) lines.push('', '### Metadata', '', ...entries.map(([key, item]) => `- **${md(key)}:** ${md(item)}`));
  }
  const files = attachments(message);
  if (files.length) lines.push('', '### Attachments', '', ...files.map(([name, detail]) => `- ${md(name)}${detail ? ` — ${md(detail)}` : ''}`));
  lines.push(...markdownSources('Sources', sources(message)), ...markdownSources('Citations', citations(message)), '');
  return lines;
}

function htmlMessage(message: ChatMessage, options: ChatExportOptions): string {
  const role = options.roleLabels?.[message.role] || ROLES[message.role] || message.role;
  const content = message.displayContent ?? (message.content || (message.image ? '[image attachment]' : ''));
  const parts = [`<section><h2>${escapeHtml(role)}</h2><pre>${escapeHtml(content)}</pre>`];
  if (options.includeThinking !== false && message.thinking) parts.push(`<h3>Thinking</h3><pre class="thinking">${escapeHtml(message.thinking)}</pre>`);
  if (options.includeMetadata !== false) {
    const entries = metadata(message);
    if (entries.length) parts.push(`<h3>${message.turn?.mode === 'deep_research' || researchMetadata(message) !== undefined ? 'Deep Research / Metadata' : 'Metadata'}</h3><dl>${entries.map(([key, item]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value(item))}</dd>`).join('')}</dl>`);
  }
  const files = attachments(message);
  if (files.length) parts.push(`<h3>Attachments</h3><ul>${files.map(([name, detail]) => `<li>${escapeHtml(name)}${detail ? ` <small>(${escapeHtml(detail)})</small>` : ''}</li>`).join('')}</ul>`);
  parts.push(htmlSources('Sources', sources(message)), htmlSources('Citations', citations(message)), '</section>');
  return parts.join('');
}

export function serializeChatMarkdown(messages: readonly ChatMessage[], options: ChatExportOptions = {}): string {
  return [`# ${md(options.title || DEFAULT_TITLE)}`, '', ...messages.flatMap((message) => markdownMessage(message, options))].join('\n');
}

export function serializeChatHtml(messages: readonly ChatMessage[], options: ChatExportOptions = {}): string {
  const title = options.title || DEFAULT_TITLE;
  const body = messages.map((message) => htmlMessage(message, options)).join('');
  return `<!doctype html><html><head><meta charset="utf-8"><title>${escapeHtml(title)}</title><style>body{font-family:system-ui,sans-serif;margin:32px;color:#111;line-height:1.5}section{break-inside:avoid;margin-bottom:24px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px ui-monospace,monospace;background:#f7f7f7;padding:12px}h2{color:#006bbd}dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 12px;font-size:12px}dt{font-weight:600}dd{margin:0;overflow-wrap:anywhere}.thinking{background:#fff8e1}a{color:#006bbd}</style></head><body><h1>${escapeHtml(title)}</h1>${body}</body></html>`;
}

export function serializeChatExport(messages: readonly ChatMessage[], options: ChatExportOptions = {}): ChatExportResult {
  return { markdown: serializeChatMarkdown(messages, options), html: serializeChatHtml(messages, options) };
}

export function isValidExportFilename(input: unknown): input is string {
  if (typeof input !== 'string') return false;
  const name = input.trim();
  return Boolean(name && name.length <= 255 && name !== '.' && name !== '..' && !CONTROL_CHARS.test(name) && !INVALID_FILENAME_CHARS.test(name) && !/[. ]$/.test(name) && !RESERVED_FILENAME.test(name));
}

export function validateExportFilename(input: string): string {
  if (!isValidExportFilename(input)) throw new TypeError('Invalid export filename.');
  return input.trim();
}

export function sanitizeExportFilename(input: string, fallback = 'trinaxai-chat'): string {
  const safeFallback = isValidExportFilename(fallback) ? fallback.trim() : 'trinaxai-chat';
  const candidate = String(input || '').replace(/[\u0000-\u001f\u007f]/g, '-').replace(/[\\/<>:"|?*]/g, '-').replace(/\s+/g, ' ').trim().replace(/[. ]+$/g, '').slice(0, 255).replace(/[. ]+$/g, '');
  return isValidExportFilename(candidate) ? candidate : safeFallback;
}
