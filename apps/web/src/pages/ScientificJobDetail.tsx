import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { executionsService } from '../services/executions';
import type {
  JobStatusResponse,
  TrainingJobResult,
} from '../services/executions';

const DEFAULT_POLL_INTERVAL_MS = 1500;

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
]);

function displayValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value) ?? String(value);
}

function formatMetric(value: number | undefined): string {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return 'No disponible';
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(4);
}

function isStructuredTrainingResult(result: TrainingJobResult): boolean {
  return Boolean(
    result.metrics ||
      result.model ||
      result.baseline ||
      result.version ||
      result.warnings
  );
}

export function ScientificJobDetail({
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
}: ScientificJobDetailProps) {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    let active = true;
    let activeController = new AbortController();
    let pollTimer: number | null = null;

    const loadJob = async (isInitialLoad: boolean) => {
      if (isInitialLoad) {
        setLoading(true);
        setError(null);
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

        if (isInProgressStatus(response.status)) {
          pollTimer = window.setTimeout(() => {
            void loadJob(false);
          }, pollIntervalMs);
        }
      } catch (loadError) {
        if (active && !activeController.signal.aborted) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : 'No se pudo cargar el detalle del trabajo.'
          );
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
  }, [jobId, pollIntervalMs]);

  const resolvedDatasetVersionId = job ? resolveDatasetVersionId(job) : null;

  const extraResultEntries = job?.result
    ? Object.entries(job.result).filter(
        ([key]) => !STRUCTURED_RESULT_KEYS.has(key)
      )
    : [];

  const resolvedVersion =
    job?.result?.version ??
    job?.result?.model_version_id ??
    job?.result?.dataset_version_id ??
    job?.model_version_id ??
    job?.dataset_version_id;

  const resultStatusKey = job?.result?.status as
    | JobStatusResponse['status']
    | undefined;
  const resultStatusLabel =
    resultStatusKey && resultStatusKey in statusPresentation
      ? statusPresentation[resultStatusKey].label
      : job?.result?.status ?? statusPresentation[job?.status ?? 'queued'].label;

  return (
    <div className="content-container">
      <header className="page-head">
        <div>
          <span className="eyebrow">Trazabilidad científica</span>
          <h1>Detalle del experimento</h1>
          <p className="subtitle">Trabajo {jobId ?? 'no identificado'}</p>
        </div>
        <Link to="/lakes" className="btn btn-secondary">
          Volver a lagos
        </Link>
      </header>

      {!jobId ? (
        <div className="status-banner danger" role="alert">
          No se indicó el identificador del trabajo.
        </div>
      ) : loading ? (
        <p role="status">Cargando detalle del trabajo...</p>
      ) : error ? (
        <div className="status-banner danger" role="alert">
          {error}
        </div>
      ) : job ? (
        <main className="grid">
          <section className="card">
            <div className="card-head">
              <h2>Estado del experimento</h2>
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
                <b>{new Date(job.created_at).toLocaleString()}</b>
              </div>
              {job.completed_at && (
                <div className="detail">
                  <span>Finalizado</span>
                  <b>{new Date(job.completed_at).toLocaleString()}</b>
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
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled
                  >
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
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled
                  >
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
                {isStructuredTrainingResult(job.result) && (
                  <>
                    <div className="detail">
                      <span>Modelo baseline</span>
                      <b>
                        {job.result.model ?? 'baseline'}
                        {job.result.baseline?.strategy
                          ? ` (${job.result.baseline.strategy})`
                          : ''}
                      </b>
                    </div>

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

                    {typeof job.result.prediction_value === 'number' && (
                      <div className="detail">
                        <span>Predicción baseline</span>
                        <b>{formatMetric(job.result.prediction_value)}</b>
                      </div>
                    )}

                    <div className="detail">
                      <span>Advertencias</span>
                      {job.result.warnings && job.result.warnings.length > 0 ? (
                        <ul className="traceability-list">
                          {job.result.warnings.map((warning) => (
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
        </main>
      ) : null}
    </div>
  );
}


