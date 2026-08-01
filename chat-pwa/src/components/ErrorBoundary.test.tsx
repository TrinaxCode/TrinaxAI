import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ErrorBoundary from './ErrorBoundary';

function BrokenSection() {
  throw new Error('TypeError: secret implementation detail at Widget.tsx:42');
}

describe('ErrorBoundary', () => {
  afterEach(() => vi.restoreAllMocks());

  it('logs the developer error without rendering it to the user', () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    render(<ErrorBoundary><BrokenSection /></ErrorBoundary>);

    expect(screen.getByText('No pudimos mostrar esta sección')).toBeInTheDocument();
    expect(screen.queryByText(/TypeError|Widget\.tsx|secret implementation/)).not.toBeInTheDocument();
    expect(log).toHaveBeenCalled();
  });
});
