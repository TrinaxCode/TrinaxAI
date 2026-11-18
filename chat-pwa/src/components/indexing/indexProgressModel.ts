import type { IndexJobStatus } from '../../lib/api_documents';
import { INDEX_UPLOAD_SHARE } from '../../lib/api_documents';

export type IndexStageKey = 'upload' | 'read' | 'split' | 'embed' | 'save';
export type IndexStageStatus = 'done' | 'active' | 'pending';

export interface IndexStage {
  key: IndexStageKey;
  status: IndexStageStatus;
  /** 0..1 when the indexer reports a counter for this stage, null when the stage has none. */
  fraction: number | null;
}

export const INDEX_STAGE_ORDER: IndexStageKey[] = ['upload', 'read', 'split', 'embed', 'save'];

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

/** Which stage the job's current phase belongs to. */
export function activeStageFor(phase: string | undefined, status: string | undefined): IndexStageKey {
  if (status === 'saving' || phase === 'saving') return 'upload';
  switch (phase) {
    case 'extracting':
    case 'queued':
    case 'starting':
      return 'read';
    case 'chunking':
      return 'split';
    case 'embedding':
    case 'indexing':
      return 'embed';
    case 'saving_index':
    case 'finishing':
    case 'completed':
      return 'save';
    default:
      return 'read';
  }
}

/**
 * Per-stage state for the progress rail. Fractions are the indexer's own
 * counters, so a stage only reads "done" once its work really finished; the
 * save stage has no counter and is shown as busy rather than given a number.
 */
export function deriveStages(job: IndexJobStatus | null, uploadProgress: number): IndexStage[] {
  const uploadFraction = job && job.status !== 'saving'
    ? 1
    : clamp01(Math.max(uploadProgress, job?.progress ?? 0) / INDEX_UPLOAD_SHARE);
  const stages = job?.stages;
  // Before the server has a job the only thing happening is the upload.
  const active = job ? activeStageFor(job.phase, job.status) : 'upload';
  const fractions: Record<IndexStageKey, number | null> = {
    upload: uploadFraction,
    read: stages ? clamp01(stages.read) : null,
    split: stages ? clamp01(stages.chunk) : null,
    embed: stages ? clamp01(stages.embed) : null,
    save: job?.status === 'completed' ? 1 : null,
  };
  const finished = job?.status === 'completed';
  const reachedSave = active === 'save';

  return INDEX_STAGE_ORDER.map((key) => {
    const fraction = fractions[key];
    let status: IndexStageStatus;
    if (finished) status = 'done';
    else if (key === 'upload') status = uploadFraction >= 1 ? 'done' : 'active';
    else if (key === 'save') status = reachedSave ? 'active' : 'pending';
    else if (fraction !== null && fraction >= 1) status = 'done';
    // Without counters (older server) the only evidence is the phase: whatever comes before it ran.
    else if (fraction === null && INDEX_STAGE_ORDER.indexOf(key) < INDEX_STAGE_ORDER.indexOf(active)) status = 'done';
    else if (key === active || (fraction !== null && fraction > 0)) status = 'active';
    else status = 'pending';
    return { key, status, fraction };
  });
}

/** `45 s`, `2 min 05 s`, `1 h 05 min`: compact and stable in width while it counts. */
export function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total} s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) return `${minutes} min ${String(total % 60).padStart(2, '0')} s`;
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')} min`;
}

/** Whole-minute ETA: a countdown that changes every second reads as noise. */
export function formatEta(seconds: number): string {
  const total = Math.max(1, Math.round(seconds));
  if (total < 45) return `${Math.ceil(total / 5) * 5} s`;
  if (total < 90) return '1 min';
  const minutes = Math.round(total / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')} min`;
}
