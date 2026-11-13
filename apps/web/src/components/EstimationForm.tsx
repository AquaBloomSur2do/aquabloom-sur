import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { modelsService } from '../services/models';
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
          // Filtrar modelos aptos (Experimentales y Validados)
          const aptModels = fetchedModels.filter(m => 
            m.status === 'EXPERIMENTAL' || m.status === 'VALIDATED'
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedModel || !sceneId) return;

    setIsSubmitting(true);
    setError(null);
    
    try {
      const response = await modelsService.createEstimationJob({
        model_id: selectedModel,
        scene_id: sceneId,
      });
      // Redirigir a la vista de seguimiento del trabajo asíncrono
      navigate(`/scientific/jobs/${response.job_id}`);
    } catch (err: unknown) {
      setError(
        err instanceof ApiError 
          ? err.message 
          : 'Error al iniciar la estimación.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoadingModels) {
    return <div className="p-4 text-gray-500">Cargando modelos compatibles...</div>;
  }

  if (models.length === 0) {
    return (
      <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-800">
        No hay modelos validados ni experimentales disponibles para este lago.
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 p-4 border border-gray-200 rounded-lg bg-white shadow-sm">
      <h3 className="text-lg font-semibold text-gray-800">Configuración de Estimación</h3>
      
      {error && (
        <div className="p-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md" role="alert">
          {error}
        </div>
      )}

      <div>
        <label htmlFor="model-select" className="block text-sm font-medium text-gray-700 mb-1">
          Modelo Científico
        </label>
        <select
          id="model-select"
          value={selectedModel}
          onChange={(e) => setSelectedModel(e.target.value)}
          className="w-full border border-gray-300 rounded-md p-2"
          required
        >
          <option value="" disabled>Seleccione un modelo...</option>
          {models.map(model => (
            <option key={model.id} value={model.id}>
              {model.name} v{model.version} ({model.target_variable} - {model.status})
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-gray-500">
          Debe seleccionar un modelo cuyo índice requerido y variable objetivo coincidan con las observaciones de la escena.
        </p>
      </div>

      <button
        type="submit"
        disabled={isSubmitting || !selectedModel}
        className="w-full bg-blue-600 text-white font-medium py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
      >
        {isSubmitting ? 'Iniciando estimación...' : 'Generar Estimación'}
      </button>
    </form>
  );
}
