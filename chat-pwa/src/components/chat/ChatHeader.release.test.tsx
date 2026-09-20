import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { I18nProvider } from '../../i18n/I18nContext';
import { ThemeProvider } from '../../theme/ThemeContext';
import ChatHeader from './ChatHeader';

function renderHeader(overrides: Partial<React.ComponentProps<typeof ChatHeader>> = {}) {
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
  const result = render(
    <ThemeProvider>
      <I18nProvider>
        <ChatHeader
          engine="ollama"
          isDark={false}
          messageCount={2}
          researchMode
          webSearchMode
          exportMenuOpen={false}
          {...actions}
          {...overrides}
        />
      </I18nProvider>
    </ThemeProvider>,
  );
  return { ...result, actions };
}

describe('ChatHeader release interactions', () => {
  it('exports each format and closes on outside click or Escape', async () => {
    const user = userEvent.setup();
    const { actions, rerender } = renderHeader({ exportMenuOpen: true });
    await user.click(screen.getByRole('button', { name: /markdown/i }));
    expect(actions.onExportMarkdown).toHaveBeenCalledOnce();
    expect(actions.onExportMenuChange).toHaveBeenCalledWith(false);

    rerender(
      <ThemeProvider>
        <I18nProvider>
          <ChatHeader engine="ollama" isDark={false} messageCount={2} researchMode={false} webSearchMode={false} exportMenuOpen onMenuToggle={actions.onMenuToggle} onEngineChange={actions.onEngineChange} onResearchModeChange={actions.onResearchModeChange} onWebSearchModeChange={actions.onWebSearchModeChange} onExportMenuChange={actions.onExportMenuChange} onExportMarkdown={actions.onExportMarkdown} onExportPdf={actions.onExportPdf} onExportWord={actions.onExportWord} />
        </I18nProvider>
      </ThemeProvider>,
    );
    fireEvent.pointerDown(document.body);
    expect(actions.onExportMenuChange).toHaveBeenCalledWith(false);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(actions.onExportMenuChange).toHaveBeenCalledWith(false);
  });

  it('covers temporary, mobile tools, and optional web/agent controls', async () => {
    const user = userEvent.setup();
    const onOpenAgent = vi.fn();
    const { container, unmount } = renderHeader({ temporary: true, onOpenAgent });
    expect(screen.getByLabelText(/Temporary chat|Chat temporal/i)).toBeInTheDocument();

    const tools = screen.getByRole('button', { name: 'Tools' });
    await user.click(tools);
    const popup = container.querySelectorAll('[data-header-tools]')[1] as HTMLElement;
    await user.click(within(popup).getByRole('button', { name: 'Open TrinaxAI Agent' }));
    expect(onOpenAgent).toHaveBeenCalledOnce();

    await user.click(tools);
    const popupAgain = container.querySelectorAll('[data-header-tools]')[1] as HTMLElement;
    await user.click(within(popupAgain).getByRole('button', { name: 'Toggle Deep Research' }));
    await user.click(tools);
    const popupThird = container.querySelectorAll('[data-header-tools]')[1] as HTMLElement;
    await user.click(within(popupThird).getByRole('button', { name: 'Toggle web search' }));

    unmount();
    const hiddenWeb = renderHeader({ webSearchAvailable: false });
    expect(screen.queryAllByRole('button', { name: 'Toggle web search' })).toHaveLength(0);
    hiddenWeb.unmount();
  });
});
