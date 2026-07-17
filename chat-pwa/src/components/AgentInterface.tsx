import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { MdAdd, MdArrowBack, MdCheck, MdClose, MdContentCopy, MdDelete, MdEdit, MdExpandLess, MdExpandMore, MdFolder, MdHistory, MdImage, MdMic, MdPublic, MdRefresh, MdScience, MdSearch, MdSend, MdSmartToy, MdStop, MdStorage, MdUploadFile } from 'react-icons/md';
import { useTheme } from '../theme/ThemeContext';
import { useI18n } from '../i18n/I18nContext';
import { DOCUMENT_FILE_ACCEPT, IMAGE_FILE_ACCEPT } from '../lib/attachmentAccept';
import {
  agentWorkspaceRoot,
  approveAgentAction,
  cancelAgentRun,
  describeImageForAgent,
  prepareImageForVision,
  extractDocumentText,
  indexableFilesFrom,
  DEFAULT_MODEL_SETTINGS,
  modelSetting,
  resolveAgentModel,
  routeOllamaModel,
  runAgent,
  type AgentEvent,
  type ChatMessage,
} from '../lib/api';
import { detectBackendVoice, transcribeAudio } from '../services/voice';
import { startAudioRecorder, type AudioRecorder } from '../utils/audioRecorder';
import { useAgentHistory } from '../hooks/useAgentHistory';
import { useWaitingSound } from '../hooks/useWaitingSound';
import { audioManager } from '../services/audioManager';
import { streamFlushSize } from '../hooks/useStreamChat';
import FolderPicker from './FolderPicker';
import ChatMarkdown from './chat/ChatMarkdown';
import type { AgentHandoff } from './chat/modeRouter';
import type { Translate } from './chat/types';

interface AgentInterfaceProps {
  onBack: () => void;
  initialRequest?: AgentHandoff | null;
  onRequestConsumed?: (id: string) => void;
}

/** A tool invocation and its lifecycle, shown as a step card. */
interface AgentStep {
  id: string;
  tool: string;
  dangerous: boolean;
  args: Record<string, string>;
  status: 'running' | 'awaiting' | 'done' | 'denied';
  result?: string;
  approvalId?: string;
  runSessionId?: string;
}

interface AttachedAgentDocument {
  name: string;
  content: string;
  truncated: boolean;
}

type AgentModelMode = 'auto' | 'chat' | 'code' | 'deep' | 'fast';

const AGENT_DOC_MAX_FILES = 20;
const AGENT_DOC_MAX_CHARS = 32_000;
const AGENT_DOC_TOTAL_MAX_CHARS = 48_000;
const AGENT_MODEL_KEYS: Record<Exclude<AgentModelMode, 'auto'>, keyof typeof DEFAULT_MODEL_SETTINGS> = {
  chat: 'tc-models-chat',
  code: 'tc-models-code',
  deep: 'tc-models-deep',
  fast: 'tc-models-fast',
};

/** A turn in the agent conversation. */
export interface AgentTurn {
  role: 'user' | 'assistant';
  content: string;
  /** Full hidden request context, including extracted attachments, for follow-ups. */
  contextContent?: string;
  steps?: AgentStep[];
  image?: string;
  documents?: Array<{ name: string; truncated: boolean; preview?: string }>;
  model?: string;
}

const DANGEROUS_HINT: Record<string, 'toolWrite' | 'toolEdit' | 'toolRun'> = {
  write_file: 'toolWrite',
  edit_file: 'toolEdit',
  run_command: 'toolRun',
};

function argSummary(tool: string, args: Record<string, string>): string {
  if (tool === 'run_command') return args.command ?? '';
  if (tool === 'write_file') return args.path ?? '';
  if (tool === 'edit_file') return args.path ?? '';
  if (tool === 'read_file' || tool === 'list_dir') return args.path ?? '.';
  if (tool === 'glob' || tool === 'grep') return args.pattern ?? '';
  if (tool === 'search_knowledge' || tool === 'web_search') return args.query ?? '';
  return Object.values(args).join(' ');
}

export default function AgentInterface({ onBack, initialRequest, onRequestConsumed }: AgentInterfaceProps) {
  const { isDark } = useTheme();
  const { t, lang } = useI18n();
  const voiceLang = lang === 'en' ? 'en-US' : 'es-ES';
  const isMobile = typeof window !== 'undefined' && window.matchMedia?.('(max-width: 640px)').matches;
  const [turns, setTurns] = useState<AgentTurn[]>([]);
  const [input, setInput] = useState('');
  const [running, setRunning] = useState(false);
  // The waiting cue is a "thinking" sound: it must stop the moment TrinaxAI
  // starts answering (first streamed token), not linger through the whole
  // typewriter render. `running` alone stays true until the turn fully ends.
  const [answering, setAnswering] = useState(false);
  const [agentActivity, setAgentActivity] = useState('');
  useWaitingSound(running && !answering);
  useEffect(() => {
    if (running && !answering) audioManager.play('agent-working');
    if (answering) audioManager.play('first-token');
  }, [answering, running]);
  const [workspace, setWorkspace] = useState(() => agentWorkspaceRoot());
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyClosing, setHistoryClosing] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [webSearch, setWebSearch] = useState<boolean>(() => {
    try { return localStorage.getItem('tc-agent-web-search') === '1'; } catch { return false; }
  });
  const [knowledgeSearch, setKnowledgeSearch] = useState<boolean>(() => {
    try { return localStorage.getItem('tc-agent-knowledge-search') !== '0'; } catch { return true; }
  });
  const [deepResearch, setDeepResearch] = useState<boolean>(() => {
    try { return localStorage.getItem('tc-agent-deep-research') === '1'; } catch { return false; }
  });
  const [mobileToolsOpen, setMobileToolsOpen] = useState(false);
  const [modelMode, setModelMode] = useState<AgentModelMode>(() => {
    try {
      const saved = localStorage.getItem('tc-agent-model-mode');
      return saved && ['auto', 'chat', 'code', 'deep', 'fast'].includes(saved)
        ? saved as AgentModelMode
        : 'auto';
    } catch { return 'auto'; }
  });
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const [attachedDocs, setAttachedDocs] = useState<AttachedAgentDocument[]>([]);
  const [imageError, setImageError] = useState('');
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false);
  const [analyzingImage, setAnalyzingImage] = useState(false);
  const [listening, setListening] = useState(false);
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editingText, setEditingText] = useState('');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const copiedTimerRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const agentRunSessionRef = useRef<string | null>(null);
  const runningRef = useRef(false);
  const claimedRequestRef = useRef<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const historyCloseTimerRef = useRef<number | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const docInputRef = useRef<HTMLInputElement | null>(null);
  const attachmentMenuRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const recognitionRef = useRef<any>(null);
  const recorderRef = useRef<AudioRecorder | null>(null);
  const recorderRunRef = useRef(0);
  const typewriterQueueRef = useRef('');
  const typewriterTextRef = useRef('');
  const typewriterFrameRef = useRef<number | null>(null);
  const typewriterTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typewriterWaitersRef = useRef<Array<() => void>>([]);
  const typewriterCancelRef = useRef<() => void>(() => undefined);
  const sawAgentTokenRef = useRef(false);
  const history = useAgentHistory();
  const sessionIdRef = useRef<string | null>(null);

  const voiceSupported = typeof window !== 'undefined' &&
    !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  const dictationAvailable = voiceSupported || detectBackendVoice();
  const placeholder = isMobile ? t('agentPlaceholderShort') : t('agentPlaceholder');

  useEffect(() => {
    requestAnimationFrame(() => {
      const el = inputRef.current;
      if (!el) return;
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, window.innerHeight * 0.5)}px`;
    });
  }, [input]);

  useEffect(() => { try { localStorage.setItem('tc-agent-web-search', webSearch ? '1' : '0'); } catch { /* ignore */ } }, [webSearch]);
  useEffect(() => { try { localStorage.setItem('tc-agent-knowledge-search', knowledgeSearch ? '1' : '0'); } catch { /* ignore */ } }, [knowledgeSearch]);
  useEffect(() => { try { localStorage.setItem('tc-agent-deep-research', deepResearch ? '1' : '0'); } catch { /* ignore */ } }, [deepResearch]);
  useEffect(() => { try { localStorage.setItem('tc-agent-model-mode', modelMode); } catch { /* ignore */ } }, [modelMode]);

  useEffect(() => {
    if (!attachmentMenuOpen) return undefined;
    const close = (event: PointerEvent) => {
      if (!attachmentMenuRef.current?.contains(event.target as Node)) setAttachmentMenuOpen(false);
    };
    window.addEventListener('pointerdown', close);
    return () => window.removeEventListener('pointerdown', close);
  }, [attachmentMenuOpen]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [turns]);

  useEffect(() => () => {
    abortRef.current?.abort();
    typewriterCancelRef.current();
    if (historyCloseTimerRef.current !== null) window.clearTimeout(historyCloseTimerRef.current);
    if (copiedTimerRef.current !== null) window.clearTimeout(copiedTimerRef.current);
    try { recognitionRef.current?.abort?.(); } catch { /* ignore */ }
    recorderRunRef.current += 1;
    recorderRef.current?.cancel();
  }, []);

  // Persist the running conversation to the agent's own history store.
  useEffect(() => {
    if (turns.length === 0) return;
    if (!sessionIdRef.current) sessionIdRef.current = history.newSession(workspace);
    history.saveTurns(sessionIdRef.current, turns, workspace);
    // history functions are stable; depend only on the data that should trigger a save.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turns, workspace]);

  // Mutate the last (assistant) turn — used by every streamed event.
  const patchAssistant = useCallback((fn: (turn: AgentTurn) => AgentTurn) => {
    setTurns((prev) => {
      if (prev.length === 0) return prev;
      const next = [...prev];
      const last = next[next.length - 1];
      if (last.role !== 'assistant') return prev;
      next[next.length - 1] = fn(last);
      return next;
    });
  }, []);

  const resolveTypewriterWaiters = useCallback(() => {
    const waiters = typewriterWaitersRef.current.splice(0);
    waiters.forEach((resolve) => resolve());
  }, []);

  const cancelAgentTypewriter = useCallback(() => {
    if (typewriterFrameRef.current !== null) {
      window.cancelAnimationFrame(typewriterFrameRef.current);
      typewriterFrameRef.current = null;
    }
    if (typewriterTimerRef.current !== null) {
      window.clearTimeout(typewriterTimerRef.current);
      typewriterTimerRef.current = null;
    }
    typewriterQueueRef.current = '';
    resolveTypewriterWaiters();
  }, [resolveTypewriterWaiters]);
  typewriterCancelRef.current = cancelAgentTypewriter;

  const flushAgentTypewriter = useCallback(() => {
    typewriterFrameRef.current = null;
    typewriterTimerRef.current = null;
    const pending = typewriterQueueRef.current;
    if (!pending) {
      resolveTypewriterWaiters();
      return;
    }
    const visible = pending.slice(0, streamFlushSize(pending.length));
    typewriterQueueRef.current = pending.slice(visible.length);
    typewriterTextRef.current += visible;
    const currentText = typewriterTextRef.current;
    patchAssistant((turn) => ({ ...turn, content: currentText }));
    if (typewriterQueueRef.current) {
      typewriterTimerRef.current = window.setTimeout(flushAgentTypewriter, 18);
    } else {
      resolveTypewriterWaiters();
    }
  }, [patchAssistant, resolveTypewriterWaiters]);

  const queueAgentText = useCallback((text: string) => {
    if (!text) return;
    typewriterQueueRef.current += text;
    if (typewriterQueueRef.current.length >= 8192) {
      flushAgentTypewriter();
      return;
    }
    if (typewriterFrameRef.current === null && typewriterTimerRef.current === null) {
      typewriterFrameRef.current = window.requestAnimationFrame(flushAgentTypewriter);
    }
  }, [flushAgentTypewriter]);

  const waitForAgentTypewriter = useCallback(() => {
    if (!typewriterQueueRef.current && typewriterFrameRef.current === null && typewriterTimerRef.current === null) {
      return Promise.resolve();
    }
    return new Promise<void>((resolve) => {
      typewriterWaitersRef.current.push(resolve);
    });
  }, []);

  const handleEvent = useCallback((event: AgentEvent) => {
    switch (event.type) {
      case 'start':
        agentRunSessionRef.current = event.session_id;
        setAgentActivity(lang === 'en' ? 'Starting agent' : 'Iniciando agente');
        patchAssistant((turn) => ({ ...turn, model: event.model }));
        break;
      case 'status':
        setAgentActivity(event.current_tool
          ? `${lang === 'en' ? 'Using' : 'Usando'} ${event.current_tool} · ${event.elapsed_seconds}s`
          : `${lang === 'en' ? 'Planning' : 'Planificando'} · ${event.elapsed_seconds}s`);
        break;
      case 'tool_start':
        setAgentActivity(`${lang === 'en' ? 'Using' : 'Usando'} ${event.tool}`);
        audioManager.play('tool-running');
        patchAssistant((turn) => ({
          ...turn,
          steps: [
            ...(turn.steps ?? []),
            {
              id: `${event.tool}-${(turn.steps?.length ?? 0)}-${Date.now()}`,
              tool: event.tool,
              dangerous: event.dangerous,
              args: event.args,
              status: 'running',
            },
          ],
        }));
        break;
      case 'approval_request':
        audioManager.play('confirmation');
        patchAssistant((turn) => {
          const steps = [...(turn.steps ?? [])];
          // Attach to the most recent running step for this tool.
          for (let i = steps.length - 1; i >= 0; i -= 1) {
            if (steps[i].tool === event.tool && steps[i].status === 'running') {
              steps[i] = { ...steps[i], status: 'awaiting', approvalId: event.approval_id, runSessionId: agentRunSessionRef.current ?? undefined, args: event.args };
              break;
            }
          }
          return { ...turn, steps };
        });
        break;
      case 'tool_result':
        setAgentActivity(lang === 'en' ? 'Processing tool result' : 'Procesando resultado');
        audioManager.play('tool-complete');
        patchAssistant((turn) => {
          const steps = [...(turn.steps ?? [])];
          for (let i = steps.length - 1; i >= 0; i -= 1) {
            if (steps[i].tool === event.tool && (steps[i].status === 'running' || steps[i].status === 'awaiting')) {
              const denied = /denied by user/i.test(event.result);
              steps[i] = { ...steps[i], status: denied ? 'denied' : 'done', result: event.result };
              break;
            }
          }
          return { ...turn, steps };
        });
        break;
      case 'token':
        setAgentActivity(lang === 'en' ? 'Writing response' : 'Escribiendo respuesta');
        if (!sawAgentTokenRef.current) setAnswering(true);
        sawAgentTokenRef.current = true;
        queueAgentText(event.content);
        break;
      case 'done':
        setAgentActivity(lang === 'en' ? 'Completed' : 'Completado');
        // A tool-only turn (no streamed tokens) still stops "thinking" here.
        setAnswering(true);
        if (!sawAgentTokenRef.current) queueAgentText(event.answer);
        break;
      case 'error':
        setAgentActivity(lang === 'en' ? 'Recoverable error' : 'Error recuperable');
        queueAgentText(`\n\n❌ ${event.error}`);
        break;
      default:
        break;
    }
  }, [lang, patchAssistant, queueAgentText]);

  const approve = useCallback(async (step: AgentStep, approved: boolean) => {
    if (!step.approvalId || !step.runSessionId) return;
    // Optimistically reflect the decision; the tool_result event confirms it.
    patchAssistant((turn) => ({
      ...turn,
      steps: (turn.steps ?? []).map((s) =>
        s.id === step.id ? { ...s, status: approved ? 'running' : 'denied' } : s,
      ),
    }));
    try {
      await approveAgentAction(step.runSessionId, step.approvalId, approved);
    } catch { /* stream will surface the error */ }
  }, [patchAssistant]);

  const execute = useCallback(async (
    rawText: string,
    opts: {
      seedContext?: ChatMessage[];
      image?: string | null;
      documents?: AttachedAgentDocument[];
      documentMeta?: AgentTurn['documents'];
      contextContent?: string;
      priorTurns?: AgentTurn[];
    } = {},
  ) => {
    const { seedContext = [], image = null, documents = [], documentMeta = [], contextContent, priorTurns } = opts;
    const text = rawText.trim();
    if ((!text && !image && !documents.length) || runningRef.current) return;
    runningRef.current = true;
    cancelAgentTypewriter();
    typewriterTextRef.current = '';
    sawAgentTokenRef.current = false;
    setAnswering(false);
    // `priorTurns` lets edit/regenerate replay from a truncated history; a normal
    // send just continues from the current turns.
    const baseTurns = priorTurns ?? turns;
    const history: ChatMessage[] = seedContext.length
      ? [
          {
            role: 'system',
            content: 'The following messages are compact context from the previous chat. Work on the final user request inside the configured workspace. Never assume dangerous actions are approved.',
          },
          ...seedContext,
        ]
      : baseTurns.map((turn) => ({ role: turn.role, content: turn.contextContent ?? turn.content, model: turn.model }));
    const displayContent = text || t('analyzeAttachedFiles');
    const displayDocuments = documents.length
      ? documents.map(({ name, truncated, content }) => ({ name, truncated, preview: content.slice(0, 180) }))
      : documentMeta;
    const userTurnIndex = baseTurns.length;
    setTurns([
      ...baseTurns,
      {
        role: 'user',
        content: displayContent,
        image: image || undefined,
        documents: displayDocuments,
      },
      { role: 'assistant', content: '' },
    ]);
    setInput('');
    setRunning(true);
    setAgentActivity(lang === 'en' ? 'Starting agent' : 'Iniciando agente');
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      // A text-only agent can't see pixels: run one local vision pass and hand
      // the agent a written description as extra context for the request.
      let requestText = contextContent || displayContent;
      if (!contextContent && documents.length) {
        requestText += `\n\n${documents.map((document) => `[Documento adjunto temporal: ${document.name}${document.truncated ? ' (truncado)' : ''}]\n\`\`\`text\n${document.content}\n\`\`\``).join('\n\n')}`;
      }
      if (image && !contextContent) {
        setAnalyzingImage(true);
        try {
          const description = await describeImageForAgent(image, text, controller.signal);
          if (description) requestText = `${requestText}\n\n[${t('agentImageContext')}]:\n${description}`;
        } catch (err) {
          if (!controller.signal.aborted) {
            const msg = err instanceof Error ? err.message.slice(0, 200) : t('imagePrepFailed');
            queueAgentText(`\n\n❌ ${msg}`);
          }
        } finally {
          setAnalyzingImage(false);
        }
      }
      if (controller.signal.aborted) return;
      setTurns((current) => current.map((turn, index) => (
        index === userTurnIndex && turn.role === 'user'
          ? { ...turn, contextContent: requestText }
          : turn
      )));
      const routingText = `${text}\n${documents.map((document) => `${document.name}\n${document.content.slice(0, 2000)}`).join('\n')}\n${contextContent?.slice(0, 3000) ?? ''}`.trim();
      const candidateModel = modelMode === 'auto'
        ? routeOllamaModel(routingText || displayContent, history)
        : modelSetting(AGENT_MODEL_KEYS[modelMode], DEFAULT_MODEL_SETTINGS[AGENT_MODEL_KEYS[modelMode]]);
      const model = await resolveAgentModel(candidateModel);
      const userMessage: ChatMessage = { role: 'user', content: requestText };
      await runAgent([...history, userMessage], handleEvent, {
        workspace,
        model,
        webSearch,
        knowledgeSearch,
        deepResearch,
        signal: controller.signal,
      });
      await waitForAgentTypewriter();
    } catch (err) {
      if (!controller.signal.aborted) {
        const msg = err instanceof Error ? err.message.slice(0, 300) : t('agentFailed');
        queueAgentText(`\n\n❌ ${msg}`);
        await waitForAgentTypewriter();
      }
    } finally {
      runningRef.current = false;
      setRunning(false);
      setAgentActivity('');
      setAnalyzingImage(false);
      abortRef.current = null;
    }
  }, [turns, workspace, webSearch, knowledgeSearch, deepResearch, modelMode, handleEvent, cancelAgentTypewriter, queueAgentText, waitForAgentTypewriter, t]);

  const send = useCallback(async () => {
    const image = attachedImage;
    const documents = attachedDocs;
    setAttachedImage(null);
    setAttachedDocs([]);
    setImageError('');
    await execute(input, { image, documents });
  }, [execute, input, attachedImage, attachedDocs]);

  useEffect(() => {
    if (!initialRequest || claimedRequestRef.current === initialRequest.id) return undefined;
    // Defer one tick: React StrictMode cancels the first effect setup in dev.
    // Claiming inside the timer guarantees exactly one real agent request.
    const timer = window.setTimeout(() => {
      if (claimedRequestRef.current === initialRequest.id) return;
      claimedRequestRef.current = initialRequest.id;
      onRequestConsumed?.(initialRequest.id);
      void execute(initialRequest.prompt, { seedContext: initialRequest.context });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [execute, initialRequest, onRequestConsumed]);

  const stop = useCallback(() => {
    const sessionId = agentRunSessionRef.current;
    if (sessionId) void cancelAgentRun(sessionId).catch(() => undefined);
    abortRef.current?.abort();
    cancelAgentTypewriter();
    runningRef.current = false;
    setRunning(false);
    setAnalyzingImage(false);
    setAgentActivity('');
  }, [cancelAgentTypewriter]);

  const persistWorkspace = useCallback((value: string) => {
    const v = value.trim();
    setWorkspace(v);
    try { localStorage.setItem('tc-agent-workspace', v); } catch { /* ignore */ }
  }, []);

  // ── Image attachment (routed through a local vision pass on send) ──
  const onPickImage = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    try {
      setImageError('');
      audioManager.play('file-received');
      setAttachedImage(await prepareImageForVision(file));
      audioManager.play('file-ready');
    } catch (err) {
      setAttachedImage(null);
      setImageError(err instanceof Error ? err.message : t('imagePrepFailed'));
    }
  }, [t]);

  const onPickDocs = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = indexableFilesFrom(Array.from(e.target.files ?? [])).slice(0, AGENT_DOC_MAX_FILES);
    e.target.value = '';
    if (!files.length) return;
    try {
      setImageError('');
      audioManager.play('file-processing');
      const perFileBudget = Math.max(1_000, Math.min(AGENT_DOC_MAX_CHARS, Math.floor(AGENT_DOC_TOTAL_MAX_CHARS / files.length)));
      const documents: AttachedAgentDocument[] = [];
      for (const file of files) {
        try {
          const extracted = await extractDocumentText(file);
          const content = extracted.text.slice(0, perFileBudget);
          if (content.trim()) {
            documents.push({ name: file.name, content, truncated: extracted.truncated || content.length < extracted.text.length });
          }
        } catch { /* Match the main chat: keep every document that did extract. */ }
      }
      if (!documents.length) throw new Error(t('chatDocReadFailed'));
      setAttachedDocs(documents);
      audioManager.play('file-ready');
    } catch (err) {
      setImageError(err instanceof Error ? err.message.slice(0, 180) : t('chatDocReadFailed'));
    }
  }, [t]);

  // ── Speech-to-text (dictation into the composer) ──
  const stopDictation = useCallback(() => {
    try { recognitionRef.current?.abort?.(); } catch { /* ignore */ }
    recognitionRef.current = null;
    recorderRunRef.current += 1;
    recorderRef.current?.cancel();
    recorderRef.current = null;
    setListening(false);
  }, []);

  const startDictation = useCallback(async () => {
    if (voiceSupported) {
      const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      const rec = new SR();
      rec.lang = voiceLang;
      rec.interimResults = true;
      rec.continuous = false;
      let finalText = '';
      rec.onresult = (ev: any) => {
        let interim = '';
        for (let i = ev.resultIndex; i < ev.results.length; i += 1) {
          const tr = ev.results[i][0].transcript;
          if (ev.results[i].isFinal) finalText += tr; else interim += tr;
        }
        setInput((finalText + interim).trim());
      };
      rec.onerror = () => { setListening(false); recognitionRef.current = null; };
      rec.onend = () => { setListening(false); recognitionRef.current = null; };
      rec.onstart = () => setListening(true);
      recognitionRef.current = rec;
      try { rec.start(); } catch { setListening(false); recognitionRef.current = null; }
      return;
    }
    // Backend fallback: record until silence, then transcribe.
    if (!detectBackendVoice()) return;
    const runId = ++recorderRunRef.current;
    try {
      const recorder = await startAudioRecorder({
        onStart: () => setListening(true),
        onSilence: async (blob) => {
          recorderRef.current = null;
          setListening(false);
          try {
            const text = await transcribeAudio(blob, voiceLang);
            if (text.trim()) setInput((prev) => `${prev ? `${prev} ` : ''}${text.trim()}`);
          } catch { setImageError(t('voiceRecognitionFailed')); }
        },
        onError: () => { recorderRef.current = null; setListening(false); },
      }, 2200);
      if (runId !== recorderRunRef.current) {
        recorder.cancel();
        return;
      }
      recorderRef.current = recorder;
    } catch {
      setListening(false);
      setImageError(t('voiceRecognitionFailed'));
    }
  }, [voiceSupported, voiceLang, t]);

  const toggleDictation = useCallback(() => {
    if (listening) stopDictation();
    else void startDictation();
  }, [listening, startDictation, stopDictation]);

  // ── Message actions (copy / edit+resend / regenerate) ──
  const copyText = useCallback(async (text: string, key: string) => {
    if (!text.trim()) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      if (copiedTimerRef.current !== null) window.clearTimeout(copiedTimerRef.current);
      copiedTimerRef.current = window.setTimeout(() => {
        setCopiedKey((current) => (current === key ? null : current));
        copiedTimerRef.current = null;
      }, 1400);
    } catch { /* clipboard permissions vary by browser */ }
  }, []);

  const startEdit = useCallback((index: number) => {
    if (runningRef.current) return;
    setEditingIndex(index);
    setEditingText(turns[index]?.content ?? '');
  }, [turns]);

  const cancelEdit = useCallback(() => {
    setEditingIndex(null);
    setEditingText('');
  }, []);

  const saveEdit = useCallback(() => {
    if (editingIndex === null) return;
    const text = editingText.trim();
    if (!text) { cancelEdit(); return; }
    const priorTurns = turns.slice(0, editingIndex);
    const originalTurn = turns[editingIndex];
    const image = originalTurn?.image ?? null;
    const contextContent = originalTurn?.contextContent?.startsWith(originalTurn.content)
      ? `${text}${originalTurn.contextContent.slice(originalTurn.content.length)}`
      : undefined;
    setEditingIndex(null);
    setEditingText('');
    void execute(text, { image, priorTurns, contextContent, documentMeta: originalTurn?.documents });
  }, [editingIndex, editingText, turns, execute, cancelEdit]);

  // Re-run the user turn that produced this assistant turn.
  const regenerate = useCallback((assistantIndex: number) => {
    if (runningRef.current) return;
    const userIndex = assistantIndex - 1;
    const userTurn = turns[userIndex];
    if (!userTurn || userTurn.role !== 'user') return;
    void execute(userTurn.content, {
      image: userTurn.image ?? null,
      priorTurns: turns.slice(0, userIndex),
      contextContent: userTurn.contextContent,
      documentMeta: userTurn.documents,
    });
  }, [turns, execute]);

  const startNewSession = useCallback(() => {
    abortRef.current?.abort();
    cancelAgentTypewriter();
    runningRef.current = false;
    setRunning(false);
    setTurns([]);
    setAttachedImage(null);
    setAttachedDocs([]);
    setImageError('');
    setAttachmentMenuOpen(false);
    sessionIdRef.current = null;
    history.setActiveId(null);
    setHistoryOpen(false);
  }, [cancelAgentTypewriter, history]);

  const openSession = useCallback((id: string) => {
    const session = history.sessions.find((s) => s.id === id);
    if (!session) return;
    abortRef.current?.abort();
    cancelAgentTypewriter();
    runningRef.current = false;
    setRunning(false);
    setTurns(session.turns);
    setAttachedImage(null);
    setAttachedDocs([]);
    setImageError('');
    setAttachmentMenuOpen(false);
    setWorkspace(session.workspace || agentWorkspaceRoot());
    sessionIdRef.current = session.id;
    history.selectSession(id);
    setHistoryOpen(false);
  }, [cancelAgentTypewriter, history]);

  const filteredSessions = history.sessions.filter((s) =>
    !search.trim() || s.title.toLowerCase().includes(search.trim().toLowerCase()),
  );

  // Play the drawer's exit animation before unmounting it.
  const closeHistory = useCallback(() => {
    setHistoryClosing(true);
    if (historyCloseTimerRef.current !== null) window.clearTimeout(historyCloseTimerRef.current);
    historyCloseTimerRef.current = window.setTimeout(() => {
      historyCloseTimerRef.current = null;
      setHistoryOpen(false);
      setHistoryClosing(false);
    }, 240);
  }, []);

  // Re-opening while the drawer is still closing must cancel the old timer.
  // Otherwise the stale close callback hides the newly opened history panel.
  const openHistory = useCallback(() => {
    if (historyCloseTimerRef.current !== null) {
      window.clearTimeout(historyCloseTimerRef.current);
      historyCloseTimerRef.current = null;
    }
    setHistoryClosing(false);
    setHistoryOpen(true);
  }, []);

  const surface = isDark ? 'text-white' : 'text-gray-900';
  const subtle = isDark ? 'text-white/50' : 'text-gray-500';
  const cardBg = isDark ? 'bg-white/[0.04] border-white/[0.08]' : 'bg-gray-50 border-gray-200';

  return (
    <div className={`relative flex h-full min-h-0 w-full overflow-hidden ${surface}`}>
      {/* History sidebar */}
      {historyOpen && (
        <>
          <div className={`fixed inset-0 z-[55] bg-black/40 ${historyClosing ? 'animate-overlay-out' : 'animate-overlay-in'}`} onClick={closeHistory} />
          <aside
            className={`fixed left-0 top-0 z-[60] flex h-dvh w-[85vw] max-w-[300px] flex-col border-r backdrop-blur-xl sm:w-72 ${historyClosing ? 'animate-drawer-out' : 'animate-drawer-in'} ${isDark ? 'border-white/10 bg-black/85' : 'border-gray-200 bg-white/90'}`}
            style={{ paddingBottom: 'env(safe-area-inset-bottom, 0px)' }}
          >
            <div className={`flex items-center gap-2 border-b px-3 py-3 ${isDark ? 'border-white/10' : 'border-gray-200'}`} style={{ paddingTop: 'calc(env(safe-area-inset-top, 0px) + 0.75rem)' }}>
              <MdHistory size={18} className="text-[#006bbd]" />
              <span className="text-sm font-semibold">{t('agentHistory')}</span>
              <button onClick={closeHistory} className={`ml-auto rounded-lg p-1 ${isDark ? 'hover:bg-white/10' : 'hover:bg-gray-100'}`} aria-label={t('close')}>
                <MdClose size={18} />
              </button>
            </div>
            <div className="p-2">
              <div className={`flex items-center gap-2 rounded-lg border px-2.5 py-1.5 ${isDark ? 'border-white/10 bg-white/[0.03]' : 'border-gray-200 bg-gray-50'}`}>
                <MdSearch size={15} className={subtle} />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder={t('agentSearchHistory')}
                  aria-label={t('agentSearchHistory')}
                  className="min-w-0 flex-1 bg-transparent text-xs outline-none"
                />
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
              {filteredSessions.length === 0 ? (
                <p className={`px-2 py-6 text-center text-xs ${subtle}`}>{t('agentNoHistory')}</p>
              ) : (
                filteredSessions.map((session, i) => (
                  <div
                    key={session.id}
                    className={`group flex items-center gap-1 rounded-lg px-2 py-2 text-sm ${session.id === history.activeId ? (isDark ? 'bg-white/10' : 'bg-gray-100') : isDark ? 'hover:bg-white/[0.05]' : 'hover:bg-gray-50'}`}
                  >
                    <button onClick={() => openSession(session.id)} className="min-w-0 flex-1 truncate text-left">
                      {session.title || t('agentUntitled')}
                    </button>
                    <button
                      onClick={() => history.deleteSession(session.id)}
                      className={`shrink-0 rounded p-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 focus-visible:opacity-100 ${isDark ? 'text-white/40 hover:text-red-400' : 'text-gray-500 hover:text-red-600'}`}
                      aria-label={t('delete')}
                    >
                      <MdDelete size={15} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </aside>
        </>
      )}

      {pickerOpen && (
        <FolderPicker
          initialPath={workspace}
          onSelect={(path) => { persistWorkspace(path); setPickerOpen(false); }}
          onClose={() => setPickerOpen(false)}
        />
      )}

      <div className="relative z-10 flex h-full min-h-0 w-full flex-col">
        {/* Header */}
        <nav
          className={`relative z-10 flex shrink-0 items-center gap-2 border-b px-3 backdrop-blur-xl ${isDark ? 'border-white/[0.06] bg-black/40' : 'border-gray-200 bg-white/50'}`}
          style={{ minHeight: '46px', paddingTop: 'env(safe-area-inset-top, 0px)' }}
        >
          <button
            onClick={onBack}
            className={`rounded-xl p-2 transition-colors ${isDark ? 'text-white/60 hover:bg-white/[0.06] hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
            aria-label={t('back')}
          >
            <MdArrowBack size={20} />
          </button>
          <button
            onClick={openHistory}
            className={`rounded-xl p-2 transition-colors ${isDark ? 'text-white/60 hover:bg-white/[0.06] hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
            aria-label={t('agentHistory')}
          >
            <MdHistory size={19} />
          </button>
          <h1 className="animate-brand min-w-0 truncate text-base font-bold tracking-normal sm:text-lg">{t('agentTitle')}</h1>
          <select
            value={modelMode}
            onChange={(event) => setModelMode(event.target.value as AgentModelMode)}
            disabled={running}
            aria-label={t('agentModel')}
            title={t('agentModel')}
            className={`ml-auto max-w-28 rounded-lg border px-2 py-1 text-[11px] outline-none disabled:opacity-40 ${isDark ? 'border-white/10 bg-black/40 text-white/70' : 'border-gray-200 bg-white/70 text-gray-600'}`}
          >
            <option value="auto">{t('agentModelAuto')}</option>
            <option value="chat">{t('agentModelChat')}</option>
            <option value="code">{t('agentModelCode')}</option>
            <option value="deep">{t('agentModelDeep')}</option>
            <option value="fast">{t('agentModelFast')}</option>
          </select>
          <button
            onClick={startNewSession}
            className={`rounded-xl p-2 transition-colors ${isDark ? 'text-white/60 hover:bg-white/[0.06] hover:text-white' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-800'}`}
            aria-label={t('agentNewSession')}
            title={t('agentNewSession')}
          >
            <MdAdd size={20} />
          </button>
        </nav>

        {/* Workspace selector */}
        <div className={`flex shrink-0 items-center gap-2 border-b px-3 py-2 text-xs backdrop-blur-xl ${isDark ? 'border-white/[0.06] bg-black/30' : 'border-gray-200 bg-white/40'}`}>
          <button
            onClick={() => setPickerOpen(true)}
            className={`flex shrink-0 items-center gap-1.5 rounded-lg border px-2 py-1 font-medium transition-colors ${isDark ? 'border-white/10 text-white/70 hover:bg-white/[0.06]' : 'border-gray-200 text-gray-600 hover:bg-gray-100'}`}
            title={t('agentPickFolder')}
          >
            <MdFolder size={14} className="text-[#006bbd]" />
            {t('agentPickFolder')}
          </button>
          <input
            aria-label={t('agentWorkspaceRootLabel')}
            value={workspace}
            onChange={(e) => setWorkspace(e.target.value)}
            onBlur={(e) => persistWorkspace(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') { persistWorkspace((e.target as HTMLInputElement).value); (e.target as HTMLInputElement).blur(); } }}
            spellCheck={false}
            className={`min-w-0 flex-1 rounded-md border bg-transparent px-2 py-1 font-mono text-xs outline-none ${isDark ? 'border-white/10 text-white/80 focus:border-[#006bbd]/50' : 'border-gray-200 text-gray-700 focus:border-[#006bbd]/50'}`}
          />
        </div>

        {/* Conversation */}
        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-3 py-4 sm:px-4">
          {turns.length === 0 ? (
            <div className={`flex h-full flex-col items-center justify-center gap-5 px-6 text-center ${subtle}`}>
              <MdSmartToy size={76} className="agent-empty-avatar animate-agent-avatar animate-float" />
              <p className="max-w-sm text-sm leading-relaxed">{t('agentEmptyHint')}</p>
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {turns.map((turn, idx) => (
                <div key={idx} className={`animate-fade-up ${turn.role === 'user' ? 'flex justify-end' : 'flex justify-start'}`}>
                  {turn.role === 'user' ? (
                    editingIndex === idx ? (
                      <div className="flex w-full max-w-[85%] flex-col gap-2">
                        <textarea
                          aria-label={t('saveAndResend')}
                          value={editingText}
                          onChange={(e) => {
                            setEditingText(e.target.value);
                            e.target.style.height = 'auto';
                            e.target.style.height = `${e.target.scrollHeight}px`;
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); saveEdit(); }
                            if (e.key === 'Escape') cancelEdit();
                          }}
                          rows={1}
                          className={`w-full resize-none overflow-hidden rounded-xl border border-[#006bbd]/40 px-3 py-2 text-sm outline-none focus:border-[#006bbd] ${isDark ? 'bg-[#006bbd]/20 text-white' : 'bg-[#006bbd]/10 text-gray-900'}`}
                        />
                        <div className="flex justify-end gap-2">
                          <button onClick={saveEdit} className="rounded-lg bg-[#006bbd] px-2.5 py-1 text-xs font-medium text-white hover:bg-[#0059a0]">{t('saveAndResend')}</button>
                          <button onClick={cancelEdit} className={`rounded-lg px-2.5 py-1 text-xs font-medium ${isDark ? 'bg-white/10 text-white/70 hover:text-white' : 'bg-gray-200 text-gray-700 hover:text-gray-900'}`}>{t('cancel')}</button>
                        </div>
                      </div>
                    ) : (
                      <div className="group flex max-w-[85%] flex-col items-end gap-2">
                        {turn.image && (
                          <img src={turn.image} alt={t('agentAttachImage')} className="max-h-48 w-auto rounded-2xl rounded-br-md border border-white/10 object-cover" width={320} height={192} />
                        )}
                        {turn.documents?.length ? (
                          <div className="flex max-w-full flex-wrap justify-end gap-1.5">
                            {turn.documents.map((document) => (
                              <div key={document.name} className="max-w-64 overflow-hidden rounded-xl bg-[#006bbd]/80 px-2.5 py-2 text-left text-white/90">
                                <div className="flex min-w-0 items-center gap-1.5 text-[11px] font-medium"><MdUploadFile size={14} className="shrink-0" /><span className="truncate">{document.name}</span>{document.truncated && <span className="text-amber-200">{t('truncated')}</span>}</div>
                                {document.preview && <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-[10px] leading-relaxed text-white/65">{document.preview}</p>}
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {turn.content && (
                          <div className="rounded-2xl rounded-br-md bg-[#006bbd] px-4 py-2.5 text-sm text-white">
                            {turn.content}
                          </div>
                        )}
                        <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                          <button
                            onClick={() => startEdit(idx)}
                            disabled={running}
                            className={`rounded-md p-1 transition-colors disabled:opacity-30 ${isDark ? 'text-white/35 hover:bg-white/[0.06] hover:text-white/75' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'}`}
                            title={t('edit')} aria-label={t('edit')}
                          >
                            <MdEdit size={15} />
                          </button>
                          <button
                            onClick={() => copyText(turn.content, `u-${idx}`)}
                            className={`rounded-md p-1 transition-colors ${copiedKey === `u-${idx}` ? 'bg-[#006bbd]/10 text-[#006bbd]' : isDark ? 'text-white/35 hover:bg-white/[0.06] hover:text-white/75' : 'text-gray-500 hover:bg-gray-100 hover:text-gray-700'}`}
                            title={copiedKey === `u-${idx}` ? t('copied') : t('copy')} aria-label={copiedKey === `u-${idx}` ? t('copied') : t('copy')}
                          >
                            {copiedKey === `u-${idx}` ? <MdCheck size={15} /> : <MdContentCopy size={15} />}
                          </button>
                        </div>
                      </div>
                    )
                  ) : (
                    <div className="group w-full min-w-0">
                      {turn.steps?.map((step) => (
                        <AgentStepCard key={step.id} step={step} isDark={isDark} cardBg={cardBg} subtle={subtle} onApprove={approve} t={t} />
                      ))}
                      {turn.content && (
                        <div className="mt-1">
                          {running && idx === turns.length - 1
                            ? <p className="whitespace-pre-wrap text-sm leading-relaxed">{turn.content}</p>
                            : <ChatMarkdown text={turn.content} isDark={isDark} />}
                        </div>
                      )}
                      {running && idx === turns.length - 1 && !turn.content && (!turn.steps || turn.steps.every((s) => s.status === 'done' || s.status === 'denied')) && (
                        <div className={`flex items-center gap-2 text-xs ${subtle}`}>
                          <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#006bbd]" />
                          {analyzingImage ? t('agentAnalyzingImage') : agentActivity || t('agentThinking')}
                        </div>
                      )}
                      {turn.content && !(running && idx === turns.length - 1) && (
                        <div className="mt-1 flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                          <button
                            onClick={() => copyText(turn.content, `a-${idx}`)}
                            className={`rounded-md p-1 transition-colors ${copiedKey === `a-${idx}` ? 'bg-[#006bbd]/10 text-[#006bbd]' : isDark ? 'text-white/30 hover:bg-white/[0.06] hover:text-white/70' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
                            title={copiedKey === `a-${idx}` ? t('copied') : t('copy')} aria-label={copiedKey === `a-${idx}` ? t('copied') : t('copy')}
                          >
                            {copiedKey === `a-${idx}` ? <MdCheck size={15} /> : <MdContentCopy size={15} />}
                          </button>
                          <button
                            onClick={() => regenerate(idx)}
                            disabled={running}
                            className={`rounded-md p-1 transition-colors disabled:opacity-30 ${isDark ? 'text-white/30 hover:bg-white/[0.06] hover:text-white/70' : 'text-gray-400 hover:bg-gray-100 hover:text-gray-600'}`}
                            title={t('regenerate')} aria-label={t('regenerate')}
                          >
                            <MdRefresh size={15} />
                          </button>
                        </div>
                      )}
                      {turn.model && (
                        <p className={`mt-1 font-mono text-[10px] ${subtle}`}>{turn.model}</p>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Composer */}
        <div className={`shrink-0 border-t px-3 py-2.5 backdrop-blur-xl ${isDark ? 'border-white/[0.06] bg-black/40' : 'border-gray-200 bg-white/50'}`} style={{ paddingBottom: 'calc(env(safe-area-inset-bottom, 0px) + 0.625rem)' }}>
          <div className="mx-auto flex w-full max-w-5xl flex-col gap-2 px-2 sm:px-4">
            {attachedImage && (
              <div className="relative inline-block w-max">
                <img src={attachedImage} alt={t('agentAttachImage')} className="h-20 w-auto rounded-lg border border-white/10 object-cover" width={160} height={80} />
                <button
                  onClick={() => { setAttachedImage(null); setImageError(''); }}
                  className="absolute -right-2 -top-2 rounded-full border border-white/20 bg-black/80 p-0.5 text-white/80 hover:text-white"
                  aria-label={t('agentRemoveImage')}
                >
                  <MdClose size={14} />
                </button>
              </div>
            )}
            {attachedDocs.length > 0 && (
              <div className={`grid max-h-44 grid-cols-1 gap-2 overflow-y-auto rounded-xl border p-2 sm:grid-cols-2 ${isDark ? 'border-white/[0.08] bg-white/[0.03]' : 'border-gray-200 bg-gray-50'}`}>
                {attachedDocs.map((document) => (
                  <div key={document.name} className={`min-w-0 rounded-lg px-2.5 py-2 text-[11px] ${isDark ? 'bg-white/[0.06] text-white/60' : 'bg-white text-gray-600'}`}>
                    <div className="flex min-w-0 items-center gap-1.5"><MdUploadFile size={14} className="shrink-0" /><span className="truncate font-medium">{document.name}</span>{document.truncated && <span className="text-amber-400">{t('truncated')}</span>}<button type="button" onClick={() => setAttachedDocs((current) => current.filter((item) => item.name !== document.name))} className="ml-auto shrink-0 text-current/60 hover:text-current" aria-label={t('removeDocument')}><MdClose size={13} /></button></div>
                    <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-[10px] leading-relaxed opacity-70">{document.content.slice(0, 180)}</p>
                  </div>
                ))}
              </div>
            )}
            {imageError && <p className="text-xs text-red-400">{imageError}</p>}

            <input ref={imageInputRef} type="file" accept={IMAGE_FILE_ACCEPT} className="hidden" onChange={onPickImage} />
            <input ref={docInputRef} type="file" accept={DOCUMENT_FILE_ACCEPT} multiple className="hidden" onChange={onPickDocs} />

            <div className="flex items-end gap-1.5 sm:gap-2">
              <motion.div
                layout
                transition={{ layout: { duration: 0.24, ease: [0.16, 1, 0.3, 1] } }}
                className={`flex shrink-0 items-end gap-1.5 sm:flex-row sm:gap-2 ${input.trim() ? 'flex-col-reverse' : 'flex-row'}`}
              >
              {/* Mobile: keep the composer wide by grouping optional tools. */}
              <motion.div layout className="relative shrink-0 sm:hidden">
                <button
                  type="button"
                  onClick={() => setMobileToolsOpen((open) => !open)}
                  disabled={running}
                  className={`flex h-[42px] w-[42px] items-center justify-center rounded-2xl transition-colors ${mobileToolsOpen || knowledgeSearch || webSearch || deepResearch ? 'bg-[#006bbd]/20 text-[#4ea3e0]' : isDark ? 'bg-white/[0.06] text-white/55' : 'bg-gray-100 text-gray-500'}`}
                  aria-label={t('agentTools')}
                  aria-expanded={mobileToolsOpen}
                >
                  {mobileToolsOpen ? <MdExpandLess size={21} /> : <MdExpandMore size={21} />}
                </button>
                <AnimatePresence>
                  {mobileToolsOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 8, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.96 }}
                      className={`absolute bottom-full left-0 z-50 mb-2 w-64 rounded-xl border p-1 shadow-xl ${isDark ? 'border-white/[0.08] bg-[#151515]' : 'border-gray-200 bg-white'}`}
                    >
                      {[
                        { label: t('agentRag'), active: knowledgeSearch, toggle: () => setKnowledgeSearch((value) => !value), Icon: MdStorage },
                        { label: t('agentWebSearch'), active: webSearch, toggle: () => setWebSearch((value) => !value), Icon: MdPublic },
                        { label: t('agentDeepResearch'), active: deepResearch, toggle: () => { setDeepResearch((value) => !value); setWebSearch(true); }, Icon: MdScience },
                      ].map(({ label, active, toggle, Icon }) => (
                        <button key={label} type="button" onClick={toggle} aria-pressed={active} className={`flex w-full items-center gap-3 rounded-lg px-3 py-3 text-left text-sm ${active ? 'bg-[#006bbd]/15 text-[#4ea3e0]' : isDark ? 'text-white/75 hover:bg-white/[0.06]' : 'text-gray-700 hover:bg-gray-100'}`}>
                          <Icon size={19} /><span className="flex-1">{label}</span><span>{active ? '✓' : ''}</span>
                        </button>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
              <div className="hidden items-end gap-2 sm:flex">
              {/* Indexed TrinaxAI knowledge (RAG) toggle */}
              <button
                onClick={() => setKnowledgeSearch((value) => !value)}
                disabled={running}
                className={`flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-2xl transition-colors disabled:opacity-40 ${knowledgeSearch ? 'bg-[#006bbd] text-white' : isDark ? 'bg-white/[0.06] text-white/55 hover:bg-white/[0.1] hover:text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700'}`}
                aria-label={knowledgeSearch ? t('agentRagOn') : t('agentRagOff')}
                title={t('agentRag')}
                aria-pressed={knowledgeSearch}
              >
                <MdStorage size={19} />
              </button>
              {/* Web search toggle */}
              <button
                onClick={() => setWebSearch((v) => !v)}
                disabled={running}
                className={`flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-2xl transition-colors disabled:opacity-40 ${webSearch ? 'bg-[#006bbd] text-white' : isDark ? 'bg-white/[0.06] text-white/55 hover:bg-white/[0.1] hover:text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700'}`}
                aria-label={webSearch ? t('agentWebSearchOn') : t('agentWebSearchOff')}
                title={t('agentWebSearch')}
                aria-pressed={webSearch}
              >
                <MdPublic size={19} />
              </button>
              <button
                onClick={() => { setDeepResearch((value) => !value); setWebSearch(true); }}
                disabled={running}
                className={`flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-2xl transition-colors disabled:opacity-40 ${deepResearch ? 'bg-[#006bbd] text-white' : isDark ? 'bg-white/[0.06] text-white/55 hover:bg-white/[0.1] hover:text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700'}`}
                aria-label={t('agentDeepResearch')}
                title={t('agentDeepResearch')}
                aria-pressed={deepResearch}
              >
                <MdScience size={19} />
              </button>
              </div>
              <motion.div layout ref={attachmentMenuRef} className="relative flex h-[42px] w-[42px] shrink-0 self-end items-center justify-center">
                <button
                  type="button"
                  onClick={() => setAttachmentMenuOpen((open) => !open)}
                  disabled={running}
                  className={`flex h-[42px] w-[42px] items-center justify-center rounded-2xl transition-colors disabled:opacity-40 ${isDark ? 'bg-white/[0.06] text-white/55 hover:bg-white/[0.1] hover:text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700'}`}
                  aria-label={`${t('agentAttachImage')} / ${t('attachDocument')}`}
                  aria-expanded={attachmentMenuOpen}
                >
                  <MdAdd size={20} />
                </button>
                <AnimatePresence>
                  {attachmentMenuOpen && (
                    <motion.div
                      initial={{ opacity: 0, y: 8, scale: 0.96 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 8, scale: 0.96 }}
                      transition={{ duration: 0.16, ease: [0.16, 1, 0.3, 1] }}
                      className={`absolute bottom-full left-0 z-40 mb-2 min-w-44 overflow-hidden rounded-xl border p-1 shadow-xl ${isDark ? 'border-white/[0.08] bg-[#151515]' : 'border-gray-200 bg-white'}`}
                    >
                      <button type="button" onClick={() => { setAttachmentMenuOpen(false); imageInputRef.current?.click(); }} className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}><MdImage size={18} /> {t('agentAttachImage')}</button>
                      <button type="button" onClick={() => { setAttachmentMenuOpen(false); docInputRef.current?.click(); }} className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${isDark ? 'text-white/75 hover:bg-white/[0.08]' : 'text-gray-700 hover:bg-gray-100'}`}><MdUploadFile size={18} /> {t('attachDocument')}</button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
              </motion.div>

              <textarea
                aria-label={placeholder}
                name="agent-prompt"
                autoComplete="off"
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send(); } }}
                placeholder={placeholder}
                rows={1}
                disabled={running}
                className={`max-h-[50dvh] min-h-[42px] min-w-[8rem] flex-1 resize-none overflow-y-auto rounded-2xl border px-3 py-2.5 text-base outline-none transition-colors sm:min-h-[52px] sm:px-4 sm:text-sm ${isDark ? 'border-white/10 bg-white/[0.04] text-white placeholder:text-white/30 focus:border-[#006bbd]/50' : 'border-gray-200 bg-white/70 text-gray-900 placeholder:text-gray-400 focus:border-[#006bbd]/50'}`}
                style={{ maxHeight: '50dvh' }}
              />

              {/* Dictation (speech-to-text) */}
              <AnimatePresence initial={false}>
                {dictationAvailable && !running && (
                  <motion.button
                    type="button"
                    initial={{ opacity: 0, scale: 0.72, width: 0 }} animate={{ opacity: 1, scale: 1, width: 42 }} exit={{ opacity: 0, scale: 0.72, width: 0 }}
                    transition={{ duration: 0.18, ease: [0.16, 1, 0.3, 1] }}
                    onClick={toggleDictation}
                    className={`flex h-[42px] shrink-0 self-end items-center justify-center overflow-hidden rounded-2xl transition-colors ${listening ? 'animate-pulse bg-red-500/30 text-red-400' : isDark ? 'bg-white/[0.06] text-white/55 hover:bg-white/[0.1] hover:text-white' : 'bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700'}`}
                    aria-label={listening ? t('agentExitVoiceMode') : t('agentVoiceMode')}
                    title={listening ? t('agentExitVoiceMode') : t('agentVoiceMode')}
                  >
                    <MdMic size={19} />
                  </motion.button>
                )}
              </AnimatePresence>

              {running ? (
                <button
                  onClick={stop}
                  className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-2xl bg-red-500/90 text-white transition-colors hover:bg-red-500"
                  aria-label={t('agentStop')}
                >
                  <MdStop size={20} />
                </button>
              ) : (
                <button
                  onClick={() => void send()}
                  disabled={!input.trim() && !attachedImage && attachedDocs.length === 0}
                  className="flex h-[42px] w-[42px] shrink-0 self-end items-center justify-center rounded-2xl border border-black/10 bg-white text-black shadow-sm transition-colors hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
                  aria-label={t('agentSend')}
                  title={t('agentSend')}
                >
                  <MdSend size={19} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

interface StepCardProps {
  step: AgentStep;
  isDark: boolean;
  cardBg: string;
  subtle: string;
  onApprove: (step: AgentStep, approved: boolean) => void;
  t: Translate;
}

function AgentStepCard({ step, isDark, cardBg, subtle, onApprove, t }: StepCardProps) {
  const statusIcon = {
    running: <span className="h-2 w-2 animate-pulse rounded-full bg-[#006bbd]" />,
    awaiting: <span className="h-2 w-2 rounded-full bg-amber-400" />,
    done: <MdCheck size={14} className="text-green-500" />,
    denied: <MdClose size={14} className="text-red-500" />,
  }[step.status];

  const summary = argSummary(step.tool, step.args);
  const dangerKey = DANGEROUS_HINT[step.tool];

  return (
    <div className={`mb-1.5 animate-fade-up rounded-xl border px-3 py-2 text-xs ${cardBg}`}>
      <div className="flex items-center gap-2">
        {statusIcon}
        <span className={`font-mono font-semibold ${isDark ? 'text-white/80' : 'text-gray-700'}`}>{step.tool}</span>
        {summary && <span className={`min-w-0 flex-1 truncate font-mono ${subtle}`} title={summary}>{summary}</span>}
      </div>

      {/* Preview for dangerous actions awaiting approval */}
      {step.status === 'awaiting' && (
        <div className="mt-2">
          {step.tool === 'write_file' && (
            <pre className={`mb-2 max-h-40 overflow-auto rounded-lg p-2 font-mono text-[11px] ${isDark ? 'bg-black/40 text-white/70' : 'bg-white text-gray-700'}`}>{(step.args.content ?? '').slice(0, 1200)}</pre>
          )}
          {step.tool === 'edit_file' && (
            <pre className={`mb-2 max-h-40 overflow-auto rounded-lg p-2 font-mono text-[11px] ${isDark ? 'bg-black/40' : 'bg-white'}`}>
              <span className="text-red-400">- {(step.args.old ?? '').slice(0, 400)}</span>{'\n'}
              <span className="text-green-400">+ {(step.args.new ?? '').slice(0, 400)}</span>
            </pre>
          )}
          {step.tool === 'run_command' && (
            <pre className={`mb-2 overflow-auto rounded-lg p-2 font-mono text-[11px] ${isDark ? 'bg-black/40 text-white/70' : 'bg-white text-gray-700'}`}>$ {step.args.command}</pre>
          )}
          <div className="flex items-center gap-2">
            <span className={`flex-1 ${subtle}`}>{dangerKey ? t(dangerKey) : t('agentApprovePrompt')}</span>
            <button
              onClick={() => onApprove(step, false)}
              className={`rounded-lg px-3 py-1 font-medium transition-colors ${isDark ? 'bg-white/[0.06] text-white/70 hover:bg-white/10' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
            >
              {t('agentReject')}
            </button>
            <button
              onClick={() => onApprove(step, true)}
              className="rounded-lg bg-[#006bbd] px-3 py-1 font-medium text-white transition-colors hover:bg-[#0059a0]"
            >
              {t('agentApprove')}
            </button>
          </div>
        </div>
      )}

      {/* Result line for completed / denied steps */}
      {step.result && step.status !== 'awaiting' && (
        <pre className={`mt-1.5 max-h-32 overflow-auto whitespace-pre-wrap break-words font-mono text-[11px] ${subtle}`}>{step.result.slice(0, 800)}</pre>
      )}
    </div>
  );
}
