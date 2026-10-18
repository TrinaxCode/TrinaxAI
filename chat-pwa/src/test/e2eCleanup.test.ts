import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { expect, it, vi } from 'vitest';
import cleanupE2eBuilds from '../../e2e/global-teardown';

it('removes its own build and preserves another execution', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'trinaxai-e2e-cleanup-'));
  const own = path.join(root, '.e2e-dist-4174');
  const other = path.join(root, '.e2e-dist-4175');
  fs.mkdirSync(own);
  fs.mkdirSync(other);
  vi.spyOn(process, 'cwd').mockReturnValue(root);
  vi.stubEnv('TRINAXAI_E2E_PORT', '4174');
  try {
    cleanupE2eBuilds();
    expect(fs.existsSync(own)).toBe(false);
    expect(fs.existsSync(other)).toBe(true);
    vi.stubEnv('TRINAXAI_E2E_PORT', '../4175');
    expect(cleanupE2eBuilds).toThrow('Invalid E2E port');
    expect(fs.existsSync(other)).toBe(true);
  } finally {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    fs.rmSync(root, { recursive: true, force: true });
  }
});
