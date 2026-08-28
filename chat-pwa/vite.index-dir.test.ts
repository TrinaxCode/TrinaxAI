import { afterEach, describe, expect, it, vi } from 'vitest';
import { basename, resolve } from 'node:path';

vi.mock('vite', () => ({ defineConfig: (config: unknown) => config }));
vi.mock('@vitejs/plugin-react', () => ({ default: () => ({ name: 'mock-react' }) }));
vi.mock('vite-plugin-pwa', () => ({ VitePWA: () => ({ name: 'mock-pwa' }) }));

import { indexDirectory } from './vite.config';

describe('Vite index directory fallback', () => {
  afterEach(() => vi.unstubAllEnvs());

  it('uses repository local_sources when unset or empty and preserves explicit values', () => {
    const expected = resolve(process.cwd(), basename(process.cwd()) === 'chat-pwa' ? '..' : '.', 'local_sources');

    vi.stubEnv('TRINAXAI_INDEX_DIR', undefined);
    expect(indexDirectory()).toBe(expected);

    vi.stubEnv('TRINAXAI_INDEX_DIR', '');
    expect(indexDirectory()).toBe(expected);

    vi.stubEnv('TRINAXAI_INDEX_DIR', '/tmp/explicit-index');
    expect(indexDirectory()).toBe('/tmp/explicit-index');
    expect(indexDirectory('/tmp/query-index')).toBe('/tmp/query-index');
  });
});
