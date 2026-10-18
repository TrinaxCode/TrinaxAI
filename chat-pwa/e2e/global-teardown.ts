import fs from 'node:fs';
import path from 'node:path';

export default function cleanupE2eBuilds() {
  const root = path.resolve(process.cwd());
  const port = process.env.TRINAXAI_E2E_PORT || '4174';
  if (!/^\d+$/.test(port)) throw new Error('Invalid E2E port');
  fs.rmSync(path.join(root, `.e2e-dist-${port}`), { recursive: true, force: true });
}
