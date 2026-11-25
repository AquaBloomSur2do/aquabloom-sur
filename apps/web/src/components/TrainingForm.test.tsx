import '@testing-library/jest-dom/vitest';
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '../services/apiClient';
import { executionsService } from '../services/executions';
import type { ReviewDataset } from '../types/dataset';
import { TrainingForm } from './TrainingForm';

const { mockNavigate } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
}));

vi.mock('../services/apiClient', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/apiClient')>();
  return {
    ...actual,
    apiClient: {
      get: vi.fn(),
    },
  };
});

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

const mockDatasets: ReviewDataset[] = [
  {
    id: 'dataset-villarrica',
    organization_id: 'org-1',
    name: 'Dataset Lago Villarrica',
    description: 'Serie piloto 2026',
    created_at: '2026-10-01T00:00:00Z',
    versions: [
      {
        id: 'ver-draft-1',
        dataset_id: 'dataset-villarrica',
        version_number: 1,
        state: 'DRAFT',
        status: 'draft',
        created_at: '2026-10-02T00:00:00Z',
        memberships: [],
      },
      {
        id: 'ver-approved-2',
        dataset_id: 'dataset-villarrica',
        version_number: 2,
        state: 'APPROVED',
        status: 'approved',
        created_at: '2026-10-05T00:00:00Z',
        memberships: [],
      },
      {
        id: 'ver-published-3',
        dataset_id: 'dataset-villarrica',
        version_number: 3,
        state: 'PUBLISHED',
        status: 'published',
        created_at: '2026-10-10T00:00:00Z',
        published_at: '2026-10-11T00:00:00Z',
        memberships: [],
      },
    ],
  },
];

describe('TrainingForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('filtra solo versiones publicadas y no ofrece algoritmos ni parámetros fuera del piloto', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockDatasets);

    render(
      <MemoryRouter>
        <TrainingForm />
      </MemoryRouter>,
    );

    const select = await screen.findByLabelText(
      /Versión autorizada del dataset/i,
    );
    expect(select).toBeInTheDocument();
    expect(
      screen.getByRole('option', {
        name: /Dataset Lago Villarrica — Versión v3 \(Publicada\)/i,
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Versión v1/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Versión v2/i)).not.toBeInTheDocument();

    // Solo existe el selector de versión autorizada; ningún control de algoritmo o hiperparámetros.
    expect(screen.getAllByRole('combobox')).toHaveLength(1);
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(
      screen.getByText(/Regresión lineal simple \(OLS\)/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Deshabilitada \(configuración fija\)/i),
    ).toBeInTheDocument();
  });

  it('muestra advertencia cuando no existen versiones autorizadas', async () => {
    vi.mocked(apiClient.get).mockResolvedValue([
      {
        ...mockDatasets[0],
        versions: [mockDatasets[0].versions[0], mockDatasets[0].versions[1]],
      },
    ]);

    render(
      <MemoryRouter>
        <TrainingForm />
      </MemoryRouter>,
    );

    expect(
      await screen.findByText(
        /No hay versiones publicadas y autorizadas disponibles/i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: /Iniciar Entrenamiento Piloto/i }),
    ).not.toBeInTheDocument();
  });

  it('envía el trabajo de entrenamiento con configuración fija del piloto y navega al seguimiento', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockDatasets);
    vi.mocked(executionsService.createJob).mockResolvedValue({
      job_id: 'job-train-777',
      status: 'queued',
    });

    render(
      <MemoryRouter>
        <TrainingForm />
      </MemoryRouter>,
    );

    const submitButton = await screen.findByRole('button', {
      name: /Iniciar Entrenamiento Piloto/i,
    });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(executionsService.createJob).toHaveBeenCalledWith({
        dataset_version_id: 'ver-published-3',
        job_type: 'TRAINING',
        config: {
          dataset_id: 'dataset-villarrica',
          version_id: 'ver-published-3',
          model_family: 'linear_regression',
          solver: 'ordinary_least_squares',
          fit_intercept: true,
          hyperparameter_search: false,
          target_variable: 'chlorophyll_a',
          unit: 'ug/L',
          required_index: 'NDCI',
        },
      });
    });

    expect(mockNavigate).toHaveBeenCalledWith('/scientific/jobs/job-train-777');
  });

  it('muestra alerta accesible si falla la carga de versiones autorizadas', async () => {
    vi.mocked(apiClient.get).mockRejectedValue(
      new Error('No se pudo consultar el catálogo de versiones.'),
    );

    render(
      <MemoryRouter>
        <TrainingForm />
      </MemoryRouter>,
    );

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(
      'No se pudo consultar el catálogo de versiones.',
    );
  });

  it('muestra alerta accesible y bloquea la navegación si falla la creación del trabajo', async () => {
    vi.mocked(apiClient.get).mockResolvedValue(mockDatasets);
    vi.mocked(executionsService.createJob).mockRejectedValue(
      new Error('Solo se pueden entrenar versiones publicadas.'),
    );

    render(
      <MemoryRouter>
        <TrainingForm />
      </MemoryRouter>,
    );

    const submitButton = await screen.findByRole('button', {
      name: /Iniciar Entrenamiento Piloto/i,
    });
    fireEvent.click(submitButton);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(
      'Solo se pueden entrenar versiones publicadas.',
    );
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});

