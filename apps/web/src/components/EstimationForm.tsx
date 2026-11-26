import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { modelsService } from '../services/models';
import { executionsService } from '../services/executions';
import type { ModelConfig } from '../types/models';
import { ApiError } from '../services/apiClient';

interface EstimationFormProps {
  lakeId: string;
  sceneId: string;
}

export function EstimationForm({ lakeId, sceneId }: EstimationFormProps) {
  const [models, setModels] = useState<ModelConfig[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [isLoadingModels, setIsLoadingModels] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  useEffect(() => {
    let active = true;

    const loadModels = async () => {
      setIsLoadingModels(true);
      setError(null);
      try {
        const fetchedModels = await modelsService.getModelsByLake(lakeId);
        if (active) {
          const aptModels = fetchedModels.filter(
            (m) => m.status === 'EXPERIMENTAL' || m.status === 'VALIDATED'
          );
          setModels(aptModels);
          if (aptModels.length > 0) {
            setSelectedModel(aptModels[0].id);
          }
        }
      } catch (err: unknown) {
        if (active) {
          setError(
            err instanceof ApiError
              ? err.message
              : err instanceof Error
                ? err.message
                : 'Error al cargar los modelos disponibles.'
          );
        }
      } finally {
        if (active) setIsLoadingModels(false);
      }
    };

    void loadModels();

    return () => {
      active = false;
    };
  }, [lakeId]);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!selectedModel || !sceneId || isSubmitting) return;

    setIsSubmitting(true);
    setError(null);

    try {
      const response = await executionsService.createJob({
        job_type: 'ESTIMATION',
        config: {
          model_id: selectedModel,
          scene_id: sceneId,
        },
      });
      navigate(`/estimations/${response.job_id}`);
    } catch (err: unknown) {
      setError(
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Error al iniciar la estimación.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoadingModels) {
    return (
      <div className="card card-body" role="status">
        <p className="subtitle">Cargando modelos compatibles...</p>
      </div>
    );
  }

  if (error && models.length === 0) {
    return (
      <div className="status-banner danger" role="alert">
        {error}
      </div>
    );
  }

  if (models.length === 0) {
    return (
      <div className="status-banner warning" role="status">
        No hay modelos validados ni experimentales disponibles para este lago.
      </div>
    );
  }

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="card">
      <div className="card-head">
        <div>
          <h3>Configuración de Estimación</h3>
          <div className="card-note">
            Selecciona un modelo experimental o validado compatible con la escena satelital.
          </div>
        </div>
      </div>

      <div className="card-body">
        {error && (
          <div className="status-banner danger" role="alert">
            {error}
          </div>
        )}

        <div>
          <label htmlFor="model-select" className="label">
            Modelo Científico
          </label>
          <select
            id="model-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="control"
            required
          >
            <option value="" disabled>
              Seleccione un modelo...
            </option>
            {models.map((model) => (
              <option key={model.id} value={model.id}>
                {model.name} v{model.version} ({model.target_variable} -{' '}
                {model.status})
              </option>
            ))}
          </select>
          <p className="card-note">
            Debe seleccionar un modelo cuyo índice requerido y variable objetivo
            coincidan con las observaciones de la escena.
          </p>
        </div>

        <button
          type="submit"
          disabled={isSubmitting || !selectedModel}
          className="btn btn-primary"
        >
          {isSubmitting ? 'Iniciando estimación...' : 'Generar Estimación'}
        </button>
      </div>
    </form>
  );
}
