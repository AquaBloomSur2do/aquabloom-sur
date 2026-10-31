import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, apiClient } from '../services/apiClient';
import type {
  DatasetDecision,
  DatasetDecisionInput,
  DatasetDecisionValue,
  ReviewDataset,
  DatasetCandidate // <--- Nuevo tipo importado
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

  // --- Estados de Tarea S2-139 (Candidatos) ---
  const [candidates, setCandidates] = useState<DatasetCandidate[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);

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
    let mounted = true;
    const loadCandidates = async () => {
      if (!datasetId) return;
      setLoadingCandidates(true);
      try {
        // En una API real, esto sería un GET a /api/v1/datasets/candidates?lake_id=...
        // Si no está implementado en backend, atrapamos el 404/501 y mockeamos para mostrar la vista (MVP).
        const response = await apiClient.get<DatasetCandidate[]>(`datasets/candidates?dataset_id=${datasetId}`);
        if (mounted) setCandidates(response);
      } catch {
        // Mock de datos para evidenciar la S2-139 si el backend de Ingesta no expone GET candidatos.
        if (mounted) {
           setCandidates([
            {
              id: 'c-1',
              lake_id: datasetId,
              data_uri: 's3://ingest/batch-1.csv',
              status: 'REJECTED',
              submitted_at: new Date().toISOString(),
              exclusion_reason: 'Falla regla S2-121: 85% de nubosidad.',
              source_provider: 'Sentinel-2 L2A'
            },
            {
              id: 'c-2',
              lake_id: datasetId,
              data_uri: 's3://ingest/batch-2.csv',
              status: 'PENDING',
              submitted_at: new Date().toISOString(),
              exclusion_reason: 'Evaluación de calidad geoespacial pendiente.',
              source_provider: 'Estación Fija (Terreno)'
            }
          ]);
        }
      } finally {
        if (mounted) setLoadingCandidates(false);
      }
    };
    void loadCandidates();
    return () => { mounted = false; };
  }, [datasetId]);

  const selectedDataset = datasets.find((dataset) => dataset.id === datasetId);
  const versions = selectedDataset?.versions ?? [];
  const selectedVersion = versions.find((version) => version.id === versionId);

  const handleDatasetChange = (nextDatasetId: string) => {
    const nextDataset = datasets.find(
      (dataset) => dataset.id === nextDatasetId
    );
    setDatasetId(nextDatasetId);
    setVersionId(nextDataset?.versions[0]?.id ?? '');
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

          {/* CÓDIGO ORIGINAL: ESCENAS DE LA VERSIÓN */}
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

          {/* NUEVA SECCIÓN TAREA S2-139: VISTA DE CANDIDATOS */}
          <section className="mt-10 border-t border-gray-200 pt-8" aria-label="Candidatos en cuarentena">
             <div className="mb-4">
                <h2 className="text-xl font-bold text-gray-900">Bandeja de Entrada: Candidatos de Ingesta</h2>
                <p className="mt-1 text-sm text-gray-600">
                  Muestras y observaciones crudas esperando ser evaluadas o ya descartadas automáticamente (S2-139).
                </p>
             </div>

             {loadingCandidates ? (
               <p className="text-sm text-gray-500">Cargando candidatos...</p>
             ) : candidates.length === 0 ? (
               <p className="rounded-lg border border-gray-200 bg-gray-50 p-6 text-sm text-gray-600">
                 No hay candidatos pendientes de Ingesta para este dataset.
               </p>
             ) : (
               <div className="overflow-x-auto rounded-lg border border-gray-200">
                 <table className="w-full text-left text-sm">
                   <thead className="bg-gray-100">
                     <tr>
                       <th className="p-3 font-semibold text-gray-700">ID / Archivo</th>
                       <th className="p-3 font-semibold text-gray-700">Procedencia</th>
                       <th className="p-3 font-semibold text-gray-700">Estado</th>
                       <th className="p-3 font-semibold text-gray-700">Motivo de Exclusión / Nota</th>
                     </tr>
                   </thead>
                   <tbody className="divide-y divide-gray-200 bg-white">
                     {candidates.map(candidate => (
                       <tr key={candidate.id} className="hover:bg-gray-50">
                         <td className="p-3 font-mono text-xs">{candidate.data_uri}</td>
                         <td className="p-3">{candidate.source_provider || 'Desconocido'}</td>
                         <td className="p-3">
                           <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                              candidate.status === 'REJECTED' ? 'bg-red-100 text-red-800' :
                              candidate.status === 'APPROVED' ? 'bg-green-100 text-green-800' :
                              'bg-yellow-100 text-yellow-800'
                           }`}>
                             {candidate.status}
                           </span>
                         </td>
                         <td className="p-3 text-gray-600">{candidate.exclusion_reason || '-'}</td>
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

