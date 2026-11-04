import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, apiClient } from '../services/apiClient';
import type {
  DatasetDecision,
  DatasetDecisionInput,
  DatasetDecisionValue,
  DatasetCandidate,
  DatasetCandidateDecision,
  ReviewDataset
} from '../types/dataset';

const decisionLabels: Record<DatasetDecisionValue, string> = {
  accepted: 'Incluida',
  rejected: 'Rechazada',
};

function isDatasetCandidateList(value: unknown): value is DatasetCandidate[] {
  return (
    Array.isArray(value) &&
    value.every(
      (candidate) =>
        typeof candidate === 'object' &&
        candidate !== null &&
        'id' in candidate &&
        typeof candidate.id === 'string' &&
        'dataset_id' in candidate &&
        typeof candidate.dataset_id === 'string' &&
        'lake_id' in candidate &&
        typeof candidate.lake_id === 'string' &&
        'data_uri' in candidate &&
        typeof candidate.data_uri === 'string' &&
        'source_provider' in candidate &&
        typeof candidate.source_provider === 'string' &&
        'status' in candidate &&
        ['PENDING', 'APPROVED', 'REJECTED'].includes(String(candidate.status)) &&
        'submitted_at' in candidate &&
        typeof candidate.submitted_at === 'string' &&
        'decisions' in candidate &&
        Array.isArray(candidate.decisions)
    )
  );
}

function isDatasetList(value: unknown): value is ReviewDataset[] {
  return Array.isArray(value);
}

function isDatasetListResponse(
  value: unknown
): value is { items: ReviewDataset[] } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'items' in value &&
    isDatasetList(value.items)
  );
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
  const [candidateLoadError, setCandidateLoadError] = useState<string | null>(
    null
  );
  const [candidateDecisions, setCandidateDecisions] = useState<
    Record<string, DatasetDecisionValue>
  >({});
  const [candidateReasons, setCandidateReasons] = useState<
    Record<string, string>
  >({});
  const [savingCandidateId, setSavingCandidateId] = useState<string | null>(
    null
  );
  const [candidateErrors, setCandidateErrors] = useState<
    Record<string, string>
  >({});
  const [candidateSuccesses, setCandidateSuccesses] = useState<
    Record<string, string>
  >({});

  useEffect(() => {
    let mounted = true;

    const loadDatasets = async () => {
      try {
        const response = await apiClient.get<unknown>('datasets/review');
        const datasetItems = isDatasetList(response)
          ? response
          : isDatasetListResponse(response)
            ? response.items
            : null;
        if (!datasetItems) {
          throw new Error(
            'La respuesta de datasets no tiene un formato válido.'
          );
        }
        if (mounted) {
          setDatasets(datasetItems);
          setDatasetId(datasetItems[0]?.id ?? '');
          setVersionId(datasetItems[0]?.versions[0]?.id ?? '');
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

  useEffect(() => {
    if (!datasetId) return;

    let mounted = true;
    const controller = new AbortController();
    const loadCandidates = async () => {
      setLoadingCandidates(true);
      setCandidateLoadError(null);
      try {
        const response = await apiClient.get<unknown>(
          `datasets/candidates?dataset_id=${encodeURIComponent(datasetId)}`,
          { signal: controller.signal }
        );
        if (!isDatasetCandidateList(response)) {
          throw new Error('La respuesta de candidatos no tiene un formato válido.');
        }
        if (mounted) setCandidates(response);
      } catch (error) {
        if (
          (error instanceof ApiError && error.isCancelled) ||
          (error instanceof Error && error.name === 'AbortError')
        ) {
          return;
        }
        if (mounted) {
          setCandidateLoadError(
            error instanceof Error
              ? `No se pudieron cargar los candidatos: ${error.message}`
              : 'No se pudieron cargar los candidatos.'
          );
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
    setCandidates([]);
    setVersionId(nextDataset?.versions[0]?.id ?? '');
  };

  const submitCandidateDecision = async (
    event: FormEvent<HTMLFormElement>,
    candidateId: string
  ) => {
    event.preventDefault();
    setSavingCandidateId(candidateId);
    setCandidateErrors((current) => ({ ...current, [candidateId]: '' }));
    setCandidateSuccesses((current) => ({ ...current, [candidateId]: '' }));
    const body: DatasetDecisionInput = {
      decision: candidateDecisions[candidateId] ?? 'accepted',
      reason: candidateReasons[candidateId]?.trim() ?? '',
    };

    try {
      const saved = await apiClient.post<DatasetCandidateDecision>(
        `datasets/candidates/${candidateId}/decisions`,
        body
      );
      setCandidates((current) =>
        current.map((candidate) =>
          candidate.id === candidateId
            ? {
                ...candidate,
                status:
                  saved.decision === 'accepted' ? 'APPROVED' : 'REJECTED',
                exclusion_reason:
                  saved.decision === 'rejected' ? saved.reason : null,
                decisions: [saved, ...candidate.decisions],
              }
            : candidate
        )
      );
      setCandidateSuccesses((current) => ({
        ...current,
        [candidateId]: `Respuesta guardada: ${decisionLabels[saved.decision]}.`,
      }));
      setCandidateReasons((current) => ({ ...current, [candidateId]: '' }));
    } catch (error) {
      const message =
        error instanceof ApiError && error.status === 403
          ? 'No tienes permisos para registrar decisiones en este dataset.'
          : error instanceof ApiError && error.status === 401
            ? 'Tu sesión ya no está autorizada para guardar la decisión.'
            : error instanceof Error
              ? error.message
              : 'No se pudo guardar la decisión.';
      setCandidateErrors((current) => ({
        ...current,
        [candidateId]: message,
      }));
    } finally {
      setSavingCandidateId(null);
    }
  };

  const submitDecision = async (
    event: FormEvent<HTMLFormElement>,
    membershipId: string
  ) => {
    // ... Código original de tus compañeros para submitDecision ...
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
      <div className="p-8 text-center text-gray-500" role="status">
        Cargando datasets...
      </div>
    );
  }

  if (loadError) {
    return (
      <section className="state-panel state-panel--error" role="alert">
        <h1 className="font-bold">No se pudieron cargar los datasets</h1>
        <p>{loadError}</p>
      </section>
    );
  }

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">
          Revisión de datasets
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          Revisa las escenas de una versión y registra su decisión de inclusión
          con el motivo correspondiente.
        </p>
      </header>

      {datasets.length === 0 ? (
        <p className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-600">
          No hay datasets disponibles para tu organización.
        </p>
      ) : (
        <>
          <section className="grid gap-4 rounded-lg border border-gray-200 bg-white p-5 md:grid-cols-2">
            <label className="block text-sm font-medium text-gray-700">
              Dataset
              <select
                className="mt-1 block w-full rounded-md border border-gray-300 p-2"
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

            <label className="block text-sm font-medium text-gray-700">
              Versión
              <select
                className="mt-1 block w-full rounded-md border border-gray-300 p-2"
                value={versionId}
                onChange={(event) => setVersionId(event.target.value)}
                disabled={versions.length === 0}
              >
                {versions.map((version) => (
                  <option key={version.id} value={version.id}>
                    Versión {version.version_number} ({version.status})
                  </option>
                ))}
              </select>
            </label>
          </section>

          {selectedVersion && (
            <section className="rounded-lg border border-gray-200 bg-white p-5">
              <button
                type="button"
                onClick={() => void publishVersion()}
                disabled={
                  selectedVersion.status === 'published' ||
                  publishingVersionId !== null
                }
                className="rounded-md bg-blue-700 px-4 py-2 font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {publishingVersionId === selectedVersion.id
                  ? 'Publicando...'
                  : selectedVersion.status === 'published'
                    ? 'Versión publicada'
                    : 'Publicar versión'}
              </button>
              {publicationError && (
                <p className="mt-3 text-sm text-red-700" role="alert">
                  {publicationError}
                </p>
              )}
              {publicationSuccess && (
                <p className="mt-3 text-sm text-green-700" role="status">
                  {publicationSuccess}
                </p>
              )}
            </section>
          )}

          {selectedVersionState === 'APPROVED' && (
            <section
              aria-label="Estado de publicación"
              className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
            >
              <p className="font-semibold">
                Aprobado en revisión técnica (No publicado)
              </p>
              <p className="mt-1">
                No publicado (pendiente de publicación)
              </p>
            </section>
          )}

          {selectedVersionState === 'PUBLISHED' && (
            <section
              aria-label="Estado de publicación"
              className="rounded-lg border border-green-200 bg-green-50 p-4 text-sm text-green-900"
            >
              <p className="font-semibold">Publicado oficialmente</p>
            </section>
          )}

          {!selectedVersion || selectedVersion.memberships.length === 0 ? (
            <p className="rounded-lg border border-gray-200 bg-white p-6 text-sm text-gray-600">
              Esta versión todavía no contiene escenas para revisar.
            </p>
          ) : (
            <section aria-label="Escenas de la versión" className="space-y-4">
               <h2 className="text-xl font-bold text-gray-900 mb-2">Escenas Incluidas (Memberships)</h2>
              {selectedVersion.memberships.map((membership) => {
                 // ... Código original del map intacto ...
                 const latestDecision = membership.decisions[0];
                 const isSaving = savingMembershipId === membership.id;
                 return (
                  <article key={membership.id} className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
                    <div className="mb-4">
                      <h2 className="font-semibold text-gray-900">
                        {membership.scene_external_id}
                      </h2>
                      <p className="text-sm text-gray-600">
                        Proveedor: {membership.scene_provider}
                      </p>
                      {latestDecision && (
                        <p className="mt-2 text-sm text-gray-700">
                          Decisión anterior:{' '}
                          {decisionLabels[latestDecision.decision]}
                          {latestDecision.reason
                            ? ` — ${latestDecision.reason}`
                            : ''}
                        </p>
                      )}
                    </div>

                    <form
                      className="grid gap-3 md:grid-cols-[1fr_2fr_auto] md:items-end"
                      onSubmit={(event) =>
                        void submitDecision(event, membership.id)
                      }
                    >
                      <label className="block text-sm font-medium text-gray-700">
                        Decisión
                        <select
                          className="mt-1 block w-full rounded-md border border-gray-300 p-2"
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

                      <label className="block text-sm font-medium text-gray-700">
                        Motivo
                        <textarea
                          className="mt-1 block w-full rounded-md border border-gray-300 p-2"
                          aria-label={`Motivo para ${membership.scene_external_id}`}
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
                        className="rounded-md bg-blue-700 px-4 py-2 font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {isSaving ? 'Guardando...' : 'Guardar decisión'}
                      </button>
                    </form>

                    {errors[membership.id] && (
                      <p className="mt-3 text-sm text-red-700" role="alert">
                        {errors[membership.id]}
                      </p>
                    )}
                    {successes[membership.id] && (
                      <p className="mt-3 text-sm text-green-700" role="status">
                        {successes[membership.id]}
                      </p>
                    )}
                  </article>
                );
              })}
            </section>
          )}

          <section
            className="mt-10 border-t border-gray-200 pt-8"
            aria-label="Candidatos de ingesta"
          >
            <div className="mb-4">
              <h2 className="text-xl font-bold text-gray-900">
                Candidatos de ingesta
              </h2>
              <p className="mt-1 text-sm text-gray-600">
                Revisa la procedencia y registra la decisión con su motivo.
              </p>
            </div>

            {candidateLoadError ? (
              <p
                className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
                role="alert"
              >
                {candidateLoadError}
              </p>
            ) : loadingCandidates ? (
              <p className="text-sm text-gray-500" role="status">
                Cargando candidatos...
              </p>
            ) : candidates.length === 0 ? (
              <p className="rounded-lg border border-gray-200 bg-gray-50 p-6 text-sm text-gray-600">
                No hay candidatos registrados para este dataset.
              </p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-gray-200">
                <table className="w-full text-left text-sm">
                  <thead className="bg-gray-100">
                    <tr>
                      <th className="p-3 font-semibold text-gray-700">
                        ID / Archivo
                      </th>
                      <th className="p-3 font-semibold text-gray-700">
                        Procedencia
                      </th>
                      <th className="p-3 font-semibold text-gray-700">
                        Estado
                      </th>
                      <th className="p-3 font-semibold text-gray-700">
                        Motivo de exclusión
                      </th>
                      <th className="p-3 font-semibold text-gray-700">
                        Decisión
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 bg-white">
                    {candidates.map((candidate) => {
                      const isSaving = savingCandidateId === candidate.id;
                      return (
                        <tr key={candidate.id} className="align-top">
                          <td className="p-3 font-mono text-xs">
                            {candidate.data_uri}
                          </td>
                          <td className="p-3">{candidate.source_provider}</td>
                          <td className="p-3">
                            <span
                              className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                                candidate.status === 'REJECTED'
                                  ? 'bg-red-100 text-red-800'
                                  : candidate.status === 'APPROVED'
                                    ? 'bg-green-100 text-green-800'
                                    : 'bg-yellow-100 text-yellow-800'
                              }`}
                            >
                              {candidate.status === 'APPROVED'
                                ? 'Incluido'
                                : candidate.status === 'REJECTED'
                                  ? 'Excluido'
                                  : 'Pendiente'}
                            </span>
                          </td>
                          <td className="p-3 text-gray-600">
                            {candidate.exclusion_reason || '—'}
                          </td>
                          <td className="min-w-72 p-3">
                            <form
                              className="space-y-2"
                              onSubmit={(event) =>
                                void submitCandidateDecision(event, candidate.id)
                              }
                            >
                              <label className="block text-sm font-medium text-gray-700">
                                <span className="sr-only">Decisión para {candidate.data_uri}</span>
                                <select
                                  className="block w-full rounded-md border border-gray-300 p-2"
                                  aria-label={`Decisión para ${candidate.data_uri}`}
                                  value={candidateDecisions[candidate.id] ?? 'accepted'}
                                  onChange={(event) =>
                                    setCandidateDecisions((current) => ({
                                      ...current,
                                      [candidate.id]: event.target
                                        .value as DatasetDecisionValue,
                                    }))
                                  }
                                >
                                  <option value="accepted">Incluir</option>
                                  <option value="rejected">Excluir</option>
                                </select>
                              </label>
                              <label className="block text-sm font-medium text-gray-700">
                                <span className="sr-only">Motivo para {candidate.data_uri}</span>
                                <textarea
                                  className="block w-full rounded-md border border-gray-300 p-2"
                                  aria-label={`Motivo para ${candidate.data_uri}`}
                                  value={candidateReasons[candidate.id] ?? ''}
                                  onChange={(event) =>
                                    setCandidateReasons((current) => ({
                                      ...current,
                                      [candidate.id]: event.target.value,
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
                                className="rounded-md bg-blue-700 px-3 py-2 font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
                              >
                                {isSaving
                                  ? 'Guardando...'
                                  : `Guardar decisión para ${candidate.data_uri}`}
                              </button>
                            </form>
                            {candidateErrors[candidate.id] && (
                              <p className="mt-2 text-sm text-red-700" role="alert">
                                {candidateErrors[candidate.id]}
                              </p>
                            )}
                            {candidateSuccesses[candidate.id] && (
                              <p className="mt-2 text-sm text-green-700" role="status">
                                {candidateSuccesses[candidate.id]}
                              </p>
                            )}
                          </td>
                        </tr>
                      );
                    })}
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
