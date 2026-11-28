import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { modelsService } from '../services/models';
import { executionsService } from '../services/executions';
import { EstimationForm } from './EstimationForm';

const { mockNavigate } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
}));

vi.mock('../services/models', () => ({
  modelsService: {
    getModelsByLake: vi.fn(),
  },
}));

vi.mock('../services/executions', () => ({
  executionsService: {
    createJob: vi.fn(),
  },
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('EstimationForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('filtra modelos aptos y renderiza las opciones compatibles', async () => {
    vi.mocked(modelsService.getModelsByLake).mockResolvedValue([
      {
        id: 'model-exp-1',
        name: 'NDCI Regresión Piloto',
        version: '1.0.0',
        target_variable: 'chlorophyll_a',
        unit: 'ug/L',
        required_index: 'NDCI',
        status: 'EXPERIMENTAL',
        created_at: '2026-11-10T00:00:00Z',
      },
      {
        id: 'model-dep-2',
        name: 'Modelo Obsoleto',
        version: '0.1.0',
        target_variable: 'chlorophyll_a',
        unit: 'ug/L',
        required_index: 'NDCI',
        status: 'DEPRECATED',
        created_at: '2026-10-01T00:00:00Z',
      },
    ]);

    render(
      <MemoryRouter>
        <EstimationForm lakeId="lake-villarrica" sceneId="scene-s2-01" />
      </MemoryRouter>
    );

    const select = await screen.findByLabelText(/Modelo Científico/i);
    expect(select).toBeInTheDocument();
    expect(screen.getByText(/NDCI Regresión Piloto v1\.0\.0/i)).toBeInTheDocument();
    expect(screen.queryByText(/Modelo Obsoleto/i)).not.toBeInTheDocument();
  });

  it('muestra advertencia cuando no hay modelos compatibles para el lago', async () => {
    vi.mocked(modelsService.getModelsByLake).mockResolvedValue([]);

    render(
      <MemoryRouter>
        <EstimationForm lakeId="lake-villarrica" sceneId="scene-s2-01" />
      </MemoryRouter>
    );

    expect(
      await screen.findByText(
        /No hay modelos validados ni experimentales disponibles para este lago/i
      )
    ).toBeInTheDocument();
  });

  it('envía el trabajo de estimación via executionsService y navega al estado', async () => {
    vi.mocked(modelsService.getModelsByLake).mockResolvedValue([
      {
        id: 'model-exp-1',
        name: ' NDCI Regresión Piloto ',
        version: '1.0.0',
        model_version_id: ' 11111111-1111-4111-8111-111111111111 ',
        training_job_id: ' 22222222-2222-4222-8222-222222222222 ',
        dataset_id: ' 33333333-3333-4333-8333-333333333333 ',
        dataset_version_id: ' 44444444-4444-4444-8444-444444444444 ',
        target_variable: 'chlorophyll_a',
        unit: 'ug/L',
        required_index: 'NDCI',
        status: 'EXPERIMENTAL',
        created_at: '2026-11-10T00:00:00Z',
      },
    ]);
    vi.mocked(executionsService.createJob).mockResolvedValue({
      job_id: 'job-est-999',
      status: 'queued',
    });

    render(
      <MemoryRouter>
        <EstimationForm lakeId="lake-villarrica" sceneId="scene-s2-01" />
      </MemoryRouter>
    );

    const submitButton = await screen.findByRole('button', {
      name: /Generar Estimación/i,
    });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(executionsService.createJob).toHaveBeenCalledWith({
        job_type: 'ESTIMATION',
        config: {
          model_id: 'model-exp-1',
          scene_id: 'scene-s2-01',
          model_name: 'NDCI Regresión Piloto',
          model_version_id: '11111111-1111-4111-8111-111111111111',
          training_job_id: '22222222-2222-4222-8222-222222222222',
          dataset_id: '33333333-3333-4333-8333-333333333333',
          dataset_version_id: '44444444-4444-4444-8444-444444444444',
        },
      });
    });

    expect(mockNavigate).toHaveBeenCalledWith('/scientific/jobs/job-est-999');
  });

  it('omite metadatos de trazabilidad vacíos después de normalizarlos', async () => {
    vi.mocked(modelsService.getModelsByLake).mockResolvedValue([
      {
        id: 'model-exp-1',
        name: '   ',
        version: '1.0.0',
        model_version_id: '   ',
        training_job_id: ' ',
        dataset_id: '  ',
        dataset_version_id: '\t',
        target_variable: 'chlorophyll_a',
        unit: 'ug/L',
        required_index: 'NDCI',
        status: 'EXPERIMENTAL',
        created_at: '2026-11-10T00:00:00Z',
      },
    ]);
    vi.mocked(executionsService.createJob).mockResolvedValue({
      job_id: 'job-est-1000',
      status: 'queued',
    });

    render(
      <MemoryRouter>
        <EstimationForm lakeId="lake-villarrica" sceneId="scene-s2-01" />
      </MemoryRouter>
    );

    fireEvent.click(
      await screen.findByRole('button', { name: /Generar Estimación/i })
    );

    await waitFor(() => {
      expect(executionsService.createJob).toHaveBeenCalledWith({
        job_type: 'ESTIMATION',
        config: {
          model_id: 'model-exp-1',
          scene_id: 'scene-s2-01',
        },
      });
    });
  });

  it('muestra alerta accesible si falla la creación del trabajo', async () => {
    vi.mocked(modelsService.getModelsByLake).mockResolvedValue([
      {
        id: 'model-val-1',
        name: 'NDCI Validado',
        version: '2.0.0',
        target_variable: 'chlorophyll_a',
        unit: 'ug/L',
        required_index: 'NDCI',
        status: 'VALIDATED',
        created_at: '2026-11-12T00:00:00Z',
      },
    ]);
    vi.mocked(executionsService.createJob).mockRejectedValue(
      new Error('Observaciones incompatibles con el índice requerido.')
    );

    render(
      <MemoryRouter>
        <EstimationForm lakeId="lake-villarrica" sceneId="scene-s2-01" />
      </MemoryRouter>
    );

    const submitButton = await screen.findByRole('button', {
      name: /Generar Estimación/i,
    });
    fireEvent.click(submitButton);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(
      'Observaciones incompatibles con el índice requerido.'
    );
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
