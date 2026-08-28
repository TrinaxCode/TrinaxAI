import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useTheme } from '../theme/ThemeContext';
import { useI18n } from '../i18n/I18nContext';
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
  runAgent,
  apiErrorFromPayload,
  userFacingError,
  type AgentEvent,
  type ChatMessage,
} from '../lib/api';
import { useAgentHistory } from './useAgentHistory';
import { useAgentVoice } from './useAgentVoice';
import { useWaitingSound } from './useWaitingSound';
import { audioManager } from '../services/audioManager';
import { streamFlushSize } from './useStreamChat';
import type { AgentInterfaceViewProps } from '../components/agent/AgentInterfaceView';
import {
  AGENT_DOC_MAX_CHARS,
  AGENT_DOC_MAX_FILES,
  AGENT_DOC_TOTAL_MAX_CHARS,
  AGENT_MODEL_KEYS,
  HISTORY_FOCUSABLE,
  type AgentInterfaceProps,
  type AgentModelMode,
  type AgentStep,
  type AgentTurn,
  type AttachedAgentDocument,
} from '../components/agent/agentTypes';

export function useAgentController({
  onBack,
  initialRequest,
  onRequestConsumed,
}: AgentInterfaceProps): AgentInterfaceViewProps {
  const { isDark } = useTheme();
  const { t, lang } = useI18n();
  const isMobile = typeof window !== 'undefined' && window.matchMedia?.('(max-width: 640px)').matches;
  const [turns, setTurns] = useState<AgentTurn[]>([]);
  const [input, setInput] = useState('');
  const [running, setRunning] = useState(false);
  // The waiting cue is a "thinking" sound: it must stop the moment TrinaxAI
  // starts answering (first streamed token), not linger through the whole
  // typewriter render. `running` alone stays true until the turn fully ends.
  const [answering, setAnswering] = useState(false);
  const [agentActivity, setAgentActivity] = useState('');
  const activityPhaseRef = useRef<'start' | 'status' | 'tool' | 'result' | 'writing' | 'done' | 'error'>('start');
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
    try { return localStorage.getItem('tc-agent-web-search') !== '0'; } catch { return true; }
  });
  const [knowledgeSearch, setKnowledgeSearch] = useState<boolean>(() => {
    try { return localStorage.getItem('tc-agent-knowledge-search') !== '0'; } catch { return true; }
  });
  const [deepResearch, setDeepResearch] = useState<boolean>(() => {
    try { return localStorage.getItem('tc-agent-deep-research') !== '0'; } catch { return true; }
  });
  const [yoloMode, setYoloMode] = useState<boolean>(() => {
    try { return localStorage.getItem('tc-agent-yolo-mode') === '1'; } catch { return false; }
  });
  const [yoloConfirmOpen, setYoloConfirmOpen] = useState(false);
  const [mobileToolsOpen, setMobileToolsOpen] = useState(false);
  const [modelMode, setModelMode] = useState<AgentModelMode>(() => {
    try {
      const saved = localStorage.getItem('tc-agent-model-mode');
      return saved && ['auto', 'chat', 'deep', 'fast'].includes(saved)
        ? saved as AgentModelMode
        : 'auto';
    } catch { return 'auto'; }
  });
  const [attachedImage, setAttachedImage] = useState<string | null>(null);
  const [attachedDocs, setAttachedDocs] = useState<AttachedAgentDocument[]>([]);
  const [imageError, setImageError] = useState('');
  const [attachmentMenuOpen, setAttachmentMenuOpen] = useState(false);
  const [analyzingImage, setAnalyzingImage] = useState(false);
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
  const historyDialogRef = useRef<HTMLElement | null>(null);
  const historyCloseButtonRef = useRef<HTMLButtonElement | null>(null);
  const mobileToolsRef = useRef<HTMLDivElement | null>(null);
  const mainContentRef = useRef<HTMLDivElement | null>(null);
  const historyDialogId = useId();
  const historyTitleId = useId();
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const docInputRef = useRef<HTMLInputElement | null>(null);
  const attachmentMenuRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const typewriterQueueRef = useRef('');
  const typewriterTextRef = useRef('');
  const typewriterFrameRef = useRef<number | null>(null);
  const typewriterTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const typewriterWaitersRef = useRef<Array<() => void>>([]);
  const typewriterCancelRef = useRef<() => void>(() => undefined);
  const sawAgentTokenRef = useRef(false);
  const history = useAgentHistory();
  const sessionIdRef = useRef<string | null>(null);

  const { cancelDictation, dictationAvailable, listening, toggleDictation } = useAgentVoice({
    inputRef,
    lang,
    setInput,
    setImageError,
    t,
  });

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
  useEffect(() => { try { localStorage.setItem('tc-agent-yolo-mode', yoloMode ? '1' : '0'); } catch { /* ignore */ } }, [yoloMode]);
  useEffect(() => { try { localStorage.setItem('tc-agent-model-mode', modelMode); } catch { /* ignore */ } }, [modelMode]);

  const handleYoloChange = (enabled: boolean) => {
    if (enabled) setYoloConfirmOpen(true);
    else setYoloMode(false);
  };

  useEffect(() => {
    if (!mobileToolsOpen) return undefined;
    const closeOnOutsideInteraction = (event: PointerEvent) => {
      if (!mobileToolsRef.current?.contains(event.target as Node)) setMobileToolsOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMobileToolsOpen(false);
    };
    document.addEventListener('pointerdown', closeOnOutsideInteraction);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOnOutsideInteraction);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [mobileToolsOpen]);

  useEffect(() => {
    if (running) setMobileToolsOpen(false);
  }, [running]);

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
  }, []);

  // Persist the running conversation to the agent's own history store.
  useEffect(() => {
    if (turns.length === 0) return;
    if (!sessionIdRef.current) sessionIdRef.current = history.newSession(workspace);
    history.saveTurns(sessionIdRef.current, turns, workspace);
    // history functions are stable; depend only on the data that should trigger a save.
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

  const recordAgentActivity = useCallback((message: string) => {
    setAgentActivity(message);
  }, []);

  const phaseMessages: Record<typeof activityPhaseRef.current, string[]> = {
    start: [t('agentStarting'), t('agentUsingModel')],
    status: [t('agentPlanning'), t('agentInspectingWorkspace'), t('agentUsing')],
    tool: [t('agentPreparingTool'), t('agentPlanning'), t('agentUsing')],
    result: [t('agentProcessingToolResult'), t('agentReviewingResult'), t('agentPlanning')],
    writing: [t('agentWritingResponse'), t('agentReviewingResult')],
    done: [t('agentCompleted')],
    error: [t('agentRecoverableError'), t('agentReviewingResult')],
  };

  useEffect(() => {
    if (!running || answering) return undefined;
    const rotate = () => {
      const messages = phaseMessages[activityPhaseRef.current];
      const current = agentActivity;
      const next = messages.find((message) => message !== current) || messages[0];
      setAgentActivity(next);
    };
    const timer = window.setInterval(rotate, 3200);
    return () => window.clearInterval(timer);
  }, [agentActivity, answering, running, t]);

  const handleEvent = useCallback((event: AgentEvent) => {
    switch (event.type) {
      case 'start':
        activityPhaseRef.current = 'start';
        agentRunSessionRef.current = event.session_id;
        setWorkspace(event.workspace);
        recordAgentActivity(t('agentStarting'));
        patchAssistant((turn) => ({ ...turn, model: event.model }));
        break;
      case 'status':
        activityPhaseRef.current = 'status';
        recordAgentActivity(t('agentPlanning'));
        break;
      case 'tool_start':
        activityPhaseRef.current = 'tool';
        recordAgentActivity(t('agentPreparingTool'));
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
        activityPhaseRef.current = 'result';
        recordAgentActivity(t('agentProcessingToolResult'));
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
        activityPhaseRef.current = 'writing';
        setAgentActivity(t('agentWritingResponse'));
        if (!sawAgentTokenRef.current) setAnswering(true);
        sawAgentTokenRef.current = true;
        queueAgentText(event.content);
        break;
      case 'done':
        activityPhaseRef.current = 'done';
        setAgentActivity(event.completion_status === 'cancelled' ? t('requestCancelled') : t('agentCompleted'));
        patchAssistant((turn) => ({
          ...turn,
          completionStatus: event.completion_status || 'complete',
        }));
        // A tool-only turn (no streamed tokens) still stops "thinking" here.
        setAnswering(true);
        if (!sawAgentTokenRef.current) queueAgentText(event.answer);
        break;
      case 'error':
        activityPhaseRef.current = 'error';
        setAgentActivity(t('agentRecoverableError'));
        patchAssistant((turn) => ({ ...turn, completionStatus: event.completion_status || 'error' }));
        queueAgentText(`\n\n${t('errorPrefix')}: ${event.category ? apiErrorFromPayload(500, { error: { category: event.category, code: event.code } }).message : userFacingError(new Error(event.error), 'internal_server_error')}`);
        break;
      default:
        break;
    }
  }, [patchAssistant, queueAgentText, recordAgentActivity, t]);

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
    activityPhaseRef.current = 'start';
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
    setAgentActivity(t('agentStarting'));
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
            const msg = userFacingError(err, 'document_unreadable');
            queueAgentText(`\n\n${t('errorPrefix')}: ${msg}`);
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
      const model = modelMode === 'auto'
        ? 'auto'
        : await resolveAgentModel(modelSetting(AGENT_MODEL_KEYS[modelMode], DEFAULT_MODEL_SETTINGS[AGENT_MODEL_KEYS[modelMode]]));
      const userMessage: ChatMessage = { role: 'user', content: requestText };
      await runAgent([...history, userMessage], handleEvent, {
        workspace,
        model,
        yolo: yoloMode,
        webSearch,
        knowledgeSearch,
        deepResearch,
        signal: controller.signal,
      });
      await waitForAgentTypewriter();
    } catch (err) {
      if (!controller.signal.aborted) {
        const msg = userFacingError(err, 'external_service_unavailable');
        queueAgentText(`\n\n${t('errorPrefix')}: ${msg}`);
        await waitForAgentTypewriter();
      }
    } finally {
      runningRef.current = false;
      setRunning(false);
      setAgentActivity('');
      setAnalyzingImage(false);
      abortRef.current = null;
    }
  }, [turns, workspace, yoloMode, webSearch, knowledgeSearch, deepResearch, modelMode, handleEvent, cancelAgentTypewriter, queueAgentText, waitForAgentTypewriter, t]);

  const send = useCallback(async () => {
    const image = attachedImage;
    const documents = attachedDocs;
    cancelDictation();
    setAttachedImage(null);
    setAttachedDocs([]);
    setImageError('');
    await execute(input, { image, documents });
  }, [execute, input, attachedImage, attachedDocs, cancelDictation]);

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
    patchAssistant((turn) => ({ ...turn, completionStatus: 'cancelled' }));
    runningRef.current = false;
    setRunning(false);
    setAnalyzingImage(false);
    setAgentActivity('');
  }, [cancelAgentTypewriter, patchAssistant]);

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
      setImageError(userFacingError(err, 'document_unreadable'));
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
      setImageError(userFacingError(err, 'document_unreadable'));
    }
  }, [t]);

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

  useEffect(() => {
    if (!historyOpen) return undefined;
    const mainContent = mainContentRef.current;
    const previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const previousInert = mainContent?.inert ?? false;
    const previousAriaHidden = mainContent?.getAttribute('aria-hidden');
    if (mainContent) {
      mainContent.inert = true;
      mainContent.setAttribute('aria-hidden', 'true');
    }
    const focusTimer = window.setTimeout(() => historyCloseButtonRef.current?.focus(), 0);
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeHistory();
        return;
      }
      if (event.key !== 'Tab') return;
      const focusable = historyDialogRef.current?.querySelectorAll<HTMLElement>(HISTORY_FOCUSABLE);
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      window.clearTimeout(focusTimer);
      document.removeEventListener('keydown', handleKeyDown);
      if (mainContent) {
        mainContent.inert = previousInert;
        if (previousAriaHidden === null || previousAriaHidden === undefined) mainContent.removeAttribute('aria-hidden');
        else mainContent.setAttribute('aria-hidden', previousAriaHidden);
      }
      window.requestAnimationFrame(() => previousFocus?.focus());
    };
  }, [closeHistory, historyOpen]);


  return {
    onBack,
    isDark,
    t,
    historyOpen,
    historyClosing,
    historyDialogRef,
    historyDialogId,
    historyTitleId,
    historyCloseButtonRef,
    search,
    setSearch,
    filteredSessions,
    history,
    closeHistory,
    openSession,
    openHistory,
    pickerOpen,
    workspace,
    persistWorkspace,
    setPickerOpen,
    mobileToolsOpen,
    mobileToolsRef,
    mainContentRef,
    setMobileToolsOpen,
    running,
    knowledgeSearch,
    setKnowledgeSearch,
    webSearch,
    setWebSearch,
    deepResearch,
    setDeepResearch,
    yoloMode,
    handleYoloChange,
    modelMode,
    setModelMode,
    startNewSession,
    setWorkspace,
    scrollRef,
    turns,
    setInput,
    inputRef,
    editingIndex,
    editingText,
    setEditingText,
    saveEdit,
    cancelEdit,
    startEdit,
    copyText,
    copiedKey,
    regenerate,
    agentActivity,
    analyzingImage,
    approve,
    attachedImage,
    setAttachedImage,
    attachedDocs,
    setAttachedDocs,
    imageError,
    setImageError,
    imageInputRef,
    onPickImage,
    docInputRef,
    onPickDocs,
    input,
    placeholder,
    attachmentMenuRef,
    attachmentMenuOpen,
    setAttachmentMenuOpen,
    dictationAvailable,
    listening,
    toggleDictation,
    stop,
    send,
    yoloConfirmOpen,
    setYoloMode,
    setYoloConfirmOpen,
  };
}
