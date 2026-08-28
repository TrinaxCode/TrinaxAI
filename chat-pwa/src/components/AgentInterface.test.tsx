import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { I18nProvider } from '../i18n/I18nContext';
import { ThemeProvider } from '../theme/ThemeContext';
import { DOCUMENT_FILE_ACCEPT, IMAGE_FILE_ACCEPT } from '../lib/attachmentAccept';
import AgentInterface from './AgentInterface';
import { expectNoA11yViolations } from '../test/a11y';

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

  it('uses separate native filters for images and documents', async () => {
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
    await expectNoA11yViolations(document.body);
  });

  it('uses the theme token for the empty-state avatar', () => {
    const { container } = render(
      <ThemeProvider>
        <I18nProvider>
          <AgentInterface onBack={vi.fn()} />
        </I18nProvider>
      </ThemeProvider>,
    );

    const avatar = container.querySelector('.agent-empty-avatar');
    expect(avatar).toBeInTheDocument();
    expect(avatar).not.toHaveClass('text-[#006bbd]');

    fireEvent.click(screen.getByRole('button', { name: 'Find bugs' }));
    expect(screen.getByRole('textbox', { name: /Ask the agent/ })).toHaveValue('Find potential bugs in my code.');
  });

  it('keeps the agent history keyboard-accessible as a modal drawer', async () => {
    localStorage.setItem('tc-agent-sessions', JSON.stringify([{
      id: 'history-1',
      title: 'Review the release',
      turns: [{ role: 'user', content: 'Review the release' }],
      workspace: '/test-workspace',
      createdAt: 1,
      updatedAt: 1,
    }]));
    const { container } = render(
      <ThemeProvider>
        <I18nProvider>
          <AgentInterface onBack={vi.fn()} />
        </I18nProvider>
      </ThemeProvider>,
    );

    const launcher = screen.getByRole('button', { name: 'Agent history' });
    fireEvent.click(launcher);
    const dialog = await screen.findByRole('dialog', { name: 'Agent history' });
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    const mainContent = Array.from(dialog.parentElement?.children ?? [])
      .find((element) => element.classList.contains('z-10')) as HTMLElement | undefined;
    expect(mainContent).toHaveAttribute('aria-hidden', 'true');
    expect(mainContent?.inert).toBe(true);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus());

    const focusable = dialog.querySelectorAll<HTMLElement>('button, input, select, textarea, [href], [tabindex]:not([tabindex="-1"])');
    fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(focusable[focusable.length - 1]);
    fireEvent.keyDown(dialog, { key: 'Tab' });
    expect(document.activeElement).toBe(focusable[0]);
    fireEvent.keyDown(dialog, { key: 'Escape' });
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('keeps manual browser dictation active after a silence until stopped', async () => {
    const previousRecognition = (window as any).SpeechRecognition;
    class FakeRecognition {
      static instances: FakeRecognition[] = [];
      continuous = false;
      onresult: ((event: any) => void) | null = null;
      onerror: ((event: any) => void) | null = null;
      onend: (() => void) | null = null;
      onstart: (() => void) | null = null;
      abort = vi.fn();

      constructor() { FakeRecognition.instances.push(this); }

      start = vi.fn(() => this.onstart?.());
    }

    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: FakeRecognition });
    vi.useFakeTimers();
    try {
      render(
        <ThemeProvider>
          <I18nProvider>
            <AgentInterface onBack={vi.fn()} />
          </I18nProvider>
        </ThemeProvider>,
      );

      fireEvent.click(screen.getByRole('button', { name: 'Voice mode' }));
      expect(FakeRecognition.instances[0].continuous).toBe(true);
      FakeRecognition.instances[0].onend?.();
      await act(async () => { vi.advanceTimersByTime(500); });
      expect(FakeRecognition.instances).toHaveLength(2);

      fireEvent.click(screen.getByRole('button', { name: 'Exit voice mode' }));
      expect(FakeRecognition.instances[1].abort).toHaveBeenCalledOnce();
    } finally {
      vi.useRealTimers();
      if (previousRecognition) Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: previousRecognition });
      else delete (window as any).SpeechRecognition;
    }
  });

  it('starts in normal mode and sends yolo false by default', async () => {
    apiMocks.runAgent.mockImplementation(async (_messages, onEvent) => {
      onEvent({ type: 'done', answer: 'Respuesta normal' });
    });

    const { container } = render(
      <ThemeProvider>
        <I18nProvider>
          <AgentInterface onBack={vi.fn()} />
        </I18nProvider>
      </ThemeProvider>,
    );

    const yoloButton = screen.getByRole('switch', { name: 'Normal mode: ask for approval' });
    expect(yoloButton).toHaveAttribute('aria-checked', 'false');
    expect(localStorage.getItem('tc-agent-yolo-mode')).toBe('0');

    fireEvent.change(container.querySelector('textarea[name="agent-prompt"]') as HTMLTextAreaElement, { target: { value: 'Haz una comprobación' } });
    fireEvent.click(screen.getByRole('button', { name: /Enviar|Send/ }));
    await waitFor(() => expect(apiMocks.runAgent).toHaveBeenCalledOnce());
    expect(apiMocks.runAgent.mock.calls[0][2]).toEqual(expect.objectContaining({ yolo: false }));
  });

  it('persists and sends yolo mode when explicitly enabled', async () => {
    apiMocks.runAgent.mockImplementation(async (_messages, onEvent) => {
      onEvent({ type: 'done', answer: 'Respuesta YOLO' });
    });

    const { container } = render(
      <ThemeProvider>
        <I18nProvider>
          <AgentInterface onBack={vi.fn()} />
        </I18nProvider>
      </ThemeProvider>,
    );

    fireEvent.click(screen.getByRole('switch', { name: 'Normal mode: ask for approval' }));
    expect(screen.getByRole('dialog', { name: 'Enable YOLO mode' })).toBeInTheDocument();
    expect(localStorage.getItem('tc-agent-yolo-mode')).toBe('0');

    fireEvent.click(screen.getByRole('button', { name: 'Enable YOLO' }));
    const yoloButton = screen.getByRole('switch', { name: 'YOLO mode enabled' });
    expect(yoloButton).toHaveAttribute('aria-checked', 'true');
    expect(yoloButton).toHaveClass('text-red-500');
    expect(localStorage.getItem('tc-agent-yolo-mode')).toBe('1');

    fireEvent.change(container.querySelector('textarea[name="agent-prompt"]') as HTMLTextAreaElement, { target: { value: 'Ejecuta la tarea' } });
    fireEvent.click(screen.getByRole('button', { name: /Enviar|Send/ }));
    await waitFor(() => expect(apiMocks.runAgent).toHaveBeenCalledOnce());
    expect(apiMocks.runAgent.mock.calls[0][2]).toEqual(expect.objectContaining({ yolo: true }));
  });

  it('does not enable yolo when its warning is cancelled', () => {
    render(
      <ThemeProvider>
        <I18nProvider>
          <AgentInterface onBack={vi.fn()} />
        </I18nProvider>
      </ThemeProvider>,
    );

    fireEvent.click(screen.getByRole('switch', { name: 'Normal mode: ask for approval' }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.getByRole('switch', { name: 'Normal mode: ask for approval' })).toHaveAttribute('aria-checked', 'false');
    expect(localStorage.getItem('tc-agent-yolo-mode')).toBe('0');
  });

  it('keeps all agent model choices available in the mobile tools menu', () => {
    const previousMatchMedia = window.matchMedia;
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        matches: query === '(max-width: 640px)',
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
    try {
      render(
        <ThemeProvider>
          <I18nProvider>
            <AgentInterface onBack={vi.fn()} />
          </I18nProvider>
        </ThemeProvider>,
      );

      const toolsButton = screen.getByRole('button', { name: 'Agent tools' });
      fireEvent.click(toolsButton);
      const toolsMenu = toolsButton.parentElement;
      expect(toolsMenu).toBeInTheDocument();
      expect(within(toolsMenu as HTMLElement).getByRole('option', { name: 'Auto | Router' })).toBeInTheDocument();
      expect(within(toolsMenu as HTMLElement).getByRole('option', { name: 'General' })).toBeInTheDocument();
      expect(within(toolsMenu as HTMLElement).getByRole('option', { name: 'Deep' })).toBeInTheDocument();
      expect(within(toolsMenu as HTMLElement).getByRole('option', { name: 'Fast' })).toBeInTheDocument();
      expect(within(toolsMenu as HTMLElement).getByRole('button', { name: 'RAG enabled' })).toBeInTheDocument();
      expect(within(toolsMenu as HTMLElement).getByRole('button', { name: 'Web search on' })).toBeInTheDocument();
      expect(within(toolsMenu as HTMLElement).getByRole('button', { name: 'Deep research' })).toBeInTheDocument();
      const yoloButton = within(toolsMenu as HTMLElement).getByRole('switch', { name: 'Normal mode: ask for approval' });
      expect(yoloButton).toHaveClass('w-full', 'text-left');
    } finally {
      Object.defineProperty(window, 'matchMedia', { configurable: true, value: previousMatchMedia });
    }
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
      model: 'auto',
      knowledgeSearch: true,
      webSearch: true,
      deepResearch: true,
    }));
    expect(apiMocks.resolveAgentModel).not.toHaveBeenCalled();
    expect(screen.getByText('Corrige los archivos del proyecto')).toBeInTheDocument();
    expect(await screen.findByText(answer, {}, { timeout: 10000 })).toBeInTheDocument();
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

  it('renders clarification first and preserves the agent conversation on follow-up', async () => {
    let call = 0;
    apiMocks.runAgent.mockImplementation(async (_messages, onEvent) => {
      call += 1;
      onEvent({
        type: 'done',
        answer: call === 1
          ? 'Antes de crear archivos, necesito saber qué tipo de negocio, qué secciones, qué colores y qué tecnología prefieres.'
          : 'Sitio creado con los requisitos indicados.',
      });
    });

    const { container } = render(
      <ThemeProvider>
        <I18nProvider>
          <AgentInterface onBack={vi.fn()} />
        </I18nProvider>
      </ThemeProvider>,
    );
    const composer = () => container.querySelector('textarea[name="agent-prompt"]') as HTMLTextAreaElement;

    fireEvent.change(composer(), { target: { value: 'Crea una página web para mi negocio' } });
    fireEvent.click(screen.getByRole('button', { name: /Enviar|Send/ }));
    await waitFor(() => expect(apiMocks.runAgent).toHaveBeenCalledOnce());
    expect(await screen.findByText(/Antes de crear archivos/)).toBeInTheDocument();

    fireEvent.change(composer(), { target: { value: 'Es una cafetería con inicio, menú y contacto, colores verdes, estilo moderno y React.' } });
    await waitFor(() => expect(screen.getByRole('button', { name: /Enviar|Send/ })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: /Enviar|Send/ }));
    await waitFor(() => expect(apiMocks.runAgent).toHaveBeenCalledTimes(2));
    expect(await screen.findByText('Sitio creado con los requisitos indicados.')).toBeInTheDocument();

    const followUpMessages = apiMocks.runAgent.mock.calls[1][0];
    expect(followUpMessages.map((message: { role: string; content: string }) => message.content)).toEqual([
      'Crea una página web para mi negocio',
      'Antes de crear archivos, necesito saber qué tipo de negocio, qué secciones, qué colores y qué tecnología prefieres.',
      'Es una cafetería con inicio, menú y contacto, colores verdes, estilo moderno y React.',
    ]);
  });

  it('shows live agent activity while a tool call is still running', async () => {
    let release!: () => void;
    apiMocks.runAgent.mockImplementation(async (_messages, onEvent) => {
      onEvent({ type: 'start', session_id: 's1', workspace: '/test-workspace', model: 'qwen3.5:4b' });
      onEvent({ type: 'status', state: 'running', elapsed_seconds: 3, idle_seconds: 3, current_tool: 'model', steps: 0, last_activity: Date.now() / 1000 });
      onEvent({ type: 'tool_start', tool: 'list_dir', dangerous: false, args: {} });
      await new Promise<void>((resolve) => { release = resolve; });
      onEvent({ type: 'done', answer: 'Listo' });
    });

    const { container } = render(
      <ThemeProvider>
        <I18nProvider>
          <AgentInterface onBack={vi.fn()} />
        </I18nProvider>
      </ThemeProvider>,
    );
    fireEvent.change(container.querySelector('textarea[name="agent-prompt"]') as HTMLTextAreaElement, { target: { value: 'Lista los archivos' } });
    fireEvent.click(screen.getByRole('button', { name: /Enviar|Send/ }));

    await waitFor(() => expect(apiMocks.runAgent).toHaveBeenCalledOnce());
    expect(screen.getByText(/Planificando|Planning|Preparando|Preparing/)).toBeInTheDocument();
    release();
    await screen.findByText('Listo');
  });
});
