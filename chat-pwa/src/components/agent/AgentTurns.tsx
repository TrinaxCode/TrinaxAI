import type { Dispatch, RefObject, SetStateAction } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { MdCheck, MdClose, MdContentCopy, MdEdit, MdRefresh, MdStop, MdUploadFile, MdVolumeUp } from 'react-icons/md';
import type { Translate } from '../chat/types';
import ChatMarkdown from '../chat/ChatMarkdown';
import type { AgentStep, AgentTurn } from './agentTypes';
import '../chat/chat.css';
import '../chat/chat-modern.css';

export interface AgentTurnsProps {
  isDark: boolean;
  t: Translate;
  scrollRef: RefObject<HTMLDivElement | null>;
  turns: AgentTurn[];
  running: boolean;
  agentActivity: string;
  analyzingImage: boolean;
  userDisplayName: string;
  editingIndex: number | null;
  editingText: string;
  setEditingText: Dispatch<SetStateAction<string>>;
  saveEdit: () => void;
  cancelEdit: () => void;
  startEdit: (index: number) => void;
  copyText: (text: string, key: string) => Promise<void>;
  copiedKey: string | null;
  regenerate: (index: number) => void;
  approve: (step: AgentStep, approved: boolean) => void | Promise<void>;
  ttsSupported: boolean;
  ttsActiveKey: string | null;
  speak: (text: string, key: string) => void;
  stopSpeak: () => void;
}

/** Agent turns reuse the chat's row, avatar and bubble language so both modes read the same. */
export default function AgentTurns({
  isDark,
  t,
  scrollRef,
  turns,
  running,
  agentActivity,
  analyzingImage,
  userDisplayName,
  editingIndex,
  editingText,
  setEditingText,
  saveEdit,
  cancelEdit,
  startEdit,
  copyText,
  copiedKey,
  regenerate,
  approve,
  ttsSupported,
  ttsActiveKey,
  speak,
  stopSpeak,
}: AgentTurnsProps) {
  const subtle = isDark ? 'text-white/50' : 'text-gray-500';
  const cardBg = isDark ? 'bg-white/[0.04] border-white/[0.08]' : 'bg-gray-50 border-gray-200';
  const actionButton = `grid h-8 w-8 place-items-center rounded-lg transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] disabled:opacity-30 ${isDark ? 'text-white/60 hover:bg-white/[0.06] hover:text-white' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-800'}`;
  const activeAction = `bg-[#006bbd]/10 ${isDark ? 'text-[#4aa7ed]' : 'text-[#005a9e]'}`;
  const initial = (userDisplayName.trim()[0] || 'U').toUpperCase();

  return (
    <div
      ref={scrollRef}
      data-agent-messages
      className="chat-messages min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-2 py-4 sm:px-4"
      style={{ overscrollBehavior: 'contain', WebkitOverflowScrolling: 'touch' }}
    >
      <div className="flex flex-col gap-4">
        {turns.map((turn, idx) => {
          const last = idx === turns.length - 1;
          const live = running && last;
          if (turn.role === 'user') {
            return (
              <div key={idx} className="chat-row flex w-full min-w-0 max-w-full justify-end gap-2 sm:gap-3">
                {editingIndex === idx ? (
                  <div className="chat-bubble-wrap min-w-0 flex-1">
                    <textarea
                      aria-label={t('saveAndResend')}
                      value={editingText}
                      onChange={(event) => {
                        setEditingText(event.target.value);
                        event.target.style.height = 'auto';
                        event.target.style.height = `${event.target.scrollHeight}px`;
                      }}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); saveEdit(); }
                        if (event.key === 'Escape') cancelEdit();
                      }}
                      rows={1}
                      className={`w-full resize-none overflow-hidden rounded-xl border border-[#006bbd]/40 px-3 py-2 text-base outline-hidden focus:border-[#006bbd] sm:text-sm ${isDark ? 'bg-[#006bbd]/20 text-white' : 'bg-[#006bbd]/10 text-gray-900'}`}
                    />
                    <div className="mt-1 flex gap-2">
                      <button onClick={saveEdit} className="min-h-11 rounded-lg bg-[#006bbd] px-3 text-sm text-white hover:bg-[#0059a0]">{t('saveAndResend')}</button>
                      <button onClick={cancelEdit} className={`min-h-11 rounded-lg px-3 text-sm ${isDark ? 'bg-white/10 text-white/70 hover:text-white' : 'bg-gray-200 text-gray-700 hover:text-gray-900'}`}>{t('cancel')}</button>
                    </div>
                  </div>
                ) : (
                  <div className="chat-bubble-wrap flex min-w-0 flex-col items-end">
                    <div className="chat-bubble group/msg min-w-0 max-w-full rounded-2xl bg-[#006bbd] px-4 py-2.5 text-sm leading-relaxed text-white transition-colors">
                      {turn.image && (
                        <div className="mb-2 flex w-full justify-center">
                          <img src={turn.image} alt={t('agentAttachImage')} className="mx-auto block max-h-52 w-auto max-w-full rounded-lg object-contain" width={320} height={208} />
                        </div>
                      )}
                      {turn.documents?.length ? (
                        <div className="mb-2 flex max-w-full flex-wrap gap-1.5">
                          {turn.documents.map((document) => (
                            <div key={document.name} className="inline-flex min-w-0 max-w-full flex-col rounded-lg bg-white/15 px-2 py-1.5 text-sm text-white/90">
                              <div className="flex min-w-0 items-center gap-1.5"><MdUploadFile size={14} className="shrink-0" /><span className="min-w-0 max-w-48 truncate">{document.name}</span>{document.truncated && <span className="shrink-0 text-amber-200">{t('truncated')}</span>}</div>
                              {document.preview && <p className="mt-1 line-clamp-3 whitespace-pre-wrap text-xs leading-relaxed text-white/75">{document.preview}</p>}
                            </div>
                          ))}
                        </div>
                      ) : null}
                      {turn.content && <p className="chat-plain-text min-w-0 max-w-full whitespace-pre-wrap">{turn.content}</p>}
                    </div>
                    <div className="chat-actions mt-1 flex items-center gap-1">
                      <button onClick={() => startEdit(idx)} disabled={running} className={actionButton} title={t('edit')} aria-label={t('edit')}><MdEdit size={15} /></button>
                      <button
                        onClick={() => copyText(turn.content, `u-${idx}`)}
                        className={`${actionButton} ${copiedKey === `u-${idx}` ? activeAction : ''}`}
                        title={copiedKey === `u-${idx}` ? t('copied') : t('copy')}
                        aria-label={copiedKey === `u-${idx}` ? t('copied') : t('copy')}
                      >
                        {copiedKey === `u-${idx}` ? <MdCheck size={15} /> : <MdContentCopy size={15} />}
                      </button>
                    </div>
                  </div>
                )}
                {editingIndex !== idx && (
                  <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-[#006bbd] text-xs font-semibold text-white" aria-label={t('userAvatar')} title={userDisplayName}>{initial}</div>
                )}
              </div>
            );
          }

          const speakKey = `agent-msg-${idx}`;
          const speaking = ttsActiveKey === speakKey;
          const showActions = Boolean(turn.content) && !live;
          const waitingLabel = analyzingImage ? t('agentAnalyzingImage') : agentActivity || t('agentThinking');
          return (
            <div key={idx} className="chat-row flex w-full min-w-0 max-w-full justify-start gap-2 sm:gap-3">
              <div className={`chat-assistant-avatar mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full p-1 ${isDark ? 'chat-assistant-avatar-dark' : 'chat-assistant-avatar-light'}`}>
                <img src="/logo-for-ai.webp" alt="TrinaxAI" className="h-full w-full rounded-full object-contain" width={28} height={28} draggable={false} />
              </div>
              <div className="chat-bubble-wrap flex min-w-0 flex-1 flex-col items-start">
                {turn.steps?.map((step) => (
                  <AgentStepCard key={step.id} step={step} isDark={isDark} cardBg={cardBg} subtle={subtle} onApprove={approve} t={t} />
                ))}
                {live && !turn.content && (
                  <div className={`chat-bubble chat-bubble-assistant min-w-0 max-w-full overflow-hidden rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${isDark ? 'chat-bubble-assistant-dark' : 'chat-bubble-assistant-light'}`}>
                    <AgentGeneratingIndicator label={waitingLabel} />
                  </div>
                )}
                {turn.content && (
                  <div className={`chat-bubble chat-bubble-assistant min-w-0 max-w-full overflow-hidden rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${live ? 'chat-bubble-streaming' : ''} ${isDark ? 'chat-bubble-assistant-dark' : 'chat-bubble-assistant-light'}`}>
                    {live
                      ? <p className="chat-plain-text min-w-0 max-w-full whitespace-pre-wrap">{turn.content}</p>
                      : <ChatMarkdown text={turn.content} isDark={isDark} />}
                  </div>
                )}
                <div data-completion-status={turn.completionStatus} className="chat-actions mt-1 flex w-full flex-wrap items-center gap-2">
                  {turn.completionStatus && turn.completionStatus !== 'complete' && (
                    <span role="status" className={`text-sm ${turn.completionStatus === 'error' ? isDark ? 'text-red-300' : 'text-red-700' : turn.completionStatus === 'cancelled' ? isDark ? 'text-white/65' : 'text-gray-600' : isDark ? 'text-amber-300' : 'text-amber-800'}`}>
                      {turn.completionStatus === 'cancelled' ? t('requestCancelled') : turn.completionStatus === 'pending' ? t('completionPending') : t('completionError')}
                    </span>
                  )}
                  {showActions && (
                    <>
                      <button
                        onClick={() => copyText(turn.content, `a-${idx}`)}
                        className={`${actionButton} ${copiedKey === `a-${idx}` ? activeAction : ''}`}
                        title={copiedKey === `a-${idx}` ? t('copied') : t('copy')}
                        aria-label={copiedKey === `a-${idx}` ? t('copied') : t('copy')}
                      >
                        {copiedKey === `a-${idx}` ? <MdCheck size={15} /> : <MdContentCopy size={15} />}
                      </button>
                      <button onClick={() => regenerate(idx)} disabled={running} className={actionButton} title={t('regenerate')} aria-label={t('regenerate')}>
                        <MdRefresh size={15} />
                      </button>
                      {ttsSupported && (
                        <button
                          onClick={() => speaking ? stopSpeak() : speak(turn.content, speakKey)}
                          className={`${actionButton} ${speaking ? activeAction : ''}`}
                          title={speaking ? t('stop') : t('listen')}
                          aria-label={speaking ? t('stop') : t('listen')}
                          aria-pressed={speaking}
                        >
                          {speaking ? <MdStop size={15} /> : <MdVolumeUp size={15} />}
                        </button>
                      )}
                    </>
                  )}
                  {turn.model && <span className="chat-model-label">{turn.model}</span>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Same label-plus-dots indicator the chat shows while an answer is being prepared. */
function AgentGeneratingIndicator({ label }: { label: string }) {
  const prefersReducedMotion = useReducedMotion();
  return (
    <div className="chat-generating-indicator" role="status" aria-live="polite" aria-label={label}>
      <span className="chat-generating-label" aria-hidden="true">
        <AnimatePresence initial={false} mode="wait">
          <motion.span
            key={label}
            initial={prefersReducedMotion ? false : { opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            transition={{ duration: prefersReducedMotion ? 0 : 0.24, ease: [0.22, 1, 0.36, 1] }}
          >
            {label}
          </motion.span>
        </AnimatePresence>
      </span>
      <span className="chat-generating-dots" aria-hidden="true">
        {[0, 160, 320].map((delay) => <span key={delay} style={{ animationDelay: `${delay}ms` }} />)}
      </span>
    </div>
  );
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

interface StepCardProps {
  step: AgentStep;
  isDark: boolean;
  cardBg: string;
  subtle: string;
  onApprove: (step: AgentStep, approved: boolean) => void | Promise<void>;
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
    <div className={`tc-agent-step mb-1.5 w-full min-w-0 animate-fade-up rounded-xl border px-3 py-3 text-sm ${cardBg}`}>
      <div className="flex items-center gap-2">
        {statusIcon}
        <span className={`font-mono font-semibold ${isDark ? 'text-white/80' : 'text-gray-700'}`}>{step.tool}</span>
        {summary && <span className={`min-w-0 flex-1 truncate font-mono ${subtle}`} title={summary}>{summary}</span>}
      </div>

      {/* Preview for dangerous actions awaiting approval */}
      {step.status === 'awaiting' && (
        <div className="mt-2">
          {step.tool === 'write_file' && (
            <pre className={`mb-2 max-h-40 overflow-auto rounded-lg p-2 font-mono text-sm leading-relaxed ${isDark ? 'bg-black/40 text-white/80' : 'bg-gray-100 text-gray-800'}`}>{(step.args.content ?? '').slice(0, 1200)}</pre>
          )}
          {step.tool === 'edit_file' && (
            <pre className={`mb-2 max-h-40 overflow-auto rounded-lg p-2 font-mono text-sm leading-relaxed ${isDark ? 'bg-black/40' : 'bg-gray-100'}`}>
              <span className="text-red-400">- {(step.args.old ?? '').slice(0, 400)}</span>{'\n'}
              <span className="text-green-400">+ {(step.args.new ?? '').slice(0, 400)}</span>
            </pre>
          )}
          {step.tool === 'run_command' && (
            <pre className={`mb-2 max-h-40 overflow-auto rounded-lg p-2 font-mono text-sm leading-relaxed ${isDark ? 'bg-black/40 text-white/80' : 'bg-gray-100 text-gray-800'}`}>$ {step.args.command}</pre>
          )}
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <span className={`min-w-0 flex-1 leading-relaxed ${dangerKey ? isDark ? 'text-amber-200' : 'text-amber-800' : subtle}`}>{dangerKey ? t(dangerKey) : t('agentApprovePrompt')}</span>
            <div className="flex w-full gap-2 sm:w-auto">
              <button
                onClick={() => onApprove(step, false)}
                className={`min-h-11 min-w-0 flex-1 rounded-lg px-3 text-sm font-medium transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] sm:flex-none ${isDark ? 'bg-white/[0.06] text-white/80 hover:bg-white/10' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'}`}
              >
                {t('agentReject')}
              </button>
              <button
                onClick={() => onApprove(step, true)}
                className="min-h-11 min-w-0 flex-1 rounded-lg bg-[#006bbd] px-3 text-sm font-medium text-white transition-colors hover:bg-[#0059a0] focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-[#4aa7ed] sm:flex-none"
              >
                {t('agentApprove')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Result line for completed / denied steps */}
      {step.result && step.status !== 'awaiting' && (
        <pre className={`mt-2 max-h-32 overflow-auto whitespace-pre-wrap break-words rounded-lg p-2 font-mono text-sm leading-relaxed ${isDark ? 'bg-black/30 text-white/75' : 'bg-gray-100 text-gray-700'}`}>{step.result.slice(0, 800)}</pre>
      )}
    </div>
  );
}
