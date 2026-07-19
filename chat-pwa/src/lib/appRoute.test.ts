import { describe, expect, it } from 'vitest';
import { formatAppRoute, parseAppRoute } from './appRoute';

describe('app routes', () => {
  it('supports canonical deep links for every main view', () => {
    expect(parseAppRoute('#/chat/session%201')).toEqual({ page: 'chat', chatId: 'session 1' });
    expect(parseAppRoute('#/knowledge')).toEqual({ page: 'browser' });
    expect(parseAppRoute('#/agent')).toEqual({ page: 'agent' });
    expect(parseAppRoute('#/settings/memory')).toEqual({ page: 'settings', settingsSection: 'memory' });
    expect(parseAppRoute('#/settings/web-search')).toEqual({ page: 'settings', settingsSection: 'web-search' });
  });

  it('keeps old shortcuts compatible and normalizes generated URLs', () => {
    expect(parseAppRoute('#docs')).toEqual({ page: 'docs' });
    expect(parseAppRoute('#settings')).toEqual({ page: 'settings', settingsSection: 'general' });
    expect(formatAppRoute({ page: 'chat', chatId: 'a/b' })).toBe('#/chat/a%2Fb');
    expect(formatAppRoute({ page: 'settings', settingsSection: 'indexing' })).toBe('#/settings/indexing');
  });

  it('falls back safely for unknown or malformed routes', () => {
    expect(parseAppRoute('#/unknown')).toEqual({ page: 'chat' });
    expect(parseAppRoute('#/chat/%E0%A4%A')).toEqual({ page: 'chat', chatId: undefined });
  });
});
