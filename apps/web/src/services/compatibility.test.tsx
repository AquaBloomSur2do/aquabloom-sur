import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ScientificJobDetail } from '../pages/ScientificJobDetail';
import { executionsService } from './executions';
import type {
  JobStatusResponse,
  PointPredictionItem,
  TrainingJobResult,
} from './executions';

const { mockGetJobStatus } = vi.hoisted(() => ({
  mockGetJobStatus: vi.fn(),
}));

vi.mock('./executions', () => ({
  executionsService: {
    getJobStatus: mockGetJobStatus,
  },
}));

vi.mock('../components/Map/BaseMap', () => ({
  default: () => <div data-testid="base-map" />,
}));

type OriginCode = 'synthetic' | 'real' | 'mixed' | 'unknown';

interface OriginInterpretation {
  code: OriginCode;
  label: string;
}

interface ProvenanceSummary {
  modelName: string;
  modelVersionId: string | null;
  trainingJobId: string | null;
  datasetId: string | null;
  datasetVersionId: string | null;
}

const ORIGIN_LABELS: Record<OriginCode, string> = {
  synthetic: 'Sintético',
  real: 'Real',
  mixed: 'Mixto',
  unknown: 'No informado',
};

const STATUS_LABELS: Record<JobStatusResponse['status'], string> = {
  completed: 'Completado',
  failed: 'Fallido',
  running: 'En ejecución',
  queued: 'En cola',
};

const ORIGIN_FLAG_KEYS = [
  'is_synthetic',
  'dataset_is_synthetic',
  'scene_is_synthetic',
];

const sharedResultFixture: JobStatusResponse = {
  job_id: 'job-est-400',
  job_type: 'estimation',
  status: 'completed',
  config: {
    model_id: 'model-version-400',
    scene_id: 'scene-400',
    training_job_id: 'job-train-400',
    dataset_id: 'dataset-400',
    dataset_version_id: 'dataset-version-400',
  },
  result: {
    model_id: 'model-version-400',
    model_name: 'random_forest',
    training_job_id: 'job-train-400',
    dataset_id: 'dataset-400',
    dataset_version_id: 'dataset-version-400',
    unit: 'ug/L',
    status: 'completed',
    is_synthetic: false,
    dataset_is_synthetic: true,
    scene_is_synthetic: false,
    warnings: [
      'El resultado utiliza datos sintéticos y no representa mediciones observacionales reales.',
      'No se dispone de incertidumbre calibrada; el resultado no debe interpretarse como un intervalo de confianza.',
    ],
    predictions: [
      {
        point_id: 'est-01',
        station_name: 'Estación Centro',
        latitude: -38.7359,
        longitude: -72.5904,
        predicted_value: 14.8,
        unit: 'ug/L',
      },
      {
        point_id: 'est-02',
        station_name: 'Estación Norte',
        latitude: -38.6,
        longitude: -72.4,
        predicted_value: 18.2,
        unit: 'ug/L',
      },
    ],
  },
  dataset_version_id: 'dataset-version-400',
  model_version_id: 'model-version-400',
  requested_by: 'user-400',
  error_message: null,
  created_at: '2026-11-27T12:00:00Z',
  started_at: '2026-11-27T12:00:01Z',
  completed_at: '2026-11-27T12:05:00Z',
  updated_at: '2026-11-27T12:05:00Z',
};

function readOriginFlag(
  result: TrainingJobResult,
  key: string
): boolean | undefined {
  const value = result[key];
  return typeof value === 'boolean' ? value : undefined;
}

function classifyOrigin(
  flags: Array<boolean | undefined>
): OriginInterpretation {
  const knownFlags = flags.filter(
    (flag): flag is boolean => typeof flag === 'boolean'
  );
  if (knownFlags.length === 0) {
    return { code: 'unknown', label: ORIGIN_LABELS.unknown };
  }
  const hasSynthetic = knownFlags.some((flag) => flag === true);
  const hasReal = knownFlags.some((flag) => flag === false);
  if (hasSynthetic && hasReal) {
    return { code: 'mixed', label: ORIGIN_LABELS.mixed };
  }
  if (hasSynthetic) {
    return { code: 'synthetic', label: ORIGIN_LABELS.synthetic };
  }
  return { code: 'real', label: ORIGIN_LABELS.real };
}

function resolveWebOrigin(result: TrainingJobResult): OriginInterpretation {
  return classifyOrigin(
    ORIGIN_FLAG_KEYS.map((key) => readOriginFlag(result, key))
  );
}

function resolveMobileOrigin(result: TrainingJobResult): OriginInterpretation {
  return classifyOrigin([
    readOriginFlag(result, 'scene_is_synthetic'),
    readOriginFlag(result, 'dataset_is_synthetic'),
    readOriginFlag(result, 'is_synthetic'),
  ]);
}

function getPointPredictions(
  result: TrainingJobResult
): PointPredictionItem[] {
  if (!Array.isArray(result.predictions)) return [];
  return result.predictions.filter(
    (prediction): prediction is PointPredictionItem =>
      typeof prediction === 'object' && prediction !== null
  );
}

function asStringOrNull(value: unknown): string | null {
  return typeof value === 'string' && value.length > 0 ? value : null;
}

function extractProvenance(
  job: JobStatusResponse,
  result: TrainingJobResult
): ProvenanceSummary {
  return {
    modelName: result.model_name ?? result.model ?? 'Nombre no informado',
    modelVersionId: result.model_id ?? job.model_version_id ?? null,
    trainingJobId:
      result.training_job_id ?? result.model_artifact?.job_id ?? null,
    datasetId:
      result.dataset_id ?? asStringOrNull(job.config?.dataset_id) ?? null,
    datasetVersionId:
      result.dataset_version_id ??
      job.dataset_version_id ??
      asStringOrNull(job.config?.dataset_version_id) ??
      null,
  };
}

function interpretAsWeb(job: JobStatusResponse) {
  const result = job.result ?? {};
  const points = getPointPredictions(result);
  const unit =
    points[0]?.unit?.trim() || result.unit?.trim() || 'Sin unidad';

  return {
    identifier: job.job_id ?? job.id ?? null,
    unit,
    provenance: extractProvenance(job, result),
    origin: resolveWebOrigin(result),
    status: job.status,
    statusLabel: STATUS_LABELS[job.status],
    createdAt: job.created_at,
    completedAt: job.completed_at,
  };
}

function interpretAsMobile(job: JobStatusResponse) {
  const result = job.result ?? {};
  const points = getPointPredictions(result);
  const unit =
    result.unit?.trim() || points[0]?.unit?.trim() || 'Sin unidad';
  const resultStatus = result.status as JobStatusResponse['status'] | undefined;

  return {
    identifier: job.job_id,
    unit,
    provenance: extractProvenance(job, result),
    origin: resolveMobileOrigin(result),
    status: resultStatus ?? job.status,
    statusLabel: STATUS_LABELS[resultStatus ?? job.status],
    createdAt: job.created_at,
    completedAt: job.completed_at,
  };
}

function fixtureWithOriginFlags(
  flags: Record<string, boolean>
): JobStatusResponse {
  const result: TrainingJobResult = { ...(sharedResultFixture.result ?? {}) };
  for (const key of ORIGIN_FLAG_KEYS) {
    delete result[key];
  }
  return {
    ...sharedResultFixture,
    result: { ...result, ...flags },
  };
}

function renderScientificJobDetail() {
  return render(
    <MemoryRouter initialEntries={['/scientific/jobs/job-est-400']}>
      <Routes>
        <Route
          path="/scientific/jobs/:jobId"
          element={<ScientificJobDetail />}
        />
      </Routes>
    </MemoryRouter>
  );
}

describe('Compatibilidad web y móvil del resultado científico (S3-62)', () => {
  beforeEach(() => {
    mockGetJobStatus.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it('interpreta el mismo fixture con la misma unidad, identificador y procedencia en web y móvil', () => {
    const web = interpretAsWeb(sharedResultFixture);
    const mobile = interpretAsMobile(sharedResultFixture);

    expect(web.identifier).toBe('job-est-400');
    expect(mobile.identifier).toBe(web.identifier);

    expect(web.unit).toBe('ug/L');
    expect(mobile.unit).toBe(web.unit);

    expect(web.provenance).toEqual({
      modelName: 'random_forest',
      modelVersionId: 'model-version-400',
      trainingJobId: 'job-train-400',
      datasetId: 'dataset-400',
      datasetVersionId: 'dataset-version-400',
    });
    expect(mobile.provenance).toEqual(web.provenance);

    expect(web.origin).toEqual({ code: 'mixed', label: 'Mixto' });
    expect(mobile.origin).toEqual(web.origin);

    expect(web.statusLabel).toBe('Completado');
    expect(mobile.statusLabel).toBe(web.statusLabel);
    expect(mobile.status).toBe(web.status);

    expect(web.createdAt).toBe('2026-11-27T12:00:00Z');
    expect(mobile.createdAt).toBe(web.createdAt);
    expect(mobile.completedAt).toBe(web.completedAt);
  });

  it.each<[OriginCode, Record<string, boolean>, string]>([
    ['synthetic', { is_synthetic: true }, 'Sintético'],
    ['real', { is_synthetic: false }, 'Real'],
    [
      'mixed',
      { is_synthetic: false, dataset_is_synthetic: true },
      'Mixto',
    ],
    ['unknown', {}, 'No informado'],
  ])(
    'clasifica el origen %s de forma equivalente en web y móvil',
    (code, flags, label) => {
      const fixture = fixtureWithOriginFlags(flags);
      const web = interpretAsWeb(fixture);
      const mobile = interpretAsMobile(fixture);

      expect(web.origin).toEqual({ code, label });
      expect(mobile.origin).toEqual(web.origin);
    }
  );

  it('la vista web renderiza el fixture compartido con la misma unidad, identificador y procedencia', async () => {
    const mobile = interpretAsMobile(sharedResultFixture);
    mockGetJobStatus.mockResolvedValue(sharedResultFixture);

    renderScientificJobDetail();

    expect(
      await screen.findByText(String(mobile.identifier))
    ).toBeInTheDocument();
    expect(screen.getAllByText(mobile.unit)).toHaveLength(2);
    expect(
      screen.getByText(
        `${mobile.provenance.modelName} (${mobile.provenance.modelVersionId})`
      )
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', {
        name: `Ver entrenamiento ${mobile.provenance.trainingJobId}`,
      })
    ).toHaveAttribute(
      'href',
      `/scientific/jobs/${mobile.provenance.trainingJobId}`
    );
    expect(
      screen.getAllByText(String(mobile.provenance.datasetId)).length
    ).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText(String(mobile.provenance.datasetVersionId)).length
    ).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(mobile.statusLabel)).toBeInTheDocument();
    expect(
      screen.getAllByText(/datos sintéticos/i).length
    ).toBeGreaterThanOrEqual(1);

    const syntheticFlag = screen
      .getByText('dataset_is_synthetic')
      .closest('.detail');
    expect(syntheticFlag).toHaveTextContent('true');
    const realFlag = screen.getByText('is_synthetic').closest('.detail');
    expect(realFlag).toHaveTextContent('false');

    expect(executionsService.getJobStatus).toHaveBeenCalledWith(
      'job-est-400',
      expect.any(AbortSignal)
    );
  });
});