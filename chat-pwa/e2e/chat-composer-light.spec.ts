import { expect, test, type Page } from '@playwright/test';

/**
 * The primary composer control (call mode / send / stop) sits on a near-white
 * surface in light mode. Its white icon is only readable while the control
 * keeps its own brand fill, so the computed style is asserted directly instead
 * of trusting the class list.
 */
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    localStorage.setItem('tc-theme', 'light');
    localStorage.setItem('tc-lang', 'es');
  });
  await page.route('**/api/network', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ online: true, urls: [], needsRefresh: false, capabilities: { manageSystem: false } }),
  }));
  await page.route('**/api/rag/app-state', (route) => route.fulfill({ status: 304 }));
  await page.route('**/api/ollama/api/tags', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ models: [] }),
  }));
  await page.route('**/api/rag/**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ ok: true, memories: [], collections: [], count: 0 }),
  }));
});

test('keeps the call/send control visible on the light composer', async ({ page }) => {
  await page.goto('/#/');
  const primaryAction = page.locator('.composer-action-primary').first();
  await expect(primaryAction).toBeVisible();

  const palette = await primaryAction.evaluate((element) => {
    const style = getComputedStyle(element);
    return { background: style.backgroundColor, color: style.color };
  });

  expect(palette.background).toBe('rgb(0, 107, 189)');
  expect(palette.color).toBe('rgb(255, 255, 255)');

  await expect(primaryAction).toHaveAccessibleName(/llamada|call/i);
});

/**
 * Entering call mode must not swap the tree in a single frame: the conversation
 * stays mounted for the length of its exit animation before the voice surface
 * enters, and the call surface does the same on the way back.
 */
async function watchSwap(page: Page): Promise<void> {
  await page.evaluate(() => {
    const state = { chatRemovedAt: 0, callRemovedAt: 0 };
    (window as unknown as { __callSwap: typeof state }).__callSwap = state;
    const record = () => {
      if (!state.chatRemovedAt && !document.querySelector('[data-chat-flow]')) state.chatRemovedAt = performance.now();
      if (!state.callRemovedAt && !document.querySelector('[data-voice-call]')) state.callRemovedAt = performance.now();
    };
    new MutationObserver(record).observe(document.body, { childList: true, subtree: true });
  });
}

function readSwap(page: Page) {
  return page.evaluate(() => (window as unknown as {
    __callSwap: { chatRemovedAt: number; callRemovedAt: number };
  }).__callSwap);
}

test('animates the swap between chat and call mode in both directions', async ({ page }) => {
  await page.goto('/#/');
  const primaryAction = page.locator('.composer-action-primary').first();
  await expect(primaryAction).toBeVisible();

  const enter = page.getByRole('button', { name: /salir del modo llamada|exit voice mode|end call/i });
  await watchSwap(page);

  const enterClickedAt = await primaryAction.evaluate((element) => {
    element.click();
    return performance.now();
  });
  await expect(enter).toBeVisible();
  await expect(page.locator('.composer-action-primary')).toHaveCount(0);

  // The call surface is a motion element, not a plain swap.
  const callStyle = await page.locator('[data-voice-call]').evaluate((element) => element.getAttribute('style') || '');
  expect(callStyle).toMatch(/opacity|transform/);

  const exitClickedAt = await enter.evaluate((element) => {
    element.click();
    return performance.now();
  });
  await expect(page.locator('.composer-action-primary').first()).toBeVisible();
  await expect(page.locator('[data-voice-call]')).toHaveCount(0);

  const swap = await readSwap(page);
  // The conversation's exit animation keeps it mounted after the toggle.
  expect(swap.chatRemovedAt - enterClickedAt).toBeGreaterThan(150);
  // Leaving call mode plays the same exit before the composer returns.
  expect(swap.callRemovedAt - exitClickedAt).toBeGreaterThan(150);

  const chatStyle = await page.locator('[data-chat-flow]').evaluate((element) => element.getAttribute('style') || '');
  expect(chatStyle).toMatch(/opacity|transform/);
});
