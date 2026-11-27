import {
  executionsService,
  type JobStatusResponse,
  type PointPredictionItem,
} from './executions';

export const DEFAULT_ESTIMATION_UNIT = 'µg/L';

export const RN10_WARNING =
  'La clorofila-a es un indicador de biomasa fitoplanctónica y no confirma toxicidad ni constituye una alerta sanitaria.';

export interface EstimationUncertainty {
  calibrated: boolean;
  lower: number | null;
  upper: number | null;
  value: number | null;
  unit: string | null;
  mae: number | null;
  rmse: number | null;
}

export interface EstimationDetail {
  id: string;
  value: number | null;
  unit: string;
  date: string | null;
  status: JobStatusResponse['status'];
  model: string | null;
  modelVersionId: string | null;
  sceneId: string | null;
  sceneIdentifier: string | null;
  acquisitionDate: string | null;
  uncertainty: EstimationUncertainty;
  warnings: string[];
  usageLimits: string[];
  raw: JobStatusResponse;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object'
    ? (value as Record<string, unknown>)
    : null;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function nonEmptyString(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null;
  }
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => (typeof item === 'string' ? item.trim() : ''))
    .filter((item) => item.length > 0);
}

function pointValue(item: PointPredictionItem | number): number | null {
  if (typeof item === 'number') {
    return finiteNumber(item);
  }
  return (
    finiteNumber(item.predicted_value) ??
    finiteNumber(item.prediction_value) ??
    finiteNumber(item.value)
  );
}

function resolveEstimatedValue(
  result: Record<string, unknown>
): number | null {
  const directValue =
    finiteNumber(result.prediction_value) ??
    finiteNumber(result.estimated_value) ??
    finiteNumber(result.value) ??
    finiteNumber(result.chlorophyll_a) ??
    finiteNumber(result.clorofila_a);
  if (directValue !== null) {
    return directValue;
  }

  for (const key of ['points', 'predictions']) {
    const candidates = result[key];
    if (!Array.isArray(candidates)) {
      continue;
    }
    for (const candidate of candidates) {
      const parsed =
        typeof candidate === 'number' || asRecord(candidate)
          ? pointValue(candidate as PointPredictionItem | number)
          : null;
      if (parsed !== null) {
        return parsed;
      }
    }
  }

  return null;
}

function resolveUnit(
  result: Record<string, unknown>,
  unitFallback: string
): string {
  const directUnit = nonEmptyString(result.unit) ?? nonEmptyString(result.unidad);
  if (directUnit) {
    return directUnit;
  }

  for (const key of ['points', 'predictions']) {
    const candidates = result[key];
    if (!Array.isArray(candidates)) {
      continue;
    }
    for (const candidate of candidates) {
      const record = asRecord(candidate);
      const pointUnit = nonEmptyString(record?.unit);
      if (pointUnit) {
        return pointUnit;
      }
    }
  }

  return unitFallback;
}

function resolveUncertainty(
  result: Record<string, unknown>
): EstimationUncertainty {
  const metrics = asRecord(result.metrics);
  const rawUncertainty = result.uncertainty;
  const uncertaintyRecord = asRecord(rawUncertainty);
  const numericUncertainty = finiteNumber(rawUncertainty);

  return {
    calibrated:
      result.uncertainty_calibrated === true ||
      uncertaintyRecord?.calibrated === true,
    lower:
      finiteNumber(uncertaintyRecord?.lower) ??
      finiteNumber(uncertaintyRecord?.lower_bound),
    upper:
      finiteNumber(uncertaintyRecord?.upper) ??
      finiteNumber(uncertaintyRecord?.upper_bound),
    value: numericUncertainty ?? finiteNumber(uncertaintyRecord?.value),
    unit: nonEmptyString(uncertaintyRecord?.unit),
    mae: finiteNumber(metrics?.mae),
    rmse: finiteNumber(metrics?.rmse),
  };
}

export function buildEstimationDetail(
  job: JobStatusResponse
): EstimationDetail {
  const result = asRecord(job.result) ?? {};
  const config = asRecord(job.config) ?? {};

  return {
    id: job.job_id ?? job.id ?? '',
    value: resolveEstimatedValue(result),
    unit: resolveUnit(result, DEFAULT_ESTIMATION_UNIT),
    date: job.completed_at ?? job.updated_at ?? job.created_at ?? null,
    status: job.status,
    model:
      nonEmptyString(result.model) ??
      nonEmptyString(result.model_id) ??
      nonEmptyString(config.model_id) ??
      nonEmptyString(job.model_version_id),
    modelVersionId:
      nonEmptyString(job.model_version_id) ??
      nonEmptyString(result.model_version_id) ??
      nonEmptyString(config.model_id),
    sceneId:
      nonEmptyString(job.scene_id) ?? nonEmptyString(config.scene_id),
    sceneIdentifier: nonEmptyString(result.scene_identifier),
    acquisitionDate: nonEmptyString(result.acquisition_date),
    uncertainty: resolveUncertainty(result),
    warnings: stringList(result.warnings),
    usageLimits: stringList(result.usage_limits),
    raw: job,
  };
}

export const estimationsService = {
  async getEstimationDetail(
    estimationId: string,
    signal?: AbortSignal
  ): Promise<EstimationDetail> {
    const job = await executionsService.getJobStatus(estimationId, signal);
    return buildEstimationDetail(job);
  },
};
