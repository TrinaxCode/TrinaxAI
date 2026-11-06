import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { I18nProvider } from '../../i18n/I18nContext';
import type { IndexJobStatus } from '../../lib/api_documents';
import IndexProgress from './IndexProgress';
import { activeStageFor, deriveStages, formatDuration, formatEta } from './indexProgress';

const baseJob: IndexJobStatus = {
  id: 'job',
  label: 'Docs',
  path: '/docs',
  status: 'indexing',
  phase: 'embedding',
  progress: 55,
  eta_seconds: 300,
  elapsed_seconds: 125,
  saved: 40,
  skipped: 0,
  bytes: 0,
  indexed: false,
  projects: [],
  pages_total: null,
  pages_processed: 0,
  files_total: 40,
  files_processed: 40,
  chunks_generated: 1234,
  batches_total: 8,
  batches_processed: 3,
  progress_exact: true,
  stages: { read: 1, chunk: 1, embed: 0.4 },
  current_file: 'notes/plan.md',
  failures: [],
  retry_recommended: false,
};

function renderProgress(job: IndexJobStatus | null, uploadProgress = 0, selectedFiles = 0) {
  return render(
    <I18nProvider>
      <IndexProgress job={job} uploadProgress={uploadProgress} selectedFiles={selectedFiles} />
    </I18nProvider>,
  );
}

describe('IndexProgress', () => {
  it('shows the overall percentage, the file being processed and the measured ETA', () => {
    const { container } = renderProgress(baseJob);

    const bar = screen.getByRole('progressbar');
    expect(bar).toHaveAttribute('aria-valuenow', '55');
    expect(container.querySelector('.ip-percent')).toHaveTextContent('55%');
    expect(container.querySelector('.ip-fill')).toHaveStyle({ width: '55%' });
    expect(screen.getByText('notes/plan.md')).toBeInTheDocument();
    expect(screen.getByText(/~5 min/)).toBeInTheDocument();
    expect(screen.getByText('1,234')).toBeInTheDocument();
  });

  it('renders one ring per stage with the counters the indexer reported', () => {
    const { container } = renderProgress(baseJob);
    const steps = Array.from(container.querySelectorAll('.ip-step'));

    expect(steps.map((step) => step.getAttribute('data-status'))).toEqual(['done', 'done', 'done', 'active', 'pending']);
    // The embedding ring shows its own 40%, not the overall figure.
    expect(steps[3].querySelector('.ip-ring-percent')).toHaveTextContent('40');
  });

  it('asks for patience instead of inventing an ETA before the pace is known', () => {
    renderProgress({ ...baseJob, eta_seconds: null });
    expect(screen.getByText(/calculando|calculating/i)).toBeInTheDocument();
    expect(screen.queryByText(/~\d/)).toBeNull();
  });

  it('flags a provisional percentage', () => {
    const { container } = renderProgress({ ...baseJob, progress_exact: false });
    expect(container.querySelector('.ip-fill')).toHaveClass('ip-fill--estimating');
    expect(screen.getByText(/aprox|approx/i)).toBeInTheDocument();
  });

  it('keeps the bar inside 0..100 whatever the server reports', () => {
    const { container, rerender } = renderProgress({ ...baseJob, progress: 180 });
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100');
    rerender(
      <I18nProvider>
        <IndexProgress job={{ ...baseJob, progress: -5 }} uploadProgress={0} />
      </I18nProvider>,
    );
    expect(container.querySelector('.ip-percent')).toHaveTextContent('0%');
  });

  it('follows the upload before the server has a job', () => {
    const { container } = renderProgress(null, 4, 12);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '4');
    const steps = Array.from(container.querySelectorAll('.ip-step'));
    expect(steps[0]).toHaveAttribute('data-status', 'active');
    expect(steps[1]).toHaveAttribute('data-status', 'pending');
    // The picked folder's size stands in until the indexer reports its total.
    expect(container.querySelector('.ip-stats')).toHaveTextContent('0 / 12');
  });

  it('warns about skipped files without hiding the progress', () => {
    const { container } = renderProgress({ ...baseJob, skipped: 3 });
    expect(container.querySelector('.ip-stat--warn')).toHaveTextContent('3');
  });
});

describe('index stage derivation', () => {
  it('maps every backend phase to a stage', () => {
    expect(activeStageFor('saving', 'saving')).toBe('upload');
    expect(activeStageFor('queued', 'indexing')).toBe('read');
    expect(activeStageFor('extracting', 'indexing')).toBe('read');
    expect(activeStageFor('chunking', 'indexing')).toBe('split');
    expect(activeStageFor('embedding', 'indexing')).toBe('embed');
    expect(activeStageFor('saving_index', 'indexing')).toBe('save');
    expect(activeStageFor('finishing', 'indexing')).toBe('save');
  });

  it('treats a stage as done only when its counter reached the total', () => {
    const stages = deriveStages({ ...baseJob, phase: 'extracting', stages: { read: 0.6, chunk: 0.1, embed: 0 } }, 0);
    expect(stages.map((stage) => stage.status)).toEqual(['done', 'active', 'active', 'pending', 'pending']);
  });

  it('shows the save stage as busy, without a made-up fraction', () => {
    const stages = deriveStages({ ...baseJob, phase: 'saving_index', stages: { read: 1, chunk: 1, embed: 1 } }, 0);
    const save = stages[4];
    expect(save.status).toBe('active');
    expect(save.fraction).toBeNull();
  });

  it('marks every stage done once the job completed', () => {
    const stages = deriveStages({ ...baseJob, status: 'completed', phase: 'completed' }, 0);
    expect(stages.every((stage) => stage.status === 'done')).toBe(true);
  });

  it('works for a job from an older server that reports no stage counters', () => {
    const stages = deriveStages({ ...baseJob, stages: undefined, phase: 'chunking' }, 0);
    expect(stages.map((stage) => stage.status)).toEqual(['done', 'done', 'active', 'pending', 'pending']);
    expect(stages[2].fraction).toBeNull();
  });
});

describe('duration formatting', () => {
  it('formats elapsed time compactly', () => {
    expect(formatDuration(0)).toBe('0 s');
    expect(formatDuration(59.6)).toBe('1 min 00 s');
    expect(formatDuration(97)).toBe('1 min 37 s');
    expect(formatDuration(3900)).toBe('1 h 05 min');
  });

  it('rounds the ETA so the countdown does not flicker', () => {
    expect(formatEta(3)).toBe('5 s');
    expect(formatEta(44)).toBe('45 s');
    expect(formatEta(70)).toBe('1 min');
    expect(formatEta(125)).toBe('2 min');
    expect(formatEta(5400)).toBe('1 h 30 min');
  });
});
