import { StrictMode } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { I18nProvider } from '../i18n/I18nContext';
import { ThemeProvider } from '../theme/ThemeContext';
import { DOCUMENT_FILE_ACCEPT, IMAGE_FILE_ACCEPT } from '../lib/attachmentAccept';
import AgentInterface from './AgentInterface';

const apiMocks = vi.hoisted(() => ({
  runAgent: vi.fn(),
  approveAgentAction: vi.fn(),
  resolveAgentModel: vi.fn(async (model: string) => model),
  extractDocumentText: vi.fn(),
}));

vi.mock('../lib/api', async (importOriginal) => {
  const original = await importOriginal<typeof import('../lib/api')>();
  return {
    ...original,
    agentWorkspaceRoot: () => '/test-workspace',
    approveAgentAction: apiMocks.approveAgentAction,
    extractDocumentText: apiMocks.extractDocumentText,
    resolveAgentModel: apiMocks.resolveAgentModel,
    runAgent: apiMocks.runAgent,
  };
});

describe('AgentInterface handoff', () => {
  beforeEach(() => {
    localStorage.clear();
    apiMocks.runAgent.mockReset();
    apiMocks.resolveAgentModel.mockClear();
    apiMocks.extractDocumentText.mockReset();
  });

  it('uses separate native filters for images and documents', () => {
    const { container } = render(
      <ThemeProvider>
        <I18nProvider>
          <AgentInterface onBack={vi.fn()} />
        </I18nProvider>
      </ThemeProvider>,
    );

    const imageInput = container.querySelector('input[type="file"]:not([multiple])') as HTMLInputElement;
    const documentInput = container.querySelector('input[type="file"][multiple]') as HTMLInputElement;

    expect(imageInput.accept).toBe(IMAGE_FILE_ACCEPT);
    expect(imageInput.hasAttribute('capture')).toBe(false);
    expect(documentInput.accept).toBe(DOCUMENT_FILE_ACCEPT);
    expect(documentInput.accept).not.toContain('image/');
  });

  it('uses the theme token for the empty-state avatar', () => {
    const { container } = render(
      <ThemeProvider>
        <I18nProvider>
          <AgentInterface onBack={vi.fn()} />
        </I18nProvider>
      </ThemeProvider>,
    );

    expect(container.querySelector('.agent-empty-avatar')).toBeInTheDocument();
    expect(container.querySelector('.agent-empty-avatar')).not.toHaveClass('text-[#006bbd]');
  });

  it('continues a transferred request exactly once in React StrictMode', async () => {
    const answer = 'Trabajo recibido y procesado con una salida progresiva. '.repeat(8).trim();
    apiMocks.runAgent.mockImplementation(async (_messages, onEvent) => {
      onEvent({ type: 'token', content: answer.slice(0, 170) });
      onEvent({ type: 'token', content: answer.slice(170) });
      onEvent({ type: 'done', answer });
    });
    const onRequestConsumed = vi.fn();

    render(
      <StrictMode>
        <ThemeProvider>
          <I18nProvider>
            <AgentInterface
              onBack={vi.fn()}
              initialRequest={{
                id: 'handoff-1',
                prompt: 'Corrige los archivos del proyecto',
                context: [{ role: 'assistant', content: 'Contexto anterior' }],
              }}
              onRequestConsumed={onRequestConsumed}
            />
          </I18nProvider>
        </ThemeProvider>
      </StrictMode>,
    );

    await waitFor(() => expect(apiMocks.runAgent).toHaveBeenCalledOnce());
    expect(screen.queryByText(answer)).not.toBeInTheDocument();
    expect(onRequestConsumed).toHaveBeenCalledOnce();
    expect(apiMocks.runAgent.mock.calls[0][0]).toEqual([
      expect.objectContaining({ role: 'system' }),
      { role: 'assistant', content: 'Contexto anterior' },
      { role: 'user', content: 'Corrige los archivos del proyecto' },
    ]);
    expect(apiMocks.runAgent.mock.calls[0][2]).toEqual(expect.objectContaining({
      model: expect.any(String),
      knowledgeSearch: true,
      webSearch: false,
      deepResearch: false,
    }));
    expect(apiMocks.resolveAgentModel).toHaveBeenCalledOnce();
    expect(screen.getByText('Corrige los archivos del proyecto')).toBeInTheDocument();
    expect(await screen.findByText(answer, {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it('extracts an attached document and sends it as persistent agent context', async () => {
    apiMocks.extractDocumentText.mockResolvedValue({
      ok: true,
      name: 'reporte.txt',
      text: 'Contenido verificable del reporte',
      chars: 32,
      truncated: false,
    });
    apiMocks.runAgent.mockImplementation(async (_messages, onEvent) => {
      onEvent({ type: 'start', session_id: 's1', workspace: '/test-workspace', model: 'qwen3.5:4b' });
      onEvent({ type: 'done', answer: 'Documento analizado' });
    });

    const { container } = render(
      <ThemeProvider>
        <I18nProvider>
          <AgentInterface onBack={vi.fn()} />
        </I18nProvider>
      </ThemeProvider>,
    );

    const documentInput = container.querySelector('input[type="file"][multiple]') as HTMLInputElement;
    fireEvent.change(documentInput, { target: { files: [new File(['raw'], 'reporte.txt', { type: 'text/plain' })] } });
    expect(await screen.findByText('reporte.txt')).toBeInTheDocument();
    fireEvent.change(container.querySelector('textarea') as HTMLTextAreaElement, { target: { value: 'Resume los hallazgos' } });
    fireEvent.click(screen.getByRole('button', { name: /Enviar|Send/ }));

    await waitFor(() => expect(apiMocks.runAgent).toHaveBeenCalledOnce());
    const sentMessages = apiMocks.runAgent.mock.calls[0][0];
    expect(sentMessages.at(-1).content).toContain('[Documento adjunto temporal: reporte.txt]');
    expect(sentMessages.at(-1).content).toContain('Contenido verificable del reporte');
    expect(screen.getByText('reporte.txt')).toBeInTheDocument();
    expect(await screen.findByText('Documento analizado')).toBeInTheDocument();

    fireEvent.change(container.querySelector('textarea') as HTMLTextAreaElement, { target: { value: '¿Qué decía el reporte?' } });
    fireEvent.click(screen.getByRole('button', { name: /Enviar|Send/ }));
    await waitFor(() => expect(apiMocks.runAgent).toHaveBeenCalledTimes(2));
    const followUpMessages = apiMocks.runAgent.mock.calls[1][0];
    expect(followUpMessages.find((message: { role: string }) => message.role === 'user').content)
      .toContain('Contenido verificable del reporte');
  });
});
