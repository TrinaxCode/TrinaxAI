import { randomBytes } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';

export interface ProcessLockOptions {
  timeoutMs?: number;
  pollMs?: number;
  invalidOwnerStaleMs?: number;
  validOwnerStaleMs?: number;
}

interface LockOwner {
  pid?: number;
  owner_id?: string;
  created_at?: number;
}

function processAlive(pid: number): boolean {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return (error as NodeJS.ErrnoException).code === 'EPERM';
  }
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function quarantineAndRemove(lockDir: string): boolean {
  const quarantine = `${lockDir}.stale-${process.pid}-${randomBytes(6).toString('hex')}`;
  try {
    fs.renameSync(lockDir, quarantine);
  } catch {
    return false;
  }
  try { fs.rmSync(quarantine, { recursive: true, force: true }); } catch { /* best effort */ }
  return true;
}

function reclaimIfStale(
  lockDir: string,
  invalidOwnerStaleMs: number,
  validOwnerStaleMs: number,
): boolean {
  const ownerPath = path.join(lockDir, 'owner.json');
  let owner: LockOwner | null = null;
  try {
    owner = JSON.parse(fs.readFileSync(ownerPath, 'utf8')) as LockOwner;
  } catch { /* incomplete or foreign owner */ }

  const nowMs = Date.now();
  const createdMs = typeof owner?.created_at === 'number' ? owner.created_at * 1000 : 0;
  const ageMs = createdMs > 0
    ? nowMs - createdMs
    : (() => {
        try { return nowMs - fs.statSync(lockDir).mtimeMs; } catch { return 0; }
      })();
  const validPid = Number.isInteger(owner?.pid) && Number(owner?.pid) > 0;
  const stale = validPid
    ? (!processAlive(Number(owner?.pid)) || ageMs > validOwnerStaleMs)
    : ageMs > invalidOwnerStaleMs;
  return stale ? quarantineAndRemove(lockDir) : false;
}

/**
 * Portable atomic-directory process lock, compatible with
 * `trinaxai_core.exclusive_process_lock` on Python.
 */
export async function acquireInferenceProcessLock(
  lockDir: string,
  options: ProcessLockOptions = {},
): Promise<() => void> {
  const timeoutMs = Math.max(1, options.timeoutMs ?? 600_000);
  const pollMs = Math.max(10, options.pollMs ?? 100);
  const invalidOwnerStaleMs = Math.max(1_000, options.invalidOwnerStaleMs ?? 30_000);
  const validOwnerStaleMs = Math.max(60_000, options.validOwnerStaleMs ?? 24 * 60 * 60 * 1000);
  const deadline = Date.now() + timeoutMs;
  const ownerId = `${process.pid}-${randomBytes(16).toString('hex')}`;
  const ownerPath = path.join(lockDir, 'owner.json');
  fs.mkdirSync(path.dirname(lockDir), { recursive: true });

  while (true) {
    try {
      fs.mkdirSync(lockDir);
      fs.writeFileSync(
        ownerPath,
        JSON.stringify({ pid: process.pid, owner_id: ownerId, created_at: Date.now() / 1000 }),
        { encoding: 'utf8', mode: 0o600 },
      );
      break;
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error;
      reclaimIfStale(lockDir, invalidOwnerStaleMs, validOwnerStaleMs);
      if (Date.now() >= deadline) {
        throw new Error(`Timed out waiting for inference lock: ${lockDir}`);
      }
      await delay(pollMs);
    }
  }

  let released = false;
  return () => {
    if (released) return;
    released = true;
    try {
      const owner = JSON.parse(fs.readFileSync(ownerPath, 'utf8')) as LockOwner;
      if (owner.owner_id === ownerId) quarantineAndRemove(lockDir);
    } catch { /* never delete a lock whose ownership cannot be proven */ }
  };
}
