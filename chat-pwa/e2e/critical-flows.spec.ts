import { expect, test, type Page } from '@playwright/test';

const attachmentId = 'e'.repeat(32);

async function stubShell(page: Page, canManageSystem = true) {
  await page.addInitScript(() => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    localStorage.setItem('tc-lang', 'en');
    localStorage.setItem('tc-thinking-mode', '1');
  });
  await page.route('**/api/network', (route) => route.fulfill({
    json: { online: true, existingInstallation: true, capabilities: { manageSystem: canManageSystem } },
  }));
  await page.route('**/api/rag/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith('/app-state')) {
      return route.fulfill({
        status: 200,
        headers: { ETag: '"trinaxai-critical-flows"' },
        json: { schema_version: 2, revision: 0, values: { 'tc-onboarding-complete': 'true', 'tc-lang': 'en' } },
      });
    }
    if (pathname.endsWith('/v1/settings/web-search')) {
      return route.fulfill({ json: { enabled: false, providers: {} } });
    }
    if (pathname.endsWith('/collections')) return route.fulfill({ json: { collections: [] } });
    return route.fulfill({ json: { ok: true, memories: [], collections: [], count: 0 } });
  });
  await page.route('**/api/ollama/api/tags', (route) => route.fulfill({
    json: { models: [{ name: 'qwen3.5:4b', model: 'qwen3.5:4b', size: 1 }] },
  }));
}

test('does not move empty chat content when RAG context appears', async ({ page }) => {
  await stubShell(page);
  await page.goto('/');
  await expect(page.locator('.animate-float')).toBeVisible();
  await expect(page.locator('.chat-empty-motd')).toBeVisible();
  await expect(page.locator('.chip-elegant').first()).toBeVisible();
  await expect(page.locator('.chip-elegant').first()).toHaveCSS('opacity', '1');

  const before = await page.evaluate(() => {
    const read = (selector: string) => {
      const element = document.querySelector(selector);
      return element instanceof HTMLElement ? { top: element.offsetTop, height: element.offsetHeight } : null;
    };
    return {
      logo: read('.animate-float'),
      motd: read('.chat-empty-motd'),
      chip: read('.chip-elegant'),
    };
  });

  await page.getByRole('button', { name: 'RAG' }).click();
  await expect(page.locator('.chat-active-collections')).toBeVisible();
  await expect(page.locator('.chat-active-collections')).toHaveCSS('position', 'absolute');
  await expect(page.locator('.chat-active-collections').getByRole('button', { name: 'General' })).toBeVisible();

  const after = await page.evaluate(() => {
    const read = (selector: string) => {
      const element = document.querySelector(selector);
      return element instanceof HTMLElement ? { top: element.offsetTop, height: element.offsetHeight } : null;
    };
    return {
      logo: read('.animate-float'),
      motd: read('.chat-empty-motd'),
      chip: read('.chip-elegant'),
    };
  });
  expect(after.logo && before.logo ? after.logo.top : -1).toBe(before.logo?.top ?? -2);
  expect(after.motd && before.motd ? after.motd.top : -1).toBe(before.motd?.top ?? -2);
  expect(after.chip && before.chip ? after.chip.top : -1).toBe(before.chip?.top ?? -2);
});

test('routes public lookup and personal history, then requires explicit Agent mode for website creation', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop', 'One desktop routing flow covers the automatic capability selector.');
  await stubShell(page);

  let researchCalls = 0;
  let ragCalls = 0;
  let agentCalls = 0;
  await page.route('**/api/rag/v1/settings/web-search', (route) => route.fulfill({
    json: { enabled: true, preferred_provider: 'duckduckgo', active_provider: 'duckduckgo', providers: {} },
  }));
  await page.route('**/api/rag/v1/research/preflight', (route) => route.fulfill({ json: { ok: true, model: 'test-model' } }));
  await page.route('**/api/rag/v1/research', (route) => {
    researchCalls += 1;
    return route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'data: {"trinaxai_research":{"web_search":true,"web_provider":"test","search_query":"public lookup"}}',
        'data: {"choices":[{"delta":{"content":"Web result"}}]}',
        'data: {"trinaxai_finish":{"reason":"stop","status":"complete"}}',
        'data: {"trinaxai_sources":[{"file":"public","url":"https://example.test","kind":"web","project":"","snippet":"result","score":1}]}',
        'data: [DONE]',
        '',
      ].join('\n\n'),
    });
  });
  await page.route('**/api/rag/v1/chat/completions', (route) => {
    ragCalls += 1;
    return route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'data: {"trinaxai":{"mode":"knowledge","rag_used":true}}',
        'data: {"choices":[{"delta":{"content":"RAG result"}}]}',
        'data: {"trinaxai_finish":{"reason":"stop","status":"complete"}}',
        'data: [DONE]',
        '',
      ].join('\n\n'),
    });
  });
  await page.route('**/api/rag/v1/agent', (route) => {
    agentCalls += 1;
    return route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'data: {"type":"start","session_id":"routing-agent","workspace":"/test-workspace","model":"test-model"}',
        'data: {"type":"done","answer":"Agent request received","completion_status":"complete"}',
        'data: [DONE]',
        '',
      ].join('\n\n'),
    });
  });

  await page.goto('/');
  const input = page.getByRole('textbox', { name: /Type a message/ });
  const send = page.getByRole('button', { name: 'Send' });

  await input.fill('Busca quién es TrinaxCode');
  await send.click();
  await expect(page.locator('#tc-main-content').getByText('Web result')).toBeVisible({ timeout: 10_000 });
  expect(page.url()).not.toContain('#/agent');
  expect(researchCalls).toBe(1);
  expect(ragCalls).toBe(0);
  expect(agentCalls).toBe(0);

  await input.fill('Dime qué programas Python he hecho');
  await send.click();
  await expect(page.locator('#tc-main-content').getByText('RAG result')).toBeVisible({ timeout: 10_000 });
  expect(researchCalls).toBe(1);
  expect(ragCalls).toBe(1);
  expect(agentCalls).toBe(0);

  await input.fill('Quiero crear una página web para mi negocio');
  await page.getByRole('button', { name: 'Open TrinaxAI Agent' }).click();
  await expect(page).toHaveURL(/#\/agent$/);
  const agentPage = page.locator('#tc-main-content');
  await agentPage.getByRole('textbox', { name: /Ask the agent/ }).fill('Quiero crear una página web para mi negocio');
  await agentPage.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText('Agent request received')).toBeVisible({ timeout: 10_000 });
  expect(researchCalls).toBe(1);
  expect(ragCalls).toBe(1);
  expect(agentCalls).toBe(1);
});

test('keeps reasoning private and automatically continues a length-limited answer', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop', 'One desktop stream covers provider framing.');
  await stubShell(page);
  let calls = 0;
  await page.route('**/api/ollama/api/chat', (route) => {
    calls += 1;
    const body = calls === 1
      ? [
        { message: { thinking: 'I inspected the request. ' }, done: false },
        { message: { content: 'First half ' }, done: false },
        { message: {}, done: true, done_reason: 'length' },
      ]
      : [
        { message: { thinking: 'I checked the ending.' }, done: false },
        { message: { content: 'second half.' }, done: false },
        { message: {}, done: true, done_reason: 'stop' },
      ];
    return route.fulfill({
      status: 200,
      contentType: 'application/x-ndjson',
      body: `${body.map((value) => JSON.stringify(value)).join('\n')}\n`,
    });
  });

  await page.goto('/');
  await page.getByRole('textbox', { name: /Type a message/ }).fill('Tell me something about a blue door.');
  await page.getByRole('button', { name: 'Send' }).click();

  await expect(page.locator('#tc-main-content .chat-plain-text').filter({ hasText: 'First half second half.' })).toBeVisible({ timeout: 10_000 });
  expect(calls).toBe(2);
  await expect(page.getByRole('button', { name: /thought for|is thinking/i })).toHaveCount(0);
  await expect(page.getByText(/I inspected the request|I checked the ending/)).toHaveCount(0);
});

test('opens mobile PDF fallback and downloads Office files from a LAN hostname', async ({ page, baseURL }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-mobile', 'The PDF fallback is specific to a phone viewport.');
  await stubShell(page, false);
  await page.addInitScript(({ id }) => {
    const now = Date.now();
    localStorage.setItem('tc-chat-sessions', JSON.stringify([{
      id: 'attachments', title: 'Attachments', engine: 'ollama', createdAt: now, updatedAt: now,
      messages: [{
        role: 'user', content: 'Files', documentAttachments: [
          { name: 'manual.pdf', size: 8, mimeType: 'application/pdf', storageKey: `server:${id}`, kind: 'document' },
          { name: 'slides.pptx', size: 8, mimeType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation', storageKey: `server:${id}`, kind: 'document' },
        ],
      }],
    }]));
  }, { id: attachmentId });
  await page.route(`**/api/rag/attachments/${attachmentId}`, (route) => route.fulfill({
    status: 200,
    contentType: 'application/octet-stream',
    body: 'test-file',
  }));
  let systemOpenRequests = 0;
  await page.route(`**/api/rag/attachments/${attachmentId}/open`, (route) => {
    systemOpenRequests += 1;
    return route.fulfill({ json: { ok: true } });
  });

  const port = new URL(baseURL!).port;
  await page.goto(`http://trinaxai.test:${port}/`);
  await page.getByRole('button', { name: /Open history/ }).click();
  await page.getByText('Attachments', { exact: true }).click();
  await page.getByRole('button', { name: /manual\.pdf/ }).click();
  await expect(page.getByRole('dialog', { name: 'manual.pdf' })).toBeVisible();
  await expect(page.getByText('This format cannot be displayed in the mobile viewer. Use Download to open it on your device.')).toBeVisible();
  await expect(page.locator('object[type="application/pdf"]')).toHaveCount(0);
  await page.getByRole('button', { name: 'Close' }).click();

  await page.getByRole('button', { name: /slides\.pptx/ }).click();
  const officeDialog = page.getByRole('dialog', { name: 'slides.pptx' });
  await officeDialog.getByRole('button', { name: 'Open' }).click();
  await expect.poll(() => systemOpenRequests).toBe(0);
  const downloadPromise = page.waitForEvent('download');
  await officeDialog.getByRole('button', { name: 'Download' }).click();
  expect((await downloadPromise).suggestedFilename()).toMatch(/\.pptx$/i);

  await page.goto('/');
  await page.getByRole('button', { name: /Open history/ }).click();
  await page.getByText('Attachments', { exact: true }).click();
  await page.getByRole('button', { name: /slides\.pptx/ }).click();
  await page.getByRole('dialog', { name: 'slides.pptx' }).getByRole('button', { name: 'Open' }).click();
  await expect.poll(() => systemOpenRequests).toBe(1);
});

test('honors server capabilities for stop-all and LAN scope gates', async ({ page, baseURL }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop', 'One desktop policy flow is sufficient.');
  await stubShell(page);
  let stopRequests = 0;
  await page.route('**/api/system/stop-all', (route) => {
    stopRequests += 1;
    return route.fulfill({ json: { ok: true } });
  });
  await page.goto('/#/settings/general');
  const stopButton = page.getByRole('button', { name: 'Stop all TrinaxAI' });
  await stopButton.click();
  await page.getByRole('dialog').getByRole('button', { name: 'Stop all TrinaxAI' }).click();
  await expect.poll(() => stopRequests).toBe(1);

  await page.unroute('**/api/network');
  await page.route('**/api/network', (route) => route.fulfill({
    json: { online: true, existingInstallation: true, capabilities: { manageSystem: false } },
  }));
  const port = new URL(baseURL!).port;
  await page.goto(`http://trinaxai.test:${port}/#/agent`);
  await expect(page.getByRole('heading', { name: 'Permission required' })).toBeVisible({ timeout: 10_000 });
  await expect(page.getByText(/TrinaxAI Agent can use files and tools/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Stop all TrinaxAI' })).toHaveCount(0);
});

test('offers a local AI recovery action only for the local service outage', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop', 'One desktop recovery flow is sufficient.');
  await stubShell(page);
  let chatCalls = 0;
  let startupCalls = 0;
  await page.route('**/api/ollama/api/chat', (route) => {
    chatCalls += 1;
    const body = chatCalls === 1
      ? { detail: { code: 'proxy_unavailable' } }
      : { error: { category: 'model_loading_failed', code: 'ERR_MODEL_LOADING_FAILED' } };
    return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify(body) });
  });
  await page.route('**/api/system/startup', (route) => {
    startupCalls += 1;
    return route.fulfill({ json: { ok: true } });
  });

  await page.goto('/');
  const input = page.getByRole('textbox', { name: /Type a message/ });
  await input.fill('Check local availability.');
  await page.getByRole('button', { name: 'Send' }).click();

  const notifications = page.getByRole('region', { name: 'Notifications' });
  await expect(notifications.getByText(/The local AI service is unavailable\./)).toBeVisible({ timeout: 10_000 });
  const startButton = notifications.getByRole('button', { name: 'Start AI' });
  await expect(startButton).toBeVisible();
  await startButton.click();
  await expect.poll(() => startupCalls).toBe(1);
  await expect(notifications.getByRole('button', { name: 'Start AI' })).toHaveCount(0);

});

test('does not offer local AI startup for model errors', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop', 'One desktop error-policy flow is sufficient.');
  await stubShell(page);
  let chatCalls = 0;
  await page.route('**/api/ollama/api/chat', (route) => {
    chatCalls += 1;
    return route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ error: { category: 'model_loading_failed', code: 'ERR_MODEL_LOADING_FAILED' } }),
    });
  });

  await page.goto('/');
  const input = page.getByRole('textbox', { name: /Type a message/ });
  await input.fill('Try a model request.');
  await page.getByRole('button', { name: 'Send' }).click();

  await expect.poll(() => chatCalls).toBe(1);
  await expect(page.locator('#tc-main-content').getByText(/The AI model could not be loaded\./)).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole('region', { name: 'Notifications' }).getByRole('button', { name: 'Start AI' })).toHaveCount(0);
});
