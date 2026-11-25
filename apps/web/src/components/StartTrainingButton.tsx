import { useState } from 'react';
import { useInRouterContext, useNavigate } from 'react-router-dom';
import { ApiError } from '../services/apiClient';
import {
  executionsService,
  setActiveOrganizationId,
} from '../services/executions';

interface StartTrainingButtonProps {
  datasetVersionId: string;
  datasetId?: string;
  organizationId?: string;
  disabled?: boolean;
}

function RouterAwareTrainingButton(props: StartTrainingButtonProps) {
  const navigate = useNavigate();
  return (
    <StartTrainingButtonInner
      {...props}
      onNavigate={(path) => navigate(path)}
    />
  );
}

function StartTrainingButtonInner({
  datasetVersionId,
  datasetId,
  organizationId,
  disabled = false,
  onNavigate,
}: StartTrainingButtonProps & { onNavigate: (path: string) => void }) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartTraining = async () => {
    if (!datasetVersionId || isLoading || disabled) return;

    setIsLoading(true);
    setError(null);
    try {
      if (organizationId) {
        setActiveOrganizationId(organizationId);
      }

      const config: Record<string, unknown> = {
        target_variable: 'chlorophyll_a',
        required_index: 'NDCI',
      };
      if (datasetId) {
        config.dataset_id = datasetId;
        config.version_id = datasetVersionId;
      }

      const response = await executionsService.createJob({
        dataset_version_id: datasetVersionId,
        job_type: 'TRAINING',
        config,
      });

      onNavigate(`/scientific/jobs/${response.job_id}`);
    } catch (err: unknown) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : 'Error al iniciar el entrenamiento científico.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ display: 'grid', gap: '8px' }}>
      <button
        type="button"
        onClick={() => void handleStartTraining()}
        disabled={isLoading || disabled || !datasetVersionId}
        className="btn btn-primary"
      >
        {isLoading ? 'Iniciando entrenamiento...' : 'Entrenar Modelo Piloto'}
      </button>
      {error && (
        <p className="status-banner danger" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function StartTrainingButton(props: StartTrainingButtonProps) {
  const inRouter = useInRouterContext();
  if (inRouter) {
    return <RouterAwareTrainingButton {...props} />;
  }
  return (
    <StartTrainingButtonInner
      {...props}
      onNavigate={(path) => {
        window.history.pushState({}, '', path);
      }}
    />
  );
}


