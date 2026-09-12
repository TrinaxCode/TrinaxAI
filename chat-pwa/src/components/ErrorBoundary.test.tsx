import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ErrorBoundary from './ErrorBoundary';

function BrokenSection() {
  throw new Error('TypeError: secret implementation detail at Widget.tsx:42');
}

describe('ErrorBoundary', () => {
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('logs the developer error without rendering it to the user', () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    localStorage.setItem('tc-lang', 'es');
    render(<ErrorBoundary><BrokenSection /></ErrorBoundary>);

    expect(screen.getByText('No pudimos mostrar esta sección')).toBeInTheDocument();
    expect(screen.queryByText(/TypeError|Widget\.tsx|secret implementation/)).not.toBeInTheDocument();
    expect(log).toHaveBeenCalled();
  });

  it('renders the English fallback when English is selected', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    localStorage.setItem('tc-lang', 'en');
    render(<ErrorBoundary><BrokenSection /></ErrorBoundary>);

    expect(screen.getByText('We could not display this section')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Fix this error' })).toBeInTheDocument();
  });

  it('opens repair guidance without exposing the thrown error', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    localStorage.setItem('tc-lang', 'en');
    render(<ErrorBoundary><BrokenSection /></ErrorBoundary>);

    screen.getByRole('button', { name: 'Fix this error' }).click();
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveTextContent('Your data is safe'));
    expect(screen.getByRole('dialog')).not.toHaveTextContent('secret implementation');
  });
});
