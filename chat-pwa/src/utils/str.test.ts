import { describe, expect, it } from 'vitest';

import { escapeRegExp } from './str';

describe('escapeRegExp', () => {
  it('escapes regex metacharacters', () => {
    expect(escapeRegExp('a+b.(test)?')).toBe('a\\+b\\.\\(test\\)\\?');
  });
});
