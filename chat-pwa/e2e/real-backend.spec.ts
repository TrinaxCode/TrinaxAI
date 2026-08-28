import { expect, test } from '@playwright/test';

test.describe('@real', () => {
  test.skip(process.env.TRINAXAI_E2E_REAL !== '1', 'Runs only in the real-backend E2E job.');

  test('reaches FastAPI and exercises deterministic chat through the PWA gateway', async ({ page }) => {
    await page.goto('/');

    const health = await page.evaluate(async () => {
      const response = await fetch('/api/rag/health', { cache: 'no-store' });
      return { status: response.status, body: await response.json() };
    });
    expect(health.status).toBe(200);
    expect(health.body.ok).toBe(true);

    const resources = await page.evaluate(async () => {
      const response = await fetch('/api/rag/resources', { cache: 'no-store' });
      return { status: response.status, body: await response.json() };
    });
    expect(resources.status).toBe(200);
    expect(resources.body.ok).toBe(true);

    const chat = await page.evaluate(async () => {
      // The isolated backend starts with the protected default collection and
      // no indexed nodes. Keep this request within the chat/read scope instead
      // of creating a collection, which correctly requires local system auth.
      const response = await fetch('/api/rag/v1/chat/completions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: [{ role: 'user', content: 'Answer only from the selected knowledge collection.' }],
          mode: 'knowledge',
          collections: ['default'],
          stream: false,
        }),
      });
      return {
        status: response.status,
        contentType: response.headers.get('content-type'),
        body: await response.json(),
      };
    });
    expect(chat.status).toBe(200);
    expect(chat.contentType).toMatch(/application\/json/);
    expect(chat.body).toMatchObject({
      id: expect.stringMatching(/^chatcmpl-/),
      object: 'chat.completion',
      created: expect.any(Number),
      choices: [
        {
          index: 0,
          message: {
            role: 'assistant',
            content: 'The selected collection contains no indexed documents.',
          },
          finish_reason: 'stop',
        },
      ],
      usage: {
        prompt_tokens: expect.any(Number),
        completion_tokens: expect.any(Number),
        total_tokens: expect.any(Number),
      },
      trinaxai: {
        mode: 'knowledge',
        rag_used: true,
        abstained: true,
        result_count: 0,
        sources: [],
      },
    });
  });
});
