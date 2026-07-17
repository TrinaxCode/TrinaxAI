import { describe, expect, it } from 'vitest';
import { pickActivityMessage } from './activityMessages';

const t = (key: string) => key;

describe('activity messages', () => {
  it('selects image-specific messages deterministically for testing', () => {
    expect(pickActivityMessage('image', t, '', () => 0)).toBe('activityImageAnalyze');
    expect(pickActivityMessage('image', t, '', () => 0.99)).toBe('activityImageCloser');
  });

  it('does not immediately repeat the previous activity message', () => {
    expect(pickActivityMessage('web', t, 'webSearching', () => 0)).toBe('activityWebSources');
  });
});
