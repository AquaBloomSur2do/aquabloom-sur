import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import type { FeatureCollection, Geometry } from 'geojson';
import BaseMap from '../components/Map/BaseMap';
import { ApiError } from '../services/apiClient';
import { executionsService } from '../services/executions';
import type {
  JobStatusResponse,
  PointPredictionItem,
  TrainingJobResult,
} from '../services/executions';
import {
  buildEstimationDetail,
  DEFAULT_ESTIMATION_UNIT,
  RN10_WARNING,
  type EstimationDetail,
} from '../services/estimations';

const DEFAULT_POLL_INTERVAL_MS = 1500;
const MAX_POLL_ATTEMPTS = 40;

const statusPresentation: Record<
  JobStatusResponse['status'],
  { className: string; label: string; icon: string }
> = {
  completed: { className: 'badge validated', label: 'Completado', icon: '✓' },
  failed: { className: 'badge reported', label: 'Fallido', icon: '!' },
  running: { className: 'badge restricted', label: 'En ejecución', icon: '↻' },
  queued: { className: 'badge draft', label: 'En cola', icon: '•' },
};

interface ScientificJobDetailProps {
  pollIntervalMs?: number;
}

function isInProgressStatus(status: JobStatusResponse['status']): boolean {
  return status === 'queued' || status === 'running';
}

function resolveDatasetVersionId(job: JobStatusResponse): string | null {
  if (job.dataset_version_id) return job.dataset_version_id;
  const configVersionId = job.config?.version_id;
  return typeof configVersionId === 'string' && configVersionId.trim()
    ? configVersionId
    : null;
}

const STRUCTURED_RESULT_KEYS = new Set([
  'model',
  'baseline',
  'prediction_value',
  'predictions',
  'metrics',
  'version',
  'dataset_version_id',
  'model_version_id',
  'status',
  'warnings',
  'usage_limits',
  'unit',
  'unidad',
  'uncertainty',
  'uncertainty_calibrated',
  'point_count',
  'points',
  'model_id',
  'artifact_checksum',
  'message',
  'estimated_value',
  'value',
  'chlorophyll_a',
  'clorofila_a',
  'acquisition_date',
  'scene_identifier',
]);

function displayValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value) ?? String(value);
}

function formatMetric(value: number | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'No disponible';
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(4);
}

function formatSampleCount(value: number | undefined): string {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0
    ? String(value)
    : 'No disponible';
}

function normalizeWarnings(warnings: string[] | undefined): string[] {
  if (!Array.isArray(warnings)) {
    return [];
  }
  return warnings
    .map((warning) => warning.trim())
    .filter((warning) => warning.length > 0);
}

function formatPointValue(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return 'No disponible';
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(4);
}

function formatEstimationValue(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return 'No disponible';
  }
  return String(Number(value.toFixed(4)));
}

function formatDateTimeValue(value: string | null | undefined): string {
  if (!value) {
    return 'No disponible';
  }
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? 'No disponible' : parsed.toLocaleString();
}

function estimationValueLabel(estimation: EstimationDetail): string {
  if (estimation.value !== null) {
    return `${formatEstimationValue(estimation.value)} ${estimation.unit}`;
  }
  if (estimation.status === 'queued' || estimation.status === 'running') {
    return 'Pendiente de cálculo';
  }
  if (estimation.status === 'failed') {
    return 'No disponible por fallo del trabajo';
  }
  return 'No disponible';
}

function formatUncertainty(estimation: EstimationDetail): string {
  const { uncertainty, unit } = estimation;
  const uncertaintyUnit = uncertainty.unit ?? unit;

  if (uncertainty.lower !== null && uncertainty.upper !== null) {
    return `Intervalo ${formatEstimationValue(
      uncertainty.lower
    )} – ${formatEstimationValue(uncertainty.upper)} ${uncertaintyUnit}${
      uncertainty.calibrated ? ' (calibrada)' : ' (no calibrada)'
    }`;
  }

  if (uncertainty.value !== null) {
    return `± ${formatEstimationValue(uncertainty.value)} ${uncertaintyUnit}${
      uncertainty.calibrated ? ' (calibrada)' : ' (no calibrada)'
    }`;
  }

  if (uncertainty.mae !== null || uncertainty.rmse !== null) {
    const metricParts = [
      uncertainty.mae !== null
        ? `MAE ${formatEstimationValue(uncertainty.mae)} ${uncertaintyUnit}`
        : null,
      uncertainty.rmse !== null
        ? `RMSE ${formatEstimationValue(uncertainty.rmse)} ${uncertaintyUnit}`
        : null,
    ].filter((part): part is string => part !== null);
    return `Error del modelo: ${metricParts.join(', ')}. No es un intervalo de confianza calibrado.`;
  }

  return 'No informada por la API. El resultado no incluye un intervalo de confianza calibrado.';
}

function resolveLoadErrorMessage(
  error: unknown,
  isEstimation: boolean
): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Tu sesión expiró o no es válida. Inicia sesión nuevamente.';
    }
    if (error.status === 403) {
      return isEstimation
        ? 'No tienes permisos para consultar esta estimación.'
        : 'No tienes permisos para consultar este trabajo.';
    }
    if (error.status === 404) {
      return isEstimation
        ? 'No se encontró la estimación solicitada o no pertenece a tu organización.'
        : 'No se encontró el trabajo solicitado o no pertenece a tu organización.';
    }
    if (error.status === 422) {
      return isEstimation
        ? 'El identificador de la estimación no es válido.'
        : 'El identificador del trabajo no es válido.';
    }
    if (error.status === 503) {
      return isEstimation
        ? 'El servicio de estimaciones no está disponible. Intenta nuevamente en unos segundos.'
        : 'El servicio de trabajos científicos no está disponible. Intenta nuevamente en unos segundos.';
    }
    if (error.isNetworkError) {
      return 'No se pudo conectar con la API. Revisa tu conexión e inténtalo nuevamente.';
    }
    return error.message;
  }

  return error instanceof Error
    ? error.message
    : isEstimation
      ? 'No se pudo cargar el detalle de la estimación.'
      : 'No se pudo cargar el detalle del trabajo.';
}

function resolveCorrelationId(error: unknown): string | null {
  return error instanceof ApiError && error.correlationId
    ? error.correlationId
    : null;
}

function isPointPredictionList(
  predictions: number[] | PointPredictionItem[] | undefined
): predictions is PointPredictionItem[] {
  return (
    Array.isArray(predictions) &&
    predictions.some(
      (prediction) => typeof prediction === 'object' && prediction !== null
    )
  );
}

function isStructuredTrainingResult(result: TrainingJobResult): boolean {
  if (isPointPredictionList(result.predictions)) {
    return false;
  }
  const normalizedWarnings = normalizeWarnings(result.warnings);
  return Boolean(
    result.metrics ||
      result.model ||
      result.baseline ||
      result.version ||
      result.model_version_id ||
      result.dataset_version_id ||
      normalizedWarnings.length > 0
  );
}

function formatCoordinates(
  latitude: number | null | undefined,
  longitude: number | null | undefined
): string | null {
  if (
    typeof latitude !== 'number' ||
    !Number.isFinite(latitude) ||
    typeof longitude !== 'number' ||
    !Number.isFinite(longitude)
  ) {
    return null;
  }
  return `${latitude}, ${longitude}`;
}

function hasValidCoordinates(
  prediction: PointPredictionItem
): prediction is PointPredictionItem & {
  latitude: number;
  longitude: number;
} {
  return (
    typeof prediction.latitude === 'number' &&
    Number.isFinite(prediction.latitude) &&
    prediction.latitude >= -90 &&
    prediction.latitude <= 90 &&
    typeof prediction.longitude === 'number' &&
    Number.isFinite(prediction.longitude) &&
    prediction.longitude >= -180 &&
    prediction.longitude <= 180
  );
}

function getExperimentalCondition(result: TrainingJobResult): string {
  const normalizedWarnings = normalizeWarnings(result.warnings);
  if (normalizedWarnings.length > 0) {
    return 'Resultado piloto preliminar.';
  }
  return result.model === 'baseline'
    ? 'Modelo piloto preliminar basado en un baseline de referencia.'
    : 'Resultado piloto preliminar.';
}

export function ScientificJobDetail({
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
}: ScientificJobDetailProps) {
  const { jobId } = useParams<{ jobId: string }>();
  const { pathname } = useLocation();
  const isEstimationRoute = pathname.startsWith('/estimations');
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorCorrelationId, setErrorCorrelationId] = useState<string | null>(
    null
  );

  useEffect(() => {
    if (!jobId) return;

    let active = true;
    let activeController = new AbortController();
    let pollTimer: number | null = null;
    let pollAttempts = 0;

    const loadJob = async (isInitialLoad: boolean) => {
      if (!active) return;
      pollAttempts += 1;

      if (isInitialLoad) {
        setLoading(true);
        setError(null);
        setErrorCorrelationId(null);
      }

      activeController = new AbortController();

      try {
        const response = await executionsService.getJobStatus(
          jobId,
          activeController.signal
        );
        if (!active) return;

        setJob(response);
        setError(null);
        setErrorCorrelationId(null);

        if (isInProgressStatus(response.status)) {
          if (pollAttempts >= MAX_POLL_ATTEMPTS) {
            setError(
              'El sondeo automático se detuvo después de 40 consultas. Vuelve a cargar la vista para consultar el estado actualizado.'
            );
            return;
          }

          pollTimer = window.setTimeout(() => {
            void loadJob(false);
          }, pollIntervalMs);
        }
      } catch (loadError) {
        if (active && !activeController.signal.aborted) {
          setError(resolveLoadErrorMessage(loadError, isEstimationRoute));
          setErrorCorrelationId(resolveCorrelationId(loadError));
        }
      } finally {
        if (active && isInitialLoad) {
          setLoading(false);
        }
      }
    };

    void loadJob(true);
    return () => {
      active = false;
      activeController.abort();
      if (pollTimer !== null) {
        window.clearTimeout(pollTimer);
      }
    };
  }, [jobId, pollIntervalMs, isEstimationRoute]);

  const isEstimationView = job
    ? job.job_type === 'estimation'
    : isEstimationRoute;
  const estimation = useMemo(
    () => (job && job.job_type === 'estimation' ? buildEstimationDetail(job) : null),
    [job]
  );
  const resolvedDatasetVersionId = job ? resolveDatasetVersionId(job) : null;

  const extraResultEntries = job?.result
    ? Object.entries(job.result).filter(
        ([key]) => !STRUCTURED_RESULT_KEYS.has(key)
      )
    : [];
  const normalizedWarnings = normalizeWarnings(job?.result?.warnings);
  const baselinePrediction =
    job?.result?.baseline?.prediction_value ?? job?.result?.prediction_value;
  const pointPredictionSource =
    job?.result?.points ?? job?.result?.predictions;
  const pointPredictions = useMemo(
    () =>
      isPointPredictionList(pointPredictionSource)
        ? pointPredictionSource.filter(
            (prediction): prediction is PointPredictionItem =>
              typeof prediction === 'object' && prediction !== null
          )
        : [],
    [pointPredictionSource]
  );
  const mappedPredictions = useMemo(
    () => pointPredictions.filter(hasValidCoordinates),
    [pointPredictions]
  );
  const pointGeometries = useMemo<FeatureCollection<Geometry> | null>(() => {
    if (mappedPredictions.length === 0) return null;
    return {
      type: 'FeatureCollection',
      features: mappedPredictions.map((prediction) => ({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [prediction.longitude, prediction.latitude],
        },
        properties: {
          point_id: prediction.point_id ?? null,
          station_name:
            prediction.station_name ?? prediction.station_code ?? null,
        },
      })),
    };
  }, [mappedPredictions]);
  const mapCenter = useMemo<[number, number] | null>(() => {
    if (mappedPredictions.length === 0) return null;
    const coordinateTotals = mappedPredictions.reduce(
      (totals, prediction) => ({
        longitude: totals.longitude + prediction.longitude,
        latitude: totals.latitude + prediction.latitude,
      }),
      { longitude: 0, latitude: 0 }
    );
    return [
      coordinateTotals.longitude / mappedPredictions.length,
      coordinateTotals.latitude / mappedPredictions.length,
    ];
  }, [mappedPredictions]);
  const mapZoom = useMemo(() => {
    if (mappedPredictions.length < 2) return 12;
    const bounds = mappedPredictions.reduce(
      (current, prediction) => ({
        minLatitude: Math.min(current.minLatitude, prediction.latitude),
        maxLatitude: Math.max(current.maxLatitude, prediction.latitude),
        minLongitude: Math.min(current.minLongitude, prediction.longitude),
        maxLongitude: Math.max(current.maxLongitude, prediction.longitude),
      }),
      {
        minLatitude: mappedPredictions[0].latitude,
        maxLatitude: mappedPredictions[0].latitude,
        minLongitude: mappedPredictions[0].longitude,
        maxLongitude: mappedPredictions[0].longitude,
      }
    );
    const span = Math.max(
      bounds.maxLatitude - bounds.minLatitude,
      bounds.maxLongitude - bounds.minLongitude
    );
    return span === 0
      ? 12
      : Math.max(3, Math.min(12, Math.floor(Math.log2(360 / span)) - 1));
  }, [mappedPredictions]);

  const resolvedVersion =
    job?.result?.version ??
    job?.result?.model_version_id ??
    job?.result?.dataset_version_id ??
    job?.model_version_id ??
    job?.dataset_version_id;

  const resultStatusKey = job?.result?.status as
    JobStatusResponse['status'] | undefined;
  const resultStatusLabel =
    resultStatusKey && resultStatusKey in statusPresentation
      ? statusPresentation[resultStatusKey].label
      : (job?.result?.status ??
        statusPresentation[job?.status ?? 'queued'].label);

  return (
    <div className="content-container">
      <header className="page-head">
        <div>
          <span className="eyebrow">Trazabilidad científica</span>
          <h1>
            {isEstimationView ? 'Detalle de la estimación' : 'Detalle del experimento'}
          </h1>
          <p className="subtitle">
            {isEstimationView ? 'Estimación' : 'Trabajo'} {jobId ?? 'no identificado'}
          </p>
        </div>
        <Link to="/lakes" className="btn btn-secondary">
          Volver a lagos
        </Link>
      </header>

      {!jobId ? (
        <div className="status-banner danger" role="alert">
          {isEstimationView
            ? 'No se indicó el identificador de la estimación.'
            : 'No se indicó el identificador del trabajo.'}
        </div>
      ) : loading ? (
        <p role="status">
          {isEstimationView
            ? 'Cargando detalle de la estimación...'
            : 'Cargando detalle del trabajo...'}
        </p>
      ) : error && !job ? (
        <div className="status-banner danger" role="alert">
          <span>{error}</span>
          {errorCorrelationId && (
            <span className="card-note">
              Referencia de correlación: {errorCorrelationId}
            </span>
          )}
        </div>
      ) : job ? (
        <main className="grid">
          {error && (
            <div className="status-banner danger detail-full" role="alert">
              <span>{error}</span>
              {errorCorrelationId && (
                <span className="card-note">
                  Referencia de correlación: {errorCorrelationId}
                </span>
              )}
            </div>
          )}

          {estimation && (
            <section className="card" aria-labelledby="estimation-summary-heading">
              <div className="card-head">
                <h2 id="estimation-summary-heading">Resumen de la estimación</h2>
                <span className={statusPresentation[estimation.status].className}>
                  <span aria-hidden="true">
                    {statusPresentation[estimation.status].icon}
                  </span>{' '}
                  {statusPresentation[estimation.status].label}
                </span>
              </div>
              <div className="card-body grid">
                <div className="detail">
                  <span>Valor estimado</span>
                  <b>{estimationValueLabel(estimation)}</b>
                </div>
                <div className="detail">
                  <span>Unidad</span>
                  <b>{estimation.unit}</b>
                </div>
                <div className="detail">
                  <span>Fecha de estimación</span>
                  <b>{formatDateTimeValue(estimation.date)}</b>
                </div>
                <div className="detail">
                  <span>Estado</span>
                  <b>{statusPresentation[estimation.status].label}</b>
                </div>
                <div className="detail">
                  <span>Modelo</span>
                  <b>{estimation.model ?? 'No informado por la API'}</b>
                </div>
                <div className="detail">
                  <span>Versión del modelo</span>
                  {estimation.modelVersionId ? (
                    <span className="code-pill">{estimation.modelVersionId}</span>
                  ) : (
                    <b>No informada por la API</b>
                  )}
                </div>
                <div className="detail">
                  <span>Escena</span>
                  {estimation.sceneId ? (
                    <span className="code-pill">{estimation.sceneId}</span>
                  ) : (
                    <b>No informada por la API</b>
                  )}
                </div>
                {estimation.acquisitionDate && (
                  <div className="detail">
                    <span>Fecha de adquisición de la escena</span>
                    <b>{formatDateTimeValue(estimation.acquisitionDate)}</b>
                  </div>
                )}
                <div className="detail detail-full">
                  <span>Incertidumbre</span>
                  <b>{formatUncertainty(estimation)}</b>
                </div>
                {estimation.usageLimits.length > 0 && (
                  <div className="detail detail-full">
                    <span>Límites de uso</span>
                    <ul className="traceability-list">
                      {estimation.usageLimits.map((limit) => (
                        <li key={limit}>{limit}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <div className="detail detail-full">
                  <span>Advertencias científicas</span>
                  {estimation.warnings.length > 0 ? (
                    <ul className="traceability-list">
                      {estimation.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  ) : (
                    <b>Sin advertencias adicionales.</b>
                  )}
                </div>
                <div
                  className="status-banner warning detail-full"
                  role="note"
                  aria-label="Advertencia de interpretación"
                >
                  <div>
                    <strong>Advertencia de interpretación</strong>
                    <p>{RN10_WARNING}</p>
                  </div>
                </div>
              </div>
            </section>
          )}

          <section className="card">
            <div className="card-head">
              <h2>{isEstimationView ? 'Estado de la estimación' : 'Estado del experimento'}</h2>
              <span className={statusPresentation[job.status].className}>
                <span aria-hidden="true">
                  {statusPresentation[job.status].icon}
                </span>{' '}
                {statusPresentation[job.status].label}
              </span>
            </div>
            <div className="card-body grid">
              {isInProgressStatus(job.status) && (
                <p className="card-note" role="status">
                  Consultando estado del worker automáticamente hasta recibir el
                  resultado persistido.
                </p>
              )}
              <div className="detail">
                <span>ID del trabajo</span>
                <span className="code-pill">
                  {job.job_id ?? job.id ?? jobId}
                </span>
              </div>
              <div className="detail">
                <span>Tipo</span>
                <b>{job.job_type}</b>
              </div>
              <div className="detail">
                <span>Creado</span>
                <b>{formatDateTimeValue(job.created_at)}</b>
              </div>
              {job.completed_at && (
                <div className="detail">
                  <span>Finalizado</span>
                  <b>{formatDateTimeValue(job.completed_at)}</b>
                </div>
              )}
              {job.status === 'failed' && job.error_message && (
                <div className="status-banner danger" role="alert">
                  {job.error_message}
                </div>
              )}
            </div>
          </section>

          <section className="card">
            <div className="card-head">
              <h2>Trazabilidad</h2>
            </div>
            <div className="card-body grid">
              <div className="detail">
                <span>Versión del dataset</span>
                {resolvedDatasetVersionId ? (
                  <span className="code-pill">{resolvedDatasetVersionId}</span>
                ) : (
                  <b>No informada por la API</b>
                )}
                {resolvedDatasetVersionId && (
                  <button type="button" className="btn btn-secondary" disabled>
                    Abrir manifiesto
                  </button>
                )}
                <p className="card-note">
                  El enlace al manifiesto aún no está disponible en la API.
                </p>
              </div>

              <div className="detail">
                <span>Configuración registrada</span>
                {Object.entries(job.config ?? {}).length > 0 ? (
                  <dl className="traceability-list">
                    {Object.entries(job.config ?? {}).map(([key, value]) => (
                      <div key={key}>
                        <dt>{key}</dt>
                        <dd>{displayValue(value)}</dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <b>Sin configuración informada</b>
                )}
              </div>

              <div className="detail">
                <span>Versión del modelo asociada</span>
                {job.model_version_id ? (
                  <span className="code-pill">{job.model_version_id}</span>
                ) : (
                  <b>No informada por la API</b>
                )}
                {job.model_version_id && (
                  <button type="button" className="btn btn-secondary" disabled>
                    Abrir artefacto
                  </button>
                )}
                <p className="card-note">
                  El enlace al artefacto autorizado aún no está disponible en la
                  API.
                </p>
              </div>
            </div>
          </section>

          {job.result && (
            <section className="card">
              <div className="card-head">
                <h2>Resultado</h2>
              </div>
              <div className="card-body grid">
                {job.job_type === 'training' &&
                  isStructuredTrainingResult(job.result) && (
                    <>
                      <h3 className="detail-full">
                        Métricas frente al baseline
                      </h3>

                      <div className="detail">
                        <span>Modelo evaluado</span>
                        <b>{job.result.model ?? 'baseline'}</b>
                      </div>

                      {job.result.baseline?.strategy && (
                        <div className="detail">
                          <span>Estrategia baseline</span>
                          <b>{job.result.baseline.strategy}</b>
                        </div>
                      )}

                      {job.result.baseline?.target_variable && (
                        <div className="detail">
                          <span>Variable objetivo baseline</span>
                          <b>{job.result.baseline.target_variable}</b>
                        </div>
                      )}

                      <div className="detail">
                        <span>Versión</span>
                        {resolvedVersion ? (
                          <span className="code-pill">{resolvedVersion}</span>
                        ) : (
                          <b>No informada</b>
                        )}
                      </div>

                      <div className="detail">
                        <span>Estado del resultado</span>
                        <b>{resultStatusLabel}</b>
                      </div>

                      <div className="detail">
                        <span>MAE</span>
                        <b>{formatMetric(job.result.metrics?.mae)}</b>
                      </div>

                      <div className="detail">
                        <span>RMSE</span>
                        <b>{formatMetric(job.result.metrics?.rmse)}</b>
                      </div>

                      {typeof baselinePrediction === 'number' && (
                        <div className="detail">
                          <span>Predicción baseline</span>
                          <b>{formatMetric(baselinePrediction)}</b>
                        </div>
                      )}

                      <div className="detail">
                        <span>Tamaño de entrenamiento</span>
                        <b>
                          {formatSampleCount(
                            job.result.baseline?.train_sample_count
                          )}
                        </b>
                      </div>

                      <div className="detail">
                        <span>Tamaño de evaluación</span>
                        <b>
                          {formatSampleCount(
                            job.result.baseline?.validation_sample_count
                          )}
                        </b>
                      </div>

                      <div className="detail detail-full">
                        <span>Condición experimental</span>
                        <b>{getExperimentalCondition(job.result)}</b>
                      </div>

                      <div className="detail">
                        <span>Advertencias</span>
                        {normalizedWarnings.length > 0 ? (
                          <ul className="traceability-list">
                            {normalizedWarnings.map((warning) => (
                              <li key={warning}>{warning}</li>
                            ))}
                          </ul>
                        ) : (
                          <b>Sin advertencias</b>
                        )}
                      </div>
                    </>
                  )}

                {extraResultEntries.map(([key, value]) => (
                  <div className="detail" key={key}>
                    <span>{key}</span>
                    <b>{displayValue(value)}</b>
                  </div>
                ))}
              </div>
            </section>
          )}
          {job.job_type === 'estimation' && job.status === 'completed' && (
            <section className="card">
              <div className="card-head">
                <h2>Resultados por punto</h2>
              </div>
              <div className="card-body">
                {pointGeometries && mapCenter ? (
                  <>
                    <h3 id="estimation-map-heading">
                      Mapa de puntos de estimación
                    </h3>
                    <p className="card-note">
                      El mapa muestra los puntos con coordenadas válidas. La
                      tabla incluye todas las predicciones recibidas.
                    </p>
                    <div
                      className="estimation-map"
                      role="region"
                      aria-labelledby="estimation-map-heading"
                    >
                      <BaseMap
                        center={mapCenter}
                        zoom={mapZoom}
                        geometries={pointGeometries}
                        interactive={false}
                      />
                    </div>
                    <ul className="card-note" aria-label="Leyenda del mapa">
                      <li>
                        Punto rojo: estimación puntual de clorofila-a en la
                        escena.
                      </li>
                      <li>
                        La escala métrica se muestra en la esquina inferior
                        izquierda del mapa.
                      </li>
                    </ul>
                  </>
                ) : (
                  <p className="card-note" role="status">
                    No hay coordenadas válidas para mostrar en el mapa.
                  </p>
                )}

                {pointPredictions.length === 0 ? (
                  <p className="card-note" role="status">
                    La estimación no contiene resultados por punto.
                  </p>
                ) : (
                  <div className="table-wrap">
                    <table>
                      <caption className="sr-only">
                        Estimaciones puntuales de la escena
                      </caption>
                      <thead>
                        <tr>
                          <th scope="col">Estación / Coordenada</th>
                          <th scope="col">Valor</th>
                          <th scope="col">Unidad</th>
                          <th scope="col">Advertencia</th>
                        </tr>
                      </thead>
                      <tbody>
                        {pointPredictions.map((item, index) => {
                          const stationLabel =
                            item.station_name ??
                            item.station_code ??
                            item.point_id ??
                            null;
                          const coordinates = formatCoordinates(
                            item.latitude,
                            item.longitude
                          );
                          const rawValue =
                            item.predicted_value ??
                            item.prediction_value ??
                            item.value;
                          const unit =
                            item.unit?.trim() ||
                            job.result?.unit?.trim() ||
                            job.result?.unidad?.trim() ||
                            DEFAULT_ESTIMATION_UNIT;
                          const warning =
                            item.warning?.trim() ||
                            (item.warnings?.length
                              ? item.warnings.join('; ')
                              : null) ||
                            (job.result?.warnings?.length
                              ? job.result.warnings.join('; ')
                              : null) ||
                            'Sin advertencias';
                          const rowKey =
                            item.point_id ??
                            item.station_code ??
                            item.station_name ??
                            `${item.latitude ?? 'na'}-${item.longitude ?? 'na'}-${index}`;

                          return (
                            <tr key={rowKey}>
                              <td>
                                <div>{stationLabel ?? 'No disponible'}</div>
                                {coordinates && (
                                  <div className="cell-sub">
                                    {coordinates}
                                  </div>
                                )}
                              </td>
                              <td>{formatPointValue(rawValue)}</td>
                              <td>{unit}</td>
                              <td>{warning}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </section>
          )}
        </main>
      ) : null}
    </div>
  );
}
