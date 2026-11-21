import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { executionsService } from '../services/executions';
import type { JobStatusResponse } from '../services/executions';

function displayValue(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  return JSON.stringify(value) ?? String(value);
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
              <span className="badge draft">{job.status}</span>
            </div>
            <div className="card-body grid">
              <div className="detail">
                <span>ID del trabajo</span>
                <b>{job.id}</b>
              </div>
              <div className="detail">
                <span>Tipo</span>
                <b>{job.job_type}</b>
              </div>
              <div className="detail">
                <span>Creado</span>
                <b>{new Date(job.created_at).toLocaleString()}</b>
              </div>
              {job.error_message && (
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
                <b>{job.dataset_version_id ?? 'No informada por la API'}</b>
                {job.dataset_version_id && (
                  // TODO: Integrar el enlace al manifiesto cuando la API incluya el ID del dataset.
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled
                    title="La API debe incluir el identificador del dataset para abrir su manifiesto."
                  >
                    Abrir manifiesto
                  </button>
                )}
              </div>

              <div className="detail">
                <span>Configuración registrada</span>
                {Object.entries(job.config).length > 0 ? (
                  <dl className="traceability-list">
                    {Object.entries(job.config).map(([key, value]) => (
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
                <b>{job.model_version_id ?? 'No informada por la API'}</b>
                {job.model_version_id && (
                  // TODO: Integrar el enlace al artefacto autorizado cuando la API incluya su URL y autorización.
                  <button
                    type="button"
                    className="btn btn-secondary"
                    disabled
                    title="La API no informa la URL ni el estado de autorización del artefacto."
                  >
                    Abrir artefacto
                  </button>
                )}
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
