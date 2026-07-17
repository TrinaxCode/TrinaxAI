import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';

import { acquireInferenceProcessLock } from './inference-lock';

const roots: string[] = [];

afterEach(() => {
  for (const root of roots.splice(0)) fs.rmSync(root, { recursive: true, force: true });
});

describe('cross-process inference lock', () => {
  it('serializes owners and releases idempotently', async () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'trinaxai-inference-'));
    roots.push(root);
    const lockDir = path.join(root, '.inference.lock');
    const releaseFirst = await acquireInferenceProcessLock(lockDir, { timeoutMs: 100 });

    await expect(acquireInferenceProcessLock(lockDir, { timeoutMs: 30, pollMs: 10 }))
      .rejects.toThrow(/Timed out/);

    releaseFirst();
    releaseFirst();
    const releaseSecond = await acquireInferenceProcessLock(lockDir, { timeoutMs: 100 });
    expect(fs.existsSync(lockDir)).toBe(true);
    releaseSecond();
    expect(fs.existsSync(lockDir)).toBe(false);
  });

  it('reclaims a dead process owner', async () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'trinaxai-inference-'));
    roots.push(root);
    const lockDir = path.join(root, '.inference.lock');
    fs.mkdirSync(lockDir);
    fs.writeFileSync(
      path.join(lockDir, 'owner.json'),
      JSON.stringify({ pid: 999_999_999, created_at: Date.now() / 1000 }),
    );

    const release = await acquireInferenceProcessLock(lockDir, { timeoutMs: 100 });
    release();
    expect(fs.existsSync(lockDir)).toBe(false);
  });
});
