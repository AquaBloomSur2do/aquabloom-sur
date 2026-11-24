import { useState } from 'react';
import { useInRouterContext, useNavigate } from 'react-router-dom';
import { ApiError } from '../services/apiClient';
import { executionsService } from '../services/executions';

interface StartTrainingButtonProps {
  datasetVersionId: string;
  disabled?: boolean;
}

function RouterAwareTrainingButton({
  datasetVersionId,
  disabled = false,
}: StartTrainingButtonProps) {
  const navigate = useNavigate();
  return (
    <StartTrainingButtonInner
      datasetVersionId={datasetVersionId}
      disabled={disabled}
      onNavigate={(path) => navigate(path)}
    />
  );
}

function StartTrainingButtonInner({
  datasetVersionId,
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
      const response = await executionsService.createJob({
        dataset_version_id: datasetVersionId,
        job_type: 'TRAINING',
        config: {
          target_variable: 'chlorophyll_a',
          required_index: 'NDCI',
        },
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
    <div className="flex flex-col gap-2">
      <button
        type="button"
        onClick={() => void handleStartTraining()}
        disabled={isLoading || disabled || !datasetVersionId}
        className="rounded-md bg-emerald-600 px-4 py-2 font-semibold text-white shadow-sm transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isLoading ? 'Iniciando entrenamiento...' : 'Entrenar Modelo Piloto'}
      </button>
      {error && (
        <p className="text-sm font-medium text-red-700" role="alert">
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
