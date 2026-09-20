import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ToggleSwitch from './ToggleSwitch';

const theme = vi.hoisted(() => ({ isDark: false }));
vi.mock('../i18n/I18nContext', () => ({ useI18n: () => ({ t: (key: string) => ({ ollamaEngine: 'Ollama', ragEngine: 'RAG' }[key] || key) }) }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => theme }));

describe('ToggleSwitch engine paths', () => {
  it('toggles both engines and covers light/dark inactive styles', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    const { rerender } = render(<ToggleSwitch engine="ollama" onChange={onChange} />);
    await user.click(screen.getByRole('switch', { name: 'RAG' }));
    await user.click(screen.getByRole('button', { name: 'RAG', exact: true }));
    await user.click(screen.getByRole('button', { name: 'Ollama', exact: true }));
    expect(onChange).toHaveBeenNthCalledWith(1, 'rag');
    expect(onChange).toHaveBeenNthCalledWith(2, 'rag');
    expect(onChange).toHaveBeenNthCalledWith(3, 'ollama');

    theme.isDark = true;
    rerender(<ToggleSwitch engine="rag" onChange={onChange} />);
    expect(screen.getByRole('switch', { name: 'RAG' })).toHaveAttribute('aria-checked', 'true');
    await user.click(screen.getByRole('switch', { name: 'RAG' }));
    expect(onChange).toHaveBeenLastCalledWith('ollama');
    theme.isDark = false;
  });
});
