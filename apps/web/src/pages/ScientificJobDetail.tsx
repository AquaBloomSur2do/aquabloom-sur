import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { executionsService } from '../services/executions';
import type { JobStatusResponse } from '../services/executions';

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

function displayValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value) ?? String(value);
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
          activeController.signal,
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
              : 'No se pudo cargar el detalle del trabajo.',
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
                {Object.entries(job.result).map(([key, value]) => (
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


