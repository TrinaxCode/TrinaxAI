import { describe, expect, it } from 'vitest';

import type { ChatMessage } from './api';
import { isValidExportFilename, sanitizeExportFilename, serializeChatExport, serializeChatHtml, serializeChatMarkdown, validateExportFilename } from './chatExport';

describe('pure chat export serializer', () => {
  it('preserves roles, attachments, sources, citations, research and thinking', () => {
    const nestedSensitiveKey = ['api', 'key'].join('_');
    const assistant = {
      role: 'assistant', content: '<script>alert(1)</script> Answer [1].', thinking: 'Checked evidence.', thinkingDurationMs: 42,
      turn: { mode: 'deep_research', source: 'rule', reason: 'multiple sources', webSearch: true, depth: 3, announce: true, collections: ['docs'] },
      documentAttachments: [{ name: 'report.pdf', size: 2048, mimeType: 'application/pdf', kind: 'document' as const }],
      sources: [{ file: 'report.pdf', title: 'Report', url: 'https://example.test/report', page: 4, project: 'local', snippet: 'Evidence', score: 0.9 }],
      citations: [{ title: 'Unsafe citation', url: 'javascript:alert(1)' }], researchMeta: {
        passes: 3,
        web_provider: 'duckduckgo',
        details: { public_note: 'safe', [nestedSensitiveKey]: 'nested-secret' },
        checks: [{ note: 'kept', token: 'nested-token' }],
      },
    } as ChatMessage & { citations: unknown[]; researchMeta: Record<string, unknown> };
    const result = serializeChatExport([{ role: 'user', content: 'Question' }, assistant]);

    expect(result.markdown).toContain('## User');
    expect(result.markdown).toContain('## Assistant');
    expect(result.markdown).toContain('<script>alert(1)</script>');
    expect(result.markdown).toContain('report.pdf');
    expect(result.markdown).toContain('### Deep Research');
    expect(result.markdown).toContain('https://example.test/report');
    expect(result.html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
    expect(result.html).not.toContain('<script>alert(1)</script>');
    expect(result.html).toContain('href="https://example.test/report"');
    expect(result.html).not.toContain('href="javascript:alert(1)"');
    expect(result.html).toContain('Thinking');
    expect(result.markdown).toContain('public\\_note');
    expect(result.markdown).not.toContain('nested-secret');
    expect(result.markdown).not.toContain('nested-token');
    expect(result.html).not.toContain('nested-secret');
    expect(result.html).not.toContain('nested-token');

    const legacy = serializeChatMarkdown([{
      role: 'assistant',
      content: 'Legacy answer',
      meta: { research: { sources: [{ title: 'Legacy source', url: 'https://legacy.example' }] } },
    } as ChatMessage & { meta: Record<string, unknown> }]);
    expect(legacy).toContain('Legacy source');
  });

  it('does not mutate messages and can omit thinking', () => {
    const messages: ChatMessage[] = [{ role: 'system', content: 'Rules', thinking: 'internal' }];
    const before = JSON.stringify(messages);
    const result = serializeChatExport(messages, { title: 'Export', includeThinking: false });
    expect(JSON.stringify(messages)).toBe(before);
    expect(result.markdown).toContain('# Export');
    expect(result.html).toContain('<title>Export</title>');
    expect(result.markdown).not.toContain('internal');
    expect(result.html).not.toContain('internal');
  });

  it('validates and sanitizes filenames', () => {
    expect(isValidExportFilename('chat-2026.md')).toBe(true);
    expect(isValidExportFilename('../chat.md')).toBe(false);
    expect(isValidExportFilename('CON')).toBe(false);
    expect(isValidExportFilename('bad\nname.md')).toBe(false);
    expect(() => validateExportFilename('bad/name.md')).toThrow(TypeError);
    expect(validateExportFilename(' chat.md ')).toBe('chat.md');
    expect(sanitizeExportFilename('../bad:name?.md')).toBe('..-bad-name-.md');
    expect(sanitizeExportFilename('..')).toBe('trinaxai-chat');
  });
});
