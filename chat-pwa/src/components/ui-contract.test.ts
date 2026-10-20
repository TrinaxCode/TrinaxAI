import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

/**
 * Presentation contracts that are easy to regress and hard to assert from the
 * DOM: they live in CSS, so the guard reads the stylesheet itself.
 */
function readCss(relativePath: string): string {
  return readFileSync(new URL(relativePath, import.meta.url), 'utf8');
}

const chatModernCss = readCss('./chat/chat-modern.css');
const chatCss = readCss('./chat/chat.css');
const indexCss = readCss('../index.css');

describe('chat presentation contracts', () => {
  it('keeps the empty-chat hero free of the removed ring effect', () => {
    expect(chatModernCss).not.toContain('.empty-chat-visual > div::after');
    expect(chatModernCss).not.toContain('@keyframes tc-ring-breathe');
  });

  it('keeps assistant answers free of drop shadows', () => {
    const bubbleBlock = chatModernCss.slice(
      chatModernCss.indexOf('/* Message bubbles keep a flat framed surface'),
      chatModernCss.indexOf('html.dark .chat-assistant-avatar'),
    );
    expect(bubbleBlock.length).toBeGreaterThan(0);
    expect(bubbleBlock).toContain('box-shadow: none');
  });

  it('draws assistant answers as unframed prose', () => {
    const block = chatModernCss.slice(
      chatModernCss.indexOf('.chat-bubble.chat-bubble-assistant,'),
      chatModernCss.indexOf('.chat-bubble-assistant-dark {'),
    );
    expect(block).toContain('background: transparent');
    expect(block).toContain('border: 0');
  });

  it('drops the per-message clock', () => {
    expect(chatModernCss).not.toContain('chat-message-time');
  });

  it('keeps pulsing glow confined to the original welcome logo', () => {
    expect(chatModernCss).not.toContain('tc-glow-pulse');
    expect(indexCss).toContain('.animate-glow');
  });

  it('reveals the model label only on hover or focus', () => {
    expect(chatModernCss).toMatch(/\.chat-model-label \{[^}]*opacity: 0/);
    expect(chatModernCss).toMatch(/\.chat-row:hover \.chat-model-label,[\s\S]*?\.chat-row:focus-within \.chat-model-label \{[^}]*opacity: 1/);
    expect(chatModernCss).toMatch(/\.chat-actions \{[^}]*opacity: 0/);
    expect(chatModernCss).toMatch(/\.chat-row:hover \.chat-actions,\s*\.chat-row:focus-within \.chat-actions,[^{]*\{[^}]*opacity: 1/);
    for (const status of ['pending', 'cancelled', 'error']) {
      expect(chatModernCss).toContain(`[data-completion-status="${status}"]`);
    }
  });

  it('never lets a hidden control capture taps', () => {
    expect(chatModernCss).toMatch(/\.chat-actions \{[^}]*pointer-events: none/);
    expect(chatModernCss).toMatch(/\.chat-row:hover \.chat-actions,\s*\.chat-row:focus-within \.chat-actions,[^{]*\{[^}]*pointer-events: auto/);
    expect(indexCss).toMatch(/\.hover-reveal \{[^}]*pointer-events: none/);
    expect(indexCss).toMatch(/@media \(hover: none\), \(pointer: coarse\) \{\s*\.hover-reveal \{[^}]*pointer-events: auto/);
  });

  it('gives the rotating activity label room for its cross-fade', () => {
    const block = chatCss.slice(
      chatCss.indexOf('.chat-generating-label {'),
      chatCss.indexOf('.chat-generating-label > span'),
    );
    expect(block.length).toBeGreaterThan(0);
    // The labels fade in and out with a 5px vertical shift: without the padded
    // clip box the text is sliced while it moves.
    expect(block).toMatch(/padding-block: 5px/);
    expect(block).toMatch(/margin-block: -5px/);
    expect(block).toContain('overflow: hidden');
  });

  it('never turns message rows into nested scroll containers', () => {
    // `overflow-x: hidden` alone computes `overflow-y: auto`, which paints a
    // second scrollbar inside the message when its content grows momentarily.
    for (const selector of ['.chat-row', '.chat-bubble-wrap']) {
      const pattern = new RegExp(`(?:^|\\n)${selector.replace('.', '\\.')} \\{([^}]*)\\}`, 'g');
      const block = [...chatCss.matchAll(pattern)].map((match) => match[1]).join('\n');
      expect(block, selector).toContain('overflow-x: clip');
      expect(block, selector).toContain('overflow-y: visible');
      expect(block, selector).not.toContain('overflow-x: hidden');
    }
  });

  it('keeps a comfortable block while an answer streams', () => {
    const block = chatCss.slice(
      chatCss.indexOf('.chat-bubble-streaming {'),
      chatCss.indexOf('.chat-generating-indicator {'),
    );
    expect(block).toMatch(/\.chat-bubble-streaming \{[^}]*min-width: 18rem/);
    expect(chatCss).toMatch(/@media \(max-width: 640px\) \{\s*\.chat-bubble-streaming \{[^}]*min-width: 0/);
  });

  it('keeps the generating dots attached and visible on narrow screens', () => {
    const indicator = chatCss.slice(
      chatCss.indexOf('.chat-generating-indicator {'),
      chatCss.indexOf('.chat-generating-label {'),
    );
    const label = chatCss.slice(
      chatCss.indexOf('.chat-generating-label {'),
      chatCss.indexOf('.chat-generating-label > span'),
    );
    expect(indicator).toContain('justify-content: flex-start');
    expect(indicator).toContain('gap: 0.35rem');
    expect(label).toContain('overflow-wrap: anywhere');
    expect(label).toContain('white-space: normal');
    expect(chatCss).toMatch(/\.chat-generating-dots \{[^}]*flex: 0 0 auto/);
  });

  it('renders active chat header tools as blue icons without a filled square', () => {
    const start = indexCss.indexOf('.chat-header [data-header-tools] button[aria-pressed="true"]');
    expect(start).toBeGreaterThan(-1);
    const block = indexCss.slice(start, indexCss.indexOf('}', start));
    expect(block).toContain('background-color: transparent');
    const iconRule = indexCss.slice(indexCss.indexOf('.chat-header [data-header-tools] button[aria-pressed="true"] svg'));
    expect(iconRule).toContain('color: #168de2');
  });

  it('keeps the dark composer slightly translucent', () => {
    const start = chatModernCss.indexOf('html.dark .composer-surface {');
    expect(start).toBeGreaterThan(-1);
    const block = chatModernCss.slice(start, chatModernCss.indexOf('}', start));
    expect(block).toContain('background: rgba(26, 42, 58, 0.78)');
    expect(block).not.toContain('linear-gradient');
  });
});

describe('agent presentation contracts', () => {
  it('renders active header tools as blue icons without a filled square', () => {
    const start = indexCss.indexOf('.page-header button[aria-pressed="true"]');
    expect(start).toBeGreaterThan(-1);
    const block = indexCss.slice(start, indexCss.indexOf('}', start));
    expect(block).toContain('background-color: transparent');
    const iconRule = indexCss.slice(indexCss.indexOf('.page-header button[aria-pressed="true"] svg'));
    expect(iconRule).toContain('color: #168de2');
  });

  it('sizes the app shell from dynamic viewport units so iOS shows no strip under the app', () => {
    // window.innerHeight stops above the home indicator in the installed iOS PWA;
    // the measured value is only a fallback for browsers without dvh.
    const block = indexCss.slice(indexCss.indexOf('@supports (height: 100dvh)'));
    expect(block).toContain('#root');
    expect(block).toContain('.app-shell');
    expect(block).toContain('height: 100dvh');
    expect(indexCss).toContain('height: var(--app-height, 100vh)');
  });
});
