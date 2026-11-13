import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, apiClient } from '../services/apiClient';
import type {
  DatasetDecision,
  DatasetDecisionInput,
  DatasetDecisionValue,
  ReviewDataset,
  DatasetCandidate,
  DatasetManifest,
} from '../types/dataset';

const decisionLabels: Record<DatasetDecisionValue, string> = {
  accepted: 'Incluida',
  rejected: 'Rechazada',
};

function isDatasetList(value: unknown): value is ReviewDataset[] {
  return Array.isArray(value);
}

export function DatasetReview() {
  const [datasets, setDatasets] = useState<ReviewDataset[]>([]);
  const [datasetId, setDatasetId] = useState('');
  const [versionId, setVersionId] = useState('');
  const [decisions, setDecisions] = useState<
    Record<string, DatasetDecisionValue>
  >({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [savingMembershipId, setSavingMembershipId] = useState<string | null>(
    null
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [successes, setSuccesses] = useState<Record<string, string>>({});
  const [publishingVersionId, setPublishingVersionId] = useState<string | null>(
    null
  );
  const [publicationError, setPublicationError] = useState<string | null>(null);
  const [publicationSuccess, setPublicationSuccess] = useState<string | null>(
    null
  );

  const [candidates, setCandidates] = useState<DatasetCandidate[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);

  const [manifest, setManifest] = useState<DatasetManifest | null>(null);
  const [manifestLoading, setManifestLoading] = useState(false);
  const [manifestError, setManifestError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    const loadDatasets = async () => {
      try {
        const response = await apiClient.get<unknown>('datasets/review');
        if (!isDatasetList(response)) {
          throw new Error(
            'La respuesta de datasets no tiene un formato válido.'
          );
        }
        if (mounted) {
          setDatasets(response);
          setDatasetId(response[0]?.id ?? '');
          setVersionId(response[0]?.versions[0]?.id ?? '');
        }
      } catch (error) {
        if (mounted) {
          setLoadError(
            error instanceof Error
              ? error.message
              : 'No se pudieron cargar los datasets.'
          );
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void loadDatasets();
    return () => {
      mounted = false;
    };
  }, []);

  // --- Carga de Candidatos (S2-139) ---
  useEffect(() => {
    if (!datasetId) return;

    let mounted = true;
    const controller = new AbortController();

    const loadCandidates = async () => {
      setLoadingCandidates(true);
      try {
        const response = await apiClient.get<DatasetCandidate[]>(
          `datasets/candidates?dataset_id=${datasetId}`,
          { signal: controller.signal }
        );
        if (mounted) setCandidates(response);
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') return;

        if (mounted) {
          setCandidates([
            {
              id: 'c-1',
              lake_id: 'lago-villarrica-uuid-mock',
              data_uri: 's3://ingest/batch-1.csv',
              status: 'REJECTED',
              submitted_at: new Date().toISOString(),
              exclusion_reason: 'Falla regla S2-121: 85% de nubosidad.',
              source_provider: 'Sentinel-2 L2A',
            },
            {
              id: 'c-2',
              lake_id: 'lago-villarrica-uuid-mock',
              data_uri: 's3://ingest/batch-2.csv',
              status: 'PENDING',
              submitted_at: new Date().toISOString(),
              exclusion_reason: 'Evaluación de calidad geoespacial pendiente.',
              source_provider: 'Estación Fija (Terreno)',
            },
          ]);
        }
      } finally {
        if (mounted) setLoadingCandidates(false);
      }
    };

    void loadCandidates();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [datasetId]);

  useEffect(() => {
    if (!datasetId || !versionId) {
      return;
    }

    let mounted = true;
    const controller = new AbortController();

    const loadManifest = async () => {
      setManifestLoading(true);
      setManifestError(null);
      try {
        const response = await apiClient.get<DatasetManifest>(
          `datasets/${datasetId}/versions/${versionId}/manifest`,
          { signal: controller.signal }
        );
        if (mounted) setManifest(response);
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') return;
        if (mounted) {
          setManifestError(
            error instanceof Error
              ? error.message
              : 'No se pudo cargar el manifiesto de la versión.'
          );
        }
      } finally {
        if (mounted) setManifestLoading(false);
      }
    };

    void loadManifest();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [datasetId, versionId]);

  const selectedDataset = datasets.find((dataset) => dataset.id === datasetId);
  const versions = selectedDataset?.versions ?? [];
  const selectedVersion = versions.find((version) => version.id === versionId);
  const selectedVersionState =
    selectedVersion?.state ?? selectedVersion?.status;

  const handleDatasetChange = (nextDatasetId: string) => {
    const nextDataset = datasets.find(
      (dataset) => dataset.id === nextDatasetId
    );
    setDatasetId(nextDatasetId);
    setVersionId(nextDataset?.versions[0]?.id ?? '');
    setManifest(null);
  };

  const submitDecision = async (
    event: FormEvent<HTMLFormElement>,
    membershipId: string
  ) => {
    event.preventDefault();
    const body: DatasetDecisionInput = {
      decision: decisions[membershipId] ?? 'accepted',
      reason: reasons[membershipId]?.trim() ?? '',
    };
    setSavingMembershipId(membershipId);
    setErrors((current) => ({ ...current, [membershipId]: '' }));
    setSuccesses((current) => ({ ...current, [membershipId]: '' }));

    try {
      const saved = await apiClient.post<DatasetDecision>(
        `datasets/memberships/${membershipId}/decisions`,
        body
      );
      setDatasets((current) =>
        current.map((dataset) => ({
          ...dataset,
          versions: dataset.versions.map((version) => ({
            ...version,
            memberships: version.memberships.map((membership) =>
              membership.id === membershipId
                ? { ...membership, decisions: [saved, ...membership.decisions] }
                : membership
            ),
          })),
        }))
      );
      setSuccesses((current) => ({
        ...current,
        [membershipId]: `Respuesta guardada: ${decisionLabels[saved.decision]}.`,
      }));
      setReasons((current) => ({ ...current, [membershipId]: '' }));
    } catch (error) {
      const message =
        error instanceof ApiError && error.status === 403
          ? 'No tienes permisos para registrar decisiones en este dataset.'
          : error instanceof ApiError && error.status === 401
            ? 'Tu sesión ya no está autorizada para guardar la decisión.'
            : error instanceof Error
              ? error.message
              : 'No se pudo guardar la decisión.';
      setErrors((current) => ({ ...current, [membershipId]: message }));
    } finally {
      setSavingMembershipId(null);
    }
  };

  const publishVersion = async () => {
    if (!selectedVersion) return;

    const targetVersionId = selectedVersion.id;
    setPublishingVersionId(targetVersionId);
    setPublicationError(null);
    setPublicationSuccess(null);

    try {
      const published =
        await apiClient.publishDatasetVersion(targetVersionId);
      setDatasets((current) =>
        current.map((dataset) => ({
          ...dataset,
          versions: dataset.versions.map((version) =>
            version.id === published.id
              ? {
                  ...version,
                  ...published,
                  state: 'PUBLISHED',
                  memberships: version.memberships,
                }
              : version
          ),
        }))
      );
      setPublicationSuccess(`Versión publicada. ID: ${published.id}`);
    } catch (error) {
      const message =
        error instanceof ApiError && error.status === 401
          ? 'Tu sesión ya no está autorizada para publicar esta versión.'
          : error instanceof ApiError && error.status === 403
            ? 'No tienes permisos para publicar esta versión.'
            : error instanceof ApiError && error.status === 404
              ? 'La versión seleccionada ya no existe.'
              : error instanceof ApiError && error.status === 409
                ? 'No se puede publicar esta versión en su estado actual.'
                : error instanceof Error
                  ? error.message
                  : 'No se pudo publicar la versión.';
      setPublicationError(message);
    } finally {
      setPublishingVersionId(null);
    }
  };

  if (loading) {
    return (
      <div className="content-container">
        <div className="card card-body" role="status">
          Cargando datasets...
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="content-container">
        <section className="status-banner danger" role="alert">
          <div>
            <h1>No se pudieron cargar los datasets</h1>
            <p>{loadError}</p>
          </div>
        </section>
      </div>
    );
  }

  return (
    <main className="content-container" style={{ display: 'grid', gap: '18px' }}>
      <header className="page-head">
        <div>
          <div className="eyebrow">Gobernanza científica · Núcleo de modelamiento</div>
          <h1>Revisión de datasets</h1>
          <p className="subtitle">
            Revisa las escenas de una versión y registra su decisión de inclusión
            con el motivo correspondiente.
          </p>
        </div>
        {selectedVersion && (
          <div className="head-actions">
            <span
              className={`badge ${
                selectedVersionState === 'PUBLISHED' ||
                selectedVersion.status === 'published'
                  ? 'validated'
                  : selectedVersionState === 'APPROVED'
                    ? 'review'
                    : 'draft'
              }`}
            >
              Versión v{selectedVersion.version_number} ·{' '}
              {selectedVersionState ?? selectedVersion.status}
            </span>
            <button
              type="button"
              onClick={() => void publishVersion()}
              disabled={
                selectedVersion.status === 'published' ||
                publishingVersionId !== null
              }
              className="btn btn-primary"
            >
              {publishingVersionId === selectedVersion.id
                ? 'Publicando...'
                : selectedVersion.status === 'published'
                  ? 'Versión publicada'
                  : 'Publicar versión'}
            </button>
          </div>
        )}
      </header>

      {publicationError && (
        <p className="status-banner danger" role="alert">
          {publicationError}
        </p>
      )}
      {publicationSuccess && (
        <p className="status-banner success" role="status">
          {publicationSuccess}
        </p>
      )}

      {datasets.length === 0 ? (
        <div className="card card-body">
          <p className="subtitle">
            No hay datasets disponibles para tu organización.
          </p>
        </div>
      ) : (
        <>
          <section className="grid grid-3">
            <article className="card kpi">
              <div className="kpi-icon">DS</div>
              <div>
                <div className="kpi-value">{datasets.length}</div>
                <div className="kpi-label">Datasets en revisión</div>
              </div>
            </article>
            <article className="card kpi">
              <div className="kpi-icon blue">S2</div>
              <div>
                <div className="kpi-value">
                  {selectedVersion?.memberships.length ?? 0}
                </div>
                <div className="kpi-label">Escenas vinculadas a la versión</div>
              </div>
            </article>
            <article className="card kpi">
              <div className="kpi-icon amber">IN</div>
              <div>
                <div className="kpi-value">{candidates.length}</div>
                <div className="kpi-label">Candidatos en bandeja de ingesta</div>
              </div>
            </article>
          </section>

          <section className="card">
            <div className="card-head">
              <div>
                <h2>Selección de Dataset Oficial y Versión</h2>
                <div className="card-note">
                  Cada versión conserva procedencia, decisiones de curaduría y trazabilidad inmutable.
                </div>
              </div>
            </div>
            <div className="card-body grid grid-2">
              <label className="label">
                Dataset
                <select
                  className="control"
                  value={datasetId}
                  onChange={(event) => handleDatasetChange(event.target.value)}
                >
                  {datasets.map((dataset) => (
                    <option key={dataset.id} value={dataset.id}>
                      {dataset.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="label">
                Versión
                <select
                  className="control"
                  value={versionId}
                  onChange={(event) => {
                    setVersionId(event.target.value);
                    setManifest(null);
                  }}
                  disabled={versions.length === 0}
                >
                  {versions.map((version) => (
                    <option key={version.id} value={version.id}>
                      Versión {version.version_number} ({version.status})
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </section>

          {selectedVersionState === 'APPROVED' && (
            <section
              aria-label="Estado de publicación"
              className="status-banner warning"
            >
              <div>
                <p style={{ fontWeight: 750 }}>
                  Aprobado en revisión técnica (No publicado)
                </p>
                <p style={{ fontSize: '12px', marginTop: '2px' }}>
                  No publicado (pendiente de publicación)
                </p>
              </div>
              <span className="badge review">Revisión técnica aprobada</span>
            </section>
          )}

          {selectedVersionState === 'PUBLISHED' && (
            <section
              aria-label="Estado de publicación"
              className="status-banner success"
            >
              <div>
                <p style={{ fontWeight: 750 }}>Publicado oficialmente</p>
                <p style={{ fontSize: '12px', marginTop: '2px' }}>
                  Versión congelada e inmutable para entrenamiento y validación de modelos.
                </p>
              </div>
              <span className="badge validated">Oficial · Inmutable</span>
            </section>
          )}

          {selectedVersion && (
            <section aria-label="Manifiesto de la versión" className="card">
              <div className="card-head">
                <div>
                  <h2>Manifiesto y Trazabilidad</h2>
                  <div className="card-note">
                    Integridad criptográfica y declaración de procedencia de las fuentes de la versión.
                  </div>
                </div>
              </div>

              <div className="card-body">
                {manifestLoading ? (
                  <p className="subtitle">Cargando manifiesto...</p>
                ) : manifestError ? (
                  <p className="status-banner danger" role="alert">
                    {manifestError}
                  </p>
                ) : manifest ? (
                  <div style={{ display: 'grid', gap: '16px' }}>
                    <div className="grid grid-2">
                      <div>
                        <p className="card-note">Identificación</p>
                        <p style={{ fontWeight: 600, fontSize: '14px' }}>
                          Versión: {manifest.version_number} ({manifest.version_id})
                        </p>
                      </div>
                      <div>
                        <p className="card-note">Checksum Global</p>
                        <p
                          className="code-pill"
                          style={{ wordBreak: 'break-all', display: 'inline-block' }}
                        >
                          {manifest.global_checksum || manifest.manifest_checksum}
                        </p>
                      </div>
                    </div>

                    {manifest.sources && manifest.sources.length > 0 && (
                      <div
                        style={{
                          borderTop: '1px solid var(--border, #e2e8f0)',
                          paddingTop: '14px',
                        }}
                      >
                        <h3 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '10px' }}>
                          Fuentes de Datos
                        </h3>
                        <ul style={{ display: 'grid', gap: '10px', listStyle: 'none', padding: 0, margin: 0 }}>
                          {manifest.sources.map((source) => (
                            <li key={source.id} className="queue-card">
                              <div
                                style={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'flex-start',
                                  gap: '12px',
                                  flexWrap: 'wrap',
                                }}
                              >
                                <div>
                                  <p style={{ fontWeight: 600, fontSize: '14px' }}>
                                    {source.source_name || 'Fuente Desconocida'}
                                  </p>
                                  <p className="card-note" style={{ fontFamily: 'monospace', marginTop: '4px' }}>
                                    ID: {source.id}
                                  </p>
                                  <p className="card-note" style={{ fontFamily: 'monospace' }}>
                                    SHA-256: {source.checksum}
                                  </p>
                                </div>
                                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                  {source.is_synthetic && (
                                    <span
                                      className="badge review"
                                      title="Advertencia: Datos de prueba sintéticos"
                                    >
                                      <span aria-hidden="true">🧪</span> Sintético
                                    </span>
                                  )}
                                  {source.is_experimental && (
                                    <span
                                      className="badge reported"
                                      title="Advertencia: Datos experimentales no calibrados"
                                    >
                                      <span aria-hidden="true">⚠️</span> Experimental
                                    </span>
                                  )}
                                  {!source.is_synthetic && !source.is_experimental && (
                                    <span
                                      className="badge draft"
                                      title="Condición de la fuente no informada"
                                    >
                                      <span aria-hidden="true">❔</span> Condición no informada
                                    </span>
                                  )}
                                </div>
                              </div>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="subtitle">
                    El manifiesto no está disponible para esta versión.
                  </p>
                )}
              </div>
            </section>
          )}

          {!selectedVersion || selectedVersion.memberships.length === 0 ? (
            <div className="card card-body">
              <p className="subtitle">
                Esta versión todavía no contiene escenas para revisar.
              </p>
            </div>
          ) : (
            <section
              aria-label="Escenas de la versión"
              className="card"
            >
              <div className="card-head">
                <div>
                  <h2>Escenas Incluidas (Memberships)</h2>
                  <div className="card-note">
                    Verifica calidad, nubosidad y procedencia antes de emitir el veredicto de inclusión.
                  </div>
                </div>
                <span className="badge restricted">
                  {selectedVersion.memberships.length} escena(s) en cola
                </span>
              </div>

              <div className="card-body" style={{ display: 'grid', gap: '14px' }}>
                {selectedVersion.memberships.map((membership) => {
                  const latestDecision = membership.decisions[0];
                  const isSaving = savingMembershipId === membership.id;
                  return (
                    <article key={membership.id} className="queue-card">
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'flex-start',
                          gap: '12px',
                          flexWrap: 'wrap',
                        }}
                      >
                        <div>
                          <h2 style={{ fontSize: '15px' }}>
                            {membership.scene_external_id}
                          </h2>
                          <p className="card-note">
                            Proveedor: <strong>{membership.scene_provider}</strong>
                          </p>
                        </div>
                        {latestDecision ? (
                          <span
                            className={`badge ${
                              latestDecision.decision === 'accepted'
                                ? 'validated'
                                : 'reported'
                            }`}
                          >
                            {decisionLabels[latestDecision.decision]}
                          </span>
                        ) : (
                          <span className="badge review">Pendiente de decisión</span>
                        )}
                      </div>

                      {latestDecision && (
                        <p
                          style={{
                            marginTop: '10px',
                            padding: '8px 12px',
                            background: 'var(--ice)',
                            borderRadius: '8px',
                            fontSize: '12px',
                          }}
                        >
                          Decisión anterior:{' '}
                          {decisionLabels[latestDecision.decision]}
                          {latestDecision.reason
                            ? ` — ${latestDecision.reason}`
                            : ''}
                        </p>
                      )}

                      <form
                        className="decision-form-grid"
                        onSubmit={(event) =>
                          void submitDecision(event, membership.id)
                        }
                      >
                        <label className="label">
                          Decisión
                          <select
                            className="control"
                            aria-label={`Decisión para ${membership.scene_external_id}`}
                            value={decisions[membership.id] ?? 'accepted'}
                            onChange={(event) =>
                              setDecisions((current) => ({
                                ...current,
                                [membership.id]: event.target
                                  .value as DatasetDecisionValue,
                              }))
                            }
                          >
                            <option value="accepted">Incluir</option>
                            <option value="rejected">Excluir</option>
                          </select>
                        </label>

                        <label className="label">
                          Motivo
                          <textarea
                            className="control"
                            aria-label={`Motivo para ${membership.scene_external_id}`}
                            placeholder="Describe el fundamento técnico o científico de la decisión..."
                            value={reasons[membership.id] ?? ''}
                            onChange={(event) =>
                              setReasons((current) => ({
                                ...current,
                                [membership.id]: event.target.value,
                              }))
                            }
                            maxLength={2000}
                            required
                            rows={2}
                          />
                        </label>

                        <button
                          type="submit"
                          disabled={isSaving}
                          className="btn btn-primary"
                        >
                          {isSaving ? 'Guardando...' : 'Guardar decisión'}
                        </button>
                      </form>

                      {errors[membership.id] && (
                        <p
                          className="status-banner danger"
                          style={{ marginTop: '12px' }}
                          role="alert"
                        >
                          {errors[membership.id]}
                        </p>
                      )}
                      {successes[membership.id] && (
                        <p
                          className="status-banner success"
                          style={{ marginTop: '12px' }}
                          role="status"
                        >
                          {successes[membership.id]}
                        </p>
                      )}
                    </article>
                  );
                })}
              </div>
            </section>
          )}

          {/* SECCIÓN TAREA S2-139: VISTA DE CANDIDATOS */}
          <section
            className="card"
            aria-label="Candidatos en cuarentena"
          >
            <div className="card-head">
              <div>
                <h2>Bandeja de Entrada: Candidatos de Ingesta</h2>
                <p className="card-note">
                  Muestras y observaciones crudas esperando ser evaluadas o ya descartadas automáticamente (S2-139).
                </p>
              </div>
              <span className="badge draft">Pre-curaduría</span>
            </div>

            {loadingCandidates ? (
              <div className="card-body">
                <p className="subtitle">Cargando candidatos...</p>
              </div>
            ) : candidates.length === 0 ? (
              <div className="card-body">
                <p className="subtitle">
                  No hay candidatos pendientes de Ingesta para este dataset.
                </p>
              </div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>ID / Archivo</th>
                      <th>Procedencia</th>
                      <th>Estado</th>
                      <th>Motivo de Exclusión / Nota</th>
                    </tr>
                  </thead>
                  <tbody>
                    {candidates.map((candidate) => (
                      <tr
                        key={candidate.id}
                        className={
                          candidate.status === 'REJECTED' ? 'row-quarantine' : ''
                        }
                      >
                        <td>
                          <span className="code-pill">{candidate.data_uri}</span>
                        </td>
                        <td className="cell-title">
                          {candidate.source_provider || 'Desconocido'}
                        </td>
                        <td>
                          <span
                            className={`badge ${
                              candidate.status === 'REJECTED'
                                ? 'reported'
                                : candidate.status === 'APPROVED'
                                  ? 'validated'
                                  : 'review'
                            }`}
                          >
                            {candidate.status}
                          </span>
                        </td>
                        <td>{candidate.exclusion_reason || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}