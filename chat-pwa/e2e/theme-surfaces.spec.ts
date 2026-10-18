import { expect, test, type Locator, type Page } from '@playwright/test';

/**
 * Two explicit presentation decisions are locked here:
 *  - The composer uses a translucent blue-grey bar in dark mode and a white bar in
 *    light mode, without a gradient or an idle blue halo.
 *  - The AI lifecycle controls ("Apagar IA" / "Encender IA") use a solid fill
 *    in light mode; dark mode keeps the quieter tinted treatment.
 */

type Theme = 'dark' | 'light';

async function stubShell(page: Page, theme: Theme) {
  // The app-state sync treats its payload as authoritative, so the requested
  // theme has to travel in both places.
  await page.addInitScript((value) => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    localStorage.setItem('tc-lang', 'es');
    localStorage.setItem('tc-theme', value);
  }, theme);
  await page.route('**/api/network', (route) => route.fulfill({
    json: { online: true, existingInstallation: true, capabilities: { manageSystem: true } },
  }));
  await page.route('**/api/rag/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith('/app-state')) {
      return route.fulfill({
        status: 200,
        headers: { ETag: '"theme-surfaces"' },
        json: {
          schema_version: 2,
          revision: 0,
          values: { 'tc-onboarding-complete': 'true', 'tc-lang': 'es', 'tc-theme': theme },
        },
      });
    }
    if (pathname.endsWith('/v1/settings/web-search')) return route.fulfill({ json: { enabled: false, providers: {} } });
    if (pathname.endsWith('/collections')) return route.fulfill({ json: { collections: [] } });
    return route.fulfill({ json: { ok: true, memories: [], collections: [], count: 0 } });
  });
  await page.route('**/api/ollama/api/tags', (route) => route.fulfill({ json: { models: [] } }));
}

function composer(page: Page) {
  return page.locator('.composer-surface').first();
}

function composerStyle(page: Page) {
  return composer(page).evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      background: style.backgroundColor,
      backgroundImage: style.backgroundImage,
      border: style.borderTopColor,
      boxShadow: style.boxShadow,
    };
  });
}

async function expectBackgroundColor(locator: Locator, expected: string) {
  await expect.poll(() => locator.evaluate((element, color) => {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 1;
    const context = canvas.getContext('2d')!;
    const pixel = (value: string) => {
      context.clearRect(0, 0, 1, 1);
      context.fillStyle = value;
      context.fillRect(0, 0, 1, 1);
      return context.getImageData(0, 0, 1, 1).data;
    };
    const actual = pixel(getComputedStyle(element).backgroundColor);
    const target = pixel(color);
    return actual.every((value, index) => value === target[index]);
  }, expected)).toBe(true);
}

for (const theme of ['light', 'dark'] as const) {
  test(`rotates the new chat message and two working suggestions in ${theme} mode`, async ({ page }, testInfo) => {
    await stubShell(page, theme);
    await page.addInitScript(() => { Math.random = () => 0.9; });
    await page.goto('/');
    const message = page.locator('.chat-empty-motd');
    const suggestions = page.locator('.empty-chat .chip-elegant');
    await expect(message).toHaveText('TrinaxAI está listo para ayudarte con lo que tengas en mente.');
    await expect(suggestions).toHaveCount(2);
    const original = await suggestions.allTextContents();
    await expect(message).toHaveText('Describe tu idea y la convertimos en un plan claro.', { timeout: 6_000 });
    expect(await suggestions.allTextContents()).toEqual(original);
    await page.evaluate(() => { Math.random = () => 0.1; });
    await expect(suggestions).toHaveCount(2);
    await expect.poll(() => suggestions.allTextContents(), { timeout: 16_000 }).not.toEqual(original);
    await expect(suggestions.first().locator('..')).toHaveCSS('opacity', '1');
    await expect(suggestions.first()).toBeVisible();
    await expect(suggestions.last()).toBeVisible();
    await expect(message).toHaveCSS('opacity', '1');
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    if (process.env.VISUAL_AUDIT_LABEL) {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await expect(message).toHaveCSS('opacity', '1');
      await page.screenshot({ path: `visual-audit/${process.env.VISUAL_AUDIT_LABEL}/${testInfo.project.name}/welcome-rotation-${theme}.png` });
    }
    await suggestions.filter({ hasText: 'Tomar una decisión' }).click();
    await expect(page.locator('.composer-surface textarea')).toHaveValue('Ayúdame a analizar esta decisión y considerar las mejores opciones.');
  });

  test(`restores the original background, welcome logo and brand animation in ${theme} mode`, async ({ page }, testInfo) => {
    await stubShell(page, theme);
    await page.goto('/');
    await expect(composer(page)).toBeVisible();
    await expect(page.locator('[data-app-shell]')).toHaveCSS('background-color', theme === 'dark' ? 'rgb(2, 4, 6)' : 'rgb(255, 255, 255)');
    await expect(page.locator('.background-waves')).toHaveCSS('opacity', '1');
    const logo = page.locator('.empty-chat-visual img');
    await expect(logo).toHaveAttribute('src', '/logo-for-ai.webp');
    await expect(logo.locator('..')).toHaveCSS('background-color', theme === 'dark' ? 'rgb(0, 0, 0)' : 'rgb(255, 255, 255)');
    await expect(page.locator('.empty-chat-visual')).toHaveCSS('animation-name', 'float');
    await expect(logo).toHaveCSS('animation-name', theme === 'dark' ? 'glow-pulse' : 'none');
    const brand = page.locator('.chat-header .animate-brand');
    await expect(brand).toHaveCSS('animation-name', theme === 'dark' ? 'brand-shift' : 'brand-shift-light');
    await expect(brand).toHaveCSS('animation-duration', '4s');
    const colors = await brand.evaluate(async (element) => {
      const animation = element.getAnimations()[0];
      animation.pause();
      animation.currentTime = 0;
      const first = getComputedStyle(element).color;
      animation.currentTime = 2000;
      await new Promise(requestAnimationFrame);
      return [first, getComputedStyle(element).color];
    });
    expect(colors[0]).not.toBe(colors[1]);
    if (process.env.VISUAL_AUDIT_LABEL) {
      await page.screenshot({ path: `visual-audit/${process.env.VISUAL_AUDIT_LABEL}/${testInfo.project.name}/welcome-${theme}.png` });
    }
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect(brand).toHaveCSS('animation-name', 'none');
    await expect(page.locator('.empty-chat-visual')).toHaveCSS('animation-name', 'none');
    await expect(logo).toHaveCSS('animation-name', 'none');
    await expect(page.locator('.background-waves')).toHaveCSS('animation-name', 'none');
  });
}

test('keeps the dark composer slightly translucent', async ({ page }) => {
  await stubShell(page, 'dark');
  await page.goto('/');
  await expect(composer(page)).toBeVisible();
  await expect(page.locator('html')).toHaveClass(/\bdark\b/);

  // Blur first: the composer is focused on load, and every surface property
  // transitions, so the assertions below retry until the state settles.
  await page.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : undefined));
  await expect(composer(page)).toHaveCSS('border-top-color', 'rgb(53, 80, 106)');
  const idle = await composerStyle(page);
  expect(idle.background).toBe('rgba(26, 42, 58, 0.78)');
  expect(idle.backgroundImage).toBe('none');
  expect(idle.boxShadow).not.toContain('rgba(22, 141, 226');

  await page.locator('.composer-surface textarea').first().focus();
  await expect(composer(page)).toHaveCSS('border-top-color', 'rgba(22, 141, 226, 0.55)');
  const focused = await composerStyle(page);
  expect(focused.boxShadow).toContain('rgba(22, 141, 226, 0.16)');
});

test('keeps the light composer slightly translucent', async ({ page }) => {
  await stubShell(page, 'light');
  await page.goto('/');
  await expect(composer(page)).toBeVisible();
  await expect(page.locator('html')).toHaveClass(/\blight\b/);

  await expect(composer(page)).toHaveCSS('background-color', 'rgba(255, 255, 255, 0.85)');
  await expect(composer(page)).toHaveCSS('border-top-color', 'rgb(203, 217, 229)');
  const style = await composerStyle(page);
  expect(style.backgroundImage).toBe('none');
});

test('renders the AI lifecycle controls as solid fills in light mode', async ({ page }) => {
  await stubShell(page, 'light');
  await page.goto('/#/settings/advanced');

  const shutdown = page.getByRole('button', { name: 'Apagar IA' });
  const startup = page.getByRole('button', { name: 'Encender IA' });
  await expect(shutdown).toBeVisible();
  await expect(shutdown).toHaveCSS('background-color', 'rgb(220, 38, 38)');
  await expect(shutdown).toHaveCSS('color', 'rgb(255, 255, 255)');
  await expect(startup).toHaveCSS('background-color', 'rgb(4, 120, 87)');
  await expect(startup).toHaveCSS('color', 'rgb(255, 255, 255)');
});

test('keeps the quiet tinted AI lifecycle controls in dark mode', async ({ page }) => {
  await stubShell(page, 'dark');
  await page.goto('/#/settings/advanced');

  const shutdown = page.getByRole('button', { name: 'Apagar IA' });
  await expect(shutdown).toBeVisible();
  await expectBackgroundColor(shutdown, 'rgba(239, 68, 68, 0.1)');
  await expectBackgroundColor(page.getByRole('button', { name: 'Encender IA' }), 'rgba(34, 197, 94, 0.1)');
});
