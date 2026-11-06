import { MdCheck } from 'react-icons/md';
import { useI18n } from '../../i18n/I18nContext';
import type { TranslationKey } from '../../i18n/translations';
import type { IndexJobStatus } from '../../lib/api_documents';
import { INDEX_UPLOAD_SHARE } from '../../lib/api_documents';
import { deriveStages, formatDuration, formatEta, type IndexStage, type IndexStageKey } from './indexProgress';
import './index-progress.css';

interface IndexProgressProps {
  job: IndexJobStatus | null;
  /** Upload counter already scaled to the bar (0..INDEX_UPLOAD_SHARE). */
  uploadProgress: number;
  /** Files picked in the browser, shown until the server reports its own total. */
  selectedFiles?: number;
}

const STAGE_LABEL: Record<IndexStageKey, TranslationKey> = {
  upload: 'ipStageUpload',
  read: 'ipStageRead',
  split: 'ipStageSplit',
  embed: 'ipStageEmbed',
  save: 'ipStageSave',
};

const PHASE_TITLE: Record<string, TranslationKey> = {
  saving: 'indexPhaseSaving',
  queued: 'indexPhaseQueued',
  starting: 'indexPhaseStarting',
  extracting: 'indexPhaseExtracting',
  indexing: 'indexPhaseIndexing',
  chunking: 'indexPhaseChunking',
  embedding: 'indexPhaseEmbedding',
  saving_index: 'indexPhaseSavingIndex',
  finishing: 'indexPhaseFinishing',
};

const RING_RADIUS = 15;
const RING_LENGTH = 2 * Math.PI * RING_RADIUS;

function StageRing({ stage, label, statusText }: { stage: IndexStage; label: string; statusText: string }) {
  const known = stage.fraction !== null;
  const shown = stage.status === 'done' ? 1 : stage.fraction ?? 0;
  const busy = stage.status === 'active' && !known;
  const percent = Math.round(shown * 100);
  return (
    <li className="ip-step" data-status={stage.status} aria-label={`${label}: ${statusText}${known && stage.status === 'active' ? ` ${percent}%` : ''}`}>
      <span className="ip-ring" aria-hidden="true">
        <svg viewBox="0 0 36 36" className={`ip-ring-svg${busy ? ' ip-ring-svg--busy' : ''}`}>
          <circle className="ip-ring-track" cx="18" cy="18" r={RING_RADIUS} />
          <circle
            className="ip-ring-value"
            cx="18"
            cy="18"
            r={RING_RADIUS}
            strokeDasharray={RING_LENGTH}
            strokeDashoffset={busy ? RING_LENGTH * 0.72 : RING_LENGTH * (1 - shown)}
          />
        </svg>
        <span className="ip-ring-center">
          {stage.status === 'done' ? <MdCheck size={16} /> : known && stage.status === 'active' ? <span className="ip-ring-percent">{percent}</span> : <span className="ip-ring-dot" />}
        </span>
      </span>
      <span className="ip-step-label">{label}</span>
    </li>
  );
}

export default function IndexProgress({ job, uploadProgress, selectedFiles = 0 }: IndexProgressProps) {
  const { t } = useI18n();
  const progress = Math.min(100, Math.max(0, uploadProgress, job?.progress ?? 0));
  const exact = job ? Boolean(job.progress_exact) : true;
  const stages = deriveStages(job, uploadProgress);
  const activeStage = stages.find((stage) => stage.status === 'active') ?? stages[stages.length - 1];
  const phase = job?.phase || (uploadProgress > 0 || !job ? 'saving' : 'queued');
  const title = t(PHASE_TITLE[phase] ?? 'indexPhaseIndexing');
  const eta = typeof job?.eta_seconds === 'number' && job.eta_seconds > 0 ? job.eta_seconds : null;
  const measuring = job?.status === 'indexing' && eta === null && progress < 96;
  const filesTotal = job?.files_total || selectedFiles || job?.saved || 0;
  const filesDone = job?.files_processed || 0;
  const stageNumber = stages.findIndex((stage) => stage.key === activeStage.key) + 1;
  const statusText: Record<IndexStage['status'], string> = {
    done: t('ipStageDone'),
    active: t('ipStageActive'),
    pending: t('ipStagePending'),
  };

  return (
    <div className="ip-card" data-phase={phase}>
      <div className="ip-head">
        <div className="ip-title">
          <span className="ip-pulse" aria-hidden="true" />
          <div className="min-w-0">
            <p className="ip-title-text">{title}</p>
            <p className="ip-subtitle" title={job?.current_file || undefined}>
              {job?.current_file ? job.current_file : `${t('ipStepOf').replace('{n}', String(stageNumber)).replace('{total}', String(stages.length))}`}
            </p>
          </div>
        </div>
        <div className="ip-figure">
          <span className="ip-percent">{progress}<span className="ip-percent-sign">%</span></span>
          <span className="ip-eta" aria-live="off">
            {!exact && <span className="ip-approx">{t('indexApprox')}</span>}
            {eta !== null ? t('ipEtaLeft').replace('{time}', formatEta(eta)) : measuring ? t('indexEtaCalculating') : ''}
          </span>
        </div>
      </div>

      <div
        className="ip-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        aria-valuetext={`${progress}%${exact ? '' : ` ${t('indexApprox')}`} · ${title}`}
        aria-label={t('ipOverall')}
      >
        <div className={`ip-fill${exact ? '' : ' ip-fill--estimating'}`} style={{ width: `${progress}%` }} />
        <span className="ip-track-mark" style={{ left: `${INDEX_UPLOAD_SHARE}%` }} aria-hidden="true" />
      </div>

      <ol className="ip-rail" aria-label={t('ipStages')}>
        {stages.map((stage) => (
          <StageRing key={stage.key} stage={stage} label={t(STAGE_LABEL[stage.key])} statusText={statusText[stage.status]} />
        ))}
      </ol>

      <dl className="ip-stats">
        <div className="ip-stat">
          <dt>{t('indexFiles')}</dt>
          <dd>{filesDone}<span className="ip-stat-of"> / {filesTotal}</span></dd>
        </div>
        {!!job?.chunks_generated && (
          <div className="ip-stat">
            <dt>{t('indexChunks')}</dt>
            <dd>{job.chunks_generated.toLocaleString()}</dd>
          </div>
        )}
        {!!job?.pages_total && (
          <div className="ip-stat">
            <dt>{t('indexPages')}</dt>
            <dd>{job.pages_processed}<span className="ip-stat-of"> / {job.pages_total}</span></dd>
          </div>
        )}
        {!!job?.skipped && (
          <div className="ip-stat ip-stat--warn">
            <dt>{t('indexSkipped')}</dt>
            <dd>{job.skipped}</dd>
          </div>
        )}
        <div className="ip-stat">
          <dt>{t('indexElapsed')}</dt>
          <dd>{formatDuration(job?.elapsed_seconds ?? 0)}</dd>
        </div>
      </dl>

      {/* Announced in steps of ten so a screen reader is not read every poll. */}
      <span className="sr-only" role="status" aria-live="polite">{`${title}. ${Math.floor(progress / 10) * 10}%`}</span>
    </div>
  );
}
