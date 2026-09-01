import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { configure } from '@testing-library/dom';
import { cleanup } from '@testing-library/react';

afterEach(() => cleanup());

// Instrumented coverage runs are slower than the normal suite; keep async UI
// assertions from failing while React finishes the same state transition.
configure({ asyncUtilTimeout: 5_000 });

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => undefined,
    removeListener: () => undefined,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    dispatchEvent: () => false,
  }),
});

Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
  configurable: true,
  value: () => undefined,
});
