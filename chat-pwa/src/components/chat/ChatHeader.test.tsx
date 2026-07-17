import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { I18nProvider } from '../../i18n/I18nContext';
import { ThemeProvider } from '../../theme/ThemeContext';
import ChatHeader from './ChatHeader';

function renderHeader(messageCount = 1) {
  const actions = {
    onMenuToggle: vi.fn(),
    onEngineChange: vi.fn(),
    onResearchModeChange: vi.fn(),
    onWebSearchModeChange: vi.fn(),
    onExportMenuChange: vi.fn(),
    onExportMarkdown: vi.fn(),
    onExportPdf: vi.fn(),
    onExportWord: vi.fn(),
  };
  render(
    <ThemeProvider>
      <I18nProvider>
        <ChatHeader
          engine="ollama"
          temporary={false}
          isDark
          messageCount={messageCount}
          researchMode={false}
          webSearchMode={false}
          exportMenuOpen={false}
          {...actions}
        />
      </I18nProvider>
    </ThemeProvider>,
  );
  return actions;
}

describe('ChatHeader', () => {
  it('disables export for an empty conversation', () => {
    renderHeader(0);
    expect(screen.getByRole('button', { name: /(export|download) chat/i })).toBeDisabled();
  });

  it('exposes menu, export, research and engine actions', async () => {
    const user = userEvent.setup();
    const actions = renderHeader();

    await user.click(screen.getByRole('button', { name: /abrir historial|open history/i }));
    await user.click(screen.getByRole('button', { name: /(export|download) chat/i }));
    await user.click(screen.getByRole('button', { name: /(activar|enable|toggle) deep research/i }));
    await user.click(screen.getByRole('button', { name: /activar búsqueda en internet|toggle web search/i }));

    expect(actions.onMenuToggle).toHaveBeenCalledOnce();
    expect(actions.onExportMenuChange).toHaveBeenCalledWith(true);
    expect(actions.onResearchModeChange).toHaveBeenCalledWith(true);
    expect(actions.onWebSearchModeChange).toHaveBeenCalledWith(true);
  });
});
