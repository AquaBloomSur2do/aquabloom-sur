import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { SatelliteQueryPanel } from './SatelliteQueryPanel';
import { apiClient } from '../services/apiClient';

vi.mock('../services/apiClient', () => ({
  apiClient: {
    get: vi.fn(),
  },
}));

const mockedApiClientGet = apiClient.get as ReturnType<typeof vi.fn>;

describe('SatelliteQueryPanel', () => {
  const mockLakeId = 'lago-123';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('muestra estado de carga inicial', () => {
    mockedApiClientGet.mockImplementation(() => new Promise(() => {}));
    render(<SatelliteQueryPanel lakeId={mockLakeId} />);
    expect(screen.getByRole('status').textContent).toMatch(/cargando/i);
  });

  it('muestra mensaje vacío cuando no hay resultados', async () => {
    mockedApiClientGet.mockResolvedValue([]);
    render(<SatelliteQueryPanel lakeId={mockLakeId} />);
    
    await waitFor(() => {
      expect(screen.getByText(/no se encontraron escenas/i)).toBeTruthy();
    });
  });

  it('muestra error y permite reintentar la consulta con éxito', async () => {
    const user = userEvent.setup();
    mockedApiClientGet
      .mockRejectedValueOnce(new Error('Network error'))
      .mockResolvedValueOnce([{ id: 'escena-1', lake_id: mockLakeId, capture_date: '2026-10-28', cloud_coverage: 5 }]);

    render(<SatelliteQueryPanel lakeId={mockLakeId} />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeTruthy();
    });

    const retryButton = screen.getByRole('button', { name: /reintentar/i });
    await user.click(retryButton);

    await waitFor(() => {
      expect(mockedApiClientGet).toHaveBeenCalledTimes(2);
      expect(screen.getByText(/escena-1/i)).toBeTruthy();
    });
  });
});
