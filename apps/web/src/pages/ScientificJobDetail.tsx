import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { executionsService } from '../services/executions';
import type { JobStatusResponse, TrainingJobResult } from '../services/executions';

const statusPresentation: Record<
  JobStatusResponse['status'],
  { className: string; label: string; icon: string }
> = {
  completed: { className: 'badge validated', label: 'Completado', icon: '✓' },
  failed: { className: 'badge reported', label: 'Fallido', icon: '!' },
  running: { className: 'badge restricted', label: 'En ejecución', icon: '↻' },
  queued: { className: 'badge draft', label: 'En cola', icon: '•' },
};

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

function getExperimentalCondition(result: TrainingJobResult): string {
  if (result.warnings && result.warnings.length > 0) {
    return `Preliminar: ${result.warnings.join(' ')}`;
  }
  return result.model === 'baseline'
    ? 'Modelo piloto preliminar basado en un baseline de referencia.'
    : 'Condición experimental: resultado piloto preliminar.';
}

export function ScientificJobDetail() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const controller = new AbortController();
    let active = true;

    const loadJob = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await executionsService.getJobStatus(
          jobId,
          controller.signal
        );
        if (active) setJob(response);
      } catch (loadError) {
        if (active && !controller.signal.aborted) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : 'No se pudo cargar el detalle del trabajo.'
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    void loadJob();
    return () => {
      active = false;
      controller.abort();
    };
  }, [jobId]);

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
                {job.dataset_version_id ? (
                  <span className="code-pill">{job.dataset_version_id}</span>
                ) : (
                  <b>No informada por la API</b>
                )}
                {job.dataset_version_id && (
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
                  El enlace al artefacto autorizado aún no está disponible en la API.
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
                    <div className="detail" style={{ gridColumn: '1 / -1' }}>
                      <h3>Métricas frente al baseline</h3>
                    </div>

                    <div className="detail">
                      <span>Modelo baseline</span>
                      <b>
                        {job.result.model ?? 'baseline'}
                        {job.result.baseline?.strategy
                          ? ` (${job.result.baseline.strategy})`
                          : ''}
                      </b>
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

                    {typeof job.result.prediction_value === 'number' && (
                      <div className="detail">
                        <span>Predicción baseline</span>
                        <b>{formatMetric(job.result.prediction_value)}</b>
                      </div>
                    )}

                    <div className="detail">
                      <span>Tamaño de entrenamiento</span>
                      <b>
                        {typeof job.result.baseline?.train_sample_count === 'number'
                          ? String(job.result.baseline.train_sample_count)
                          : 'No disponible'}
                      </b>
                    </div>

                    <div className="detail">
                      <span>Tamaño de evaluación</span>
                      <b>
                        {typeof job.result.baseline?.validation_sample_count === 'number'
                          ? String(job.result.baseline.validation_sample_count)
                          : 'No disponible'}
                      </b>
                    </div>

                    <div className="detail" style={{ gridColumn: '1 / -1' }}>
                      <span>Condición experimental</span>
                      <b>{getExperimentalCondition(job.result)}</b>
                    </div>

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
