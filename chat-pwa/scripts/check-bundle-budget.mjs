import { readdir, stat } from 'node:fs/promises';
import path from 'node:path';
import process from 'node:process';

const root = path.resolve(process.cwd(), 'dist');
const kib = 1024;
const budgets = {
  maxJavaScript: Number(process.env.TRINAXAI_BUNDLE_MAX_JS_KIB || 350) * kib,
  totalJavaScript: Number(process.env.TRINAXAI_BUNDLE_TOTAL_JS_KIB || 1536) * kib,
  totalCss: Number(process.env.TRINAXAI_BUNDLE_TOTAL_CSS_KIB || 128) * kib,
  totalDist: Number(process.env.TRINAXAI_BUNDLE_TOTAL_DIST_KIB || 4096) * kib,
};

async function filesBelow(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) files.push(...await filesBelow(absolute));
    else if (entry.isFile()) files.push(absolute);
  }
  return files;
}

const files = await filesBelow(root);
const measured = await Promise.all(files.map(async (file) => ({
  file,
  bytes: (await stat(file)).size,
})));
const javascript = measured.filter(({ file }) => file.endsWith('.js'));
const css = measured.filter(({ file }) => file.endsWith('.css'));
const sum = (items) => items.reduce((total, item) => total + item.bytes, 0);
const largestJavaScript = javascript.reduce(
  (largest, item) => item.bytes > largest.bytes ? item : largest,
  { file: '', bytes: 0 },
);

const checks = [
  ['largest JavaScript chunk', largestJavaScript.bytes, budgets.maxJavaScript, largestJavaScript.file],
  ['all JavaScript', sum(javascript), budgets.totalJavaScript, ''],
  ['all CSS', sum(css), budgets.totalCss, ''],
  ['complete dist', sum(measured), budgets.totalDist, ''],
];
let failed = false;
for (const [label, bytes, budget, file] of checks) {
  const ok = bytes <= budget;
  failed ||= !ok;
  const suffix = file ? ` (${path.relative(root, file)})` : '';
  process.stdout.write(`${ok ? 'PASS' : 'FAIL'} ${label}: ${(bytes / kib).toFixed(1)} KiB / ${(budget / kib).toFixed(0)} KiB${suffix}\n`);
}
if (failed) process.exitCode = 1;
