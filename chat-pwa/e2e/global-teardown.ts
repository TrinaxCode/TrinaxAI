import fs from 'node:fs';
import path from 'node:path';

export default function cleanupE2eBuilds() {
  const root = path.resolve(process.cwd());
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory() || !/^\.e2e-dist-\d+$/.test(entry.name)) continue;
    fs.rmSync(path.join(root, entry.name), { recursive: true, force: true });
  }
}
