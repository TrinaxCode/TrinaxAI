import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const vitest = fileURLToPath(new URL('../node_modules/vitest/vitest.mjs', import.meta.url));
const environment = { ...process.env };
if (process.allowedNodeEnvironmentFlags.has('--no-experimental-webstorage')) {
  const existingNodeOptions = environment.NODE_OPTIONS?.trim();
  if (!existingNodeOptions?.split(/\s+/u).includes('--no-experimental-webstorage')) {
    environment.NODE_OPTIONS = [existingNodeOptions, '--no-experimental-webstorage']
      .filter(Boolean)
      .join(' ');
  }
}
const result = spawnSync(process.execPath, [vitest, ...process.argv.slice(2)], {
  env: environment,
  stdio: 'inherit',
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}
process.exit(result.status ?? 1);
