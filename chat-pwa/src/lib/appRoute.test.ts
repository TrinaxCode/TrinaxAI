import { describe, expect, it } from 'vitest';
import { formatAppRoute, parseAppRoute } from './appRoute';

describe('app routes', () => {
  it('supports canonical deep links for every main view', () => {
    expect(parseAppRoute('#/chat/session%201')).toEqual({ page: 'chat', chatId: 'session 1' });
    expect(parseAppRoute('#/knowledge')).toEqual({ page: 'browser' });
    expect(parseAppRoute('#/sources')).toEqual({ page: 'browser' });
    expect(parseAppRoute('#/collections')).toEqual({ page: 'browser' });
    expect(parseAppRoute('#/agent')).toEqual({ page: 'agent' });
    expect(parseAppRoute('#/settings/memory')).toEqual({ page: 'settings', settingsSection: 'memory' });
    expect(parseAppRoute('#/settings/web-search')).toEqual({ page: 'settings', settingsSection: 'web-search' });
    expect(parseAppRoute('#/settings/advanced')).toEqual({ page: 'settings', settingsSection: 'advanced' });
    expect(parseAppRoute('#/docs/security')).toEqual({ page: 'docs', docsSection: 'security' });
  });

  it('keeps old shortcuts compatible and normalizes generated URLs', () => {
    expect(parseAppRoute('#docs')).toEqual({ page: 'docs' });
    expect(parseAppRoute('#/docs')).toEqual({ page: 'docs' });
    expect(parseAppRoute('#/docs/not-a-section')).toEqual({ page: 'docs' });
    expect(parseAppRoute('#settings')).toEqual({ page: 'settings', settingsSection: 'general' });
    expect(formatAppRoute({ page: 'chat', chatId: 'a/b' })).toBe('#/chat/a%2Fb');
    expect(formatAppRoute({ page: 'settings', settingsSection: 'indexing' })).toBe('#/settings/indexing');
    expect(formatAppRoute({ page: 'settings', settingsSection: 'advanced' })).toBe('#/settings/advanced');
    expect(formatAppRoute({ page: 'docs', docsSection: 'indexing' })).toBe('#/docs/indexing');
    expect(formatAppRoute({ page: 'docs' })).toBe('#/docs');
  });

  it('falls back safely for unknown or malformed routes', () => {
    expect(parseAppRoute('#/unknown')).toEqual({ page: 'chat' });
    expect(parseAppRoute('#/chat/%E0%A4%A')).toEqual({ page: 'chat', chatId: undefined });
  });
});
