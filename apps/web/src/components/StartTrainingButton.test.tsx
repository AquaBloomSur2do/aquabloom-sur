import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { executionsService } from '../services/executions';
import { StartTrainingButton } from './StartTrainingButton';

const { mockNavigate } = vi.hoisted(() => ({
  mockNavigate: vi.fn(),
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

describe('StartTrainingButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renderiza el botón correctamente', () => {
    render(
      <MemoryRouter>
        <StartTrainingButton datasetVersionId="version-123" />
      </MemoryRouter>
    );
    expect(
      screen.getByRole('button', { name: /entrenar modelo piloto/i })
    ).toBeInTheDocument();
  });

  it('envía el trabajo a la API y navega a su estado sin bloquear la interfaz', async () => {
    vi.mocked(executionsService.createJob).mockResolvedValueOnce({
      job_id: 'job-123',
      status: 'PENDING',
      message: 'Job accepted',
    });

    render(
      <MemoryRouter>
        <StartTrainingButton datasetVersionId="version-123" />
      </MemoryRouter>
    );

    fireEvent.click(
      screen.getByRole('button', { name: /entrenar modelo piloto/i })
    );

    await waitFor(() => {
      expect(executionsService.createJob).toHaveBeenCalledWith({
        dataset_version_id: 'version-123',
        job_type: 'TRAINING',
        config: {
          target_variable: 'chlorophyll_a',
          required_index: 'NDCI',
        },
      });
      expect(mockNavigate).toHaveBeenCalledWith('/scientific/jobs/job-123');
    });
  });

  it('muestra alerta de error si falla la creación del trabajo', async () => {
    vi.mocked(executionsService.createJob).mockRejectedValueOnce(
      new Error('No se pudo encolar el entrenamiento.')
    );

    render(
      <MemoryRouter>
        <StartTrainingButton datasetVersionId="version-123" />
      </MemoryRouter>
    );

    fireEvent.click(
      screen.getByRole('button', { name: /entrenar modelo piloto/i })
    );

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo encolar el entrenamiento.'
    );
  });
});
