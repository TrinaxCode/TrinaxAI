import axe, { type ElementContext, type Result } from 'axe-core';
import { expect } from 'vitest';

function describeViolations(violations: Result[]): string {
  return violations.map((violation) => {
    const targets = violation.nodes.flatMap((node) => node.target).join(', ');
    return `${violation.id}: ${violation.help} (${targets})`;
  }).join('\n');
}

/** Run deterministic WCAG checks supported by jsdom.
 *
 * axe documents that color contrast requires a real layout engine; page-level
 * landmarks are also outside a component fixture. Browser E2E retains those
 * manual/real-engine checks.
 */
export async function expectNoA11yViolations(context: ElementContext): Promise<void> {
  const results = await axe.run(context, {
    rules: {
      'color-contrast': { enabled: false },
      region: { enabled: false },
    },
  });
  expect(results.violations, describeViolations(results.violations)).toEqual([]);
}
