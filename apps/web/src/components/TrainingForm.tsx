import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { ApiError, apiClient } from '../services/apiClient';
import { executionsService } from '../services/executions';
import type { JobResponse } from '../services/executions';
import type { DatasetVersion, ReviewDataset } from '../types/dataset';

const PILOT_TRAINING_CONFIG = {
  model_family: 'linear_regression',
  solver: 'ordinary_least_squares',
  fit_intercept: true,
  hyperparameter_search: false,
  target_variable: 'chlorophyll_a',
  unit: 'ug/L',
  required_index: 'NDCI',
} as const;

interface AuthorizedVersionOption {
  datasetId: string;
  datasetName: string;
  versionId: string;
  versionNumber: number;
  publishedAt: string | null;
}

interface TrainingFormProps {
  datasetId?: string;
  onJobCreated?: (response: JobResponse) => void;
}

function isAuthorizedVersion(version: DatasetVersion): boolean {
  const normalizedState = version.state?.trim().toUpperCase();
  const normalizedStatus = version.status.trim().toLowerCase();
  return normalizedState === 'PUBLISHED' || normalizedStatus === 'published';
}

function extractAuthorizedVersions(
  datasets: ReviewDataset[],
  datasetIdFilter?: string,
): AuthorizedVersionOption[] {
  return datasets
    .filter((dataset) => !datasetIdFilter || dataset.id === datasetIdFilter)
    .flatMap((dataset) =>
      dataset.versions.filter(isAuthorizedVersion).map((version) => ({
        datasetId: dataset.id,
        datasetName: dataset.name,
        versionId: version.id,
        versionNumber: version.version_number,
        publishedAt: version.published_at ?? null,
      })),
    );
}

function BannerIcon({ variant }: { variant: 'danger' | 'warning' }) {
  return (
    <svg
      aria-hidden="true"
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ flexShrink: 0 }}
    >
      <circle cx="12" cy="12" r="10" />
      {variant === 'danger' ? (
        <>
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </>
      ) : (
        <>
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
        </>
      )}
    </svg>
  );
}

export function TrainingForm({ datasetId, onJobCreated }: TrainingFormProps) {
  const [authorizedVersions, setAuthorizedVersions] = useState<
    AuthorizedVersionOption[]
  >([]);
  const [selectedVersionId, setSelectedVersionId] = useState<string>('');
  const [isLoadingVersions, setIsLoadingVersions] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  useEffect(() => {
    let active = true;

    const loadAuthorizedVersions = async () => {
      setIsLoadingVersions(true);
      setError(null);
      try {
        const response = await apiClient.get<unknown>('datasets/review');
        if (!Array.isArray(response)) {
          throw new Error(
            'La respuesta de datasets no tiene un formato válido.',
          );
        }

        if (active) {
          const versions = extractAuthorizedVersions(
            response as ReviewDataset[],
            datasetId,
          );
          setAuthorizedVersions(versions);
          setSelectedVersionId(versions[0]?.versionId ?? '');
        }
      } catch (err: unknown) {
        if (active) {
          setAuthorizedVersions([]);
          setSelectedVersionId('');
          setError(
            err instanceof ApiError
              ? err.message
              : err instanceof Error
                ? err.message
                : 'No se pudieron cargar las versiones autorizadas.',
          );
        }
      } finally {
        if (active) setIsLoadingVersions(false);
      }
    };

    void loadAuthorizedVersions();

    return () => {
      active = false;
    };
  }, [datasetId]);

  const selectedVersion = authorizedVersions.find(
    (option) => option.versionId === selectedVersionId,
  );

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedVersion || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await executionsService.createJob({
        dataset_version_id: selectedVersion.versionId,
        job_type: 'TRAINING',
        config: {
          dataset_id: selectedVersion.datasetId,
          version_id: selectedVersion.versionId,
          ...PILOT_TRAINING_CONFIG,
        },
      });

      onJobCreated?.(response);
      navigate(`/scientific/jobs/${response.job_id}`);
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'No se pudo iniciar el entrenamiento científico.',
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoadingVersions) {
    return (
      <div className="card card-body" role="status">
        <p className="subtitle">Cargando versiones autorizadas...</p>
      </div>
    );
  }

  if (error && authorizedVersions.length === 0) {
    return (
      <div className="status-banner danger" role="alert">
        <span
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          <BannerIcon variant="danger" />
          {error}
        </span>
      </div>
    );
  }

  if (authorizedVersions.length === 0) {
    return (
      <div className="status-banner warning" role="status">
        <span
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
        >
          <BannerIcon variant="warning" />
          No hay versiones publicadas y autorizadas disponibles para iniciar el
          entrenamiento piloto.
        </span>
      </div>
    );
  }

  return (
    <form
      onSubmit={(event) => void handleSubmit(event)}
      className="card"
      aria-label="Formulario mínimo de entrenamiento"
    >
      <div className="card-head">
        <div>
          <h2>Configuración de Entrenamiento Piloto</h2>
          <p className="card-note">
            Selecciona una versión oficial publicada. El algoritmo y los
            parámetros permanecen fijos según el alcance del piloto.
          </p>
        </div>
        <span className="badge validated">Alcance piloto fijo</span>
      </div>

      <div className="card-body" style={{ display: 'grid', gap: '18px' }}>
        {error && (
          <div className="status-banner danger" role="alert">
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <BannerIcon variant="danger" />
              {error}
            </span>
          </div>
        )}

        <div>
          <label htmlFor="authorized-version-select" className="label">
            Versión autorizada del dataset
          </label>
          <select
            id="authorized-version-select"
            value={selectedVersionId}
            onChange={(event) => setSelectedVersionId(event.target.value)}
            className="control"
            disabled={isSubmitting}
            required
          >
            <option value="" disabled>
              Seleccione una versión publicada...
            </option>
            {authorizedVersions.map((option) => (
              <option key={option.versionId} value={option.versionId}>
                {option.datasetName} — Versión v{option.versionNumber}{' '}
                (Publicada)
              </option>
            ))}
          </select>
          <p className="card-note">
            Solo se listan versiones congeladas en estado{' '}
            <span className="code-pill">PUBLISHED</span>; borradores y versiones
            pendientes quedan excluidos.
          </p>
        </div>

        <section
          aria-label="Configuración fija del piloto"
          style={{
            padding: '14px 16px',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--line)',
            background: 'var(--ice)',
            display: 'grid',
            gap: '12px',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '8px',
              flexWrap: 'wrap',
            }}
          >
            <h3>Parámetros fijos del piloto (solo lectura)</h3>
            <span className="badge restricted">
              Sin ajuste de hiperparámetros
            </span>
          </div>

          <div className="grid grid-2">
            <div>
              <p className="card-note">Modelo inicial</p>
              <p className="cell-title">Regresión lineal simple (OLS)</p>
            </div>
            <div>
              <p className="card-note">Variable objetivo y unidad</p>
              <p className="cell-title">
                Clorofila-a (<span className="code-pill">chlorophyll_a</span> ·{' '}
                <span className="code-pill">ug/L</span>)
              </p>
            </div>
            <div>
              <p className="card-note">Índice espectral requerido</p>
              <p className="cell-title">
                <span className="code-pill">NDCI</span>
              </p>
            </div>
            <div>
              <p className="card-note">Búsqueda de hiperparámetros</p>
              <p className="cell-title">Deshabilitada (configuración fija)</p>
            </div>
          </div>
        </section>

        <div className="head-actions" style={{ justifyContent: 'flex-end' }}>
          <button
            type="submit"
            disabled={isSubmitting || !selectedVersion}
            className="btn btn-primary"
          >
            {isSubmitting
              ? 'Iniciando entrenamiento...'
              : 'Iniciar Entrenamiento Piloto'}
          </button>
        </div>
      </div>
    </form>
  );
}


