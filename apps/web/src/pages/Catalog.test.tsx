import '@testing-library/jest-dom/vitest';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import Catalog from './Catalog';
import apiClient from '../services/apiClient';

// Mockeamos el servicio apiClient como exportación por defecto
vi.mock('../services/apiClient', () => ({
  default: {
    get: vi.fn(),
  },
}));

// Función auxiliar para renderizar componentes que dependen de React Router
const renderWithRouter = (ui: React.ReactElement) => {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
};

describe('Suite de Pruebas - Componente Catalog (S2-086)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it('1. Renderiza el estado de carga inicial correctamente', async () => {
    vi.mocked(apiClient.get).mockImplementationOnce(() => new Promise(() => {}));

    renderWithRouter(<Catalog />);

    const skeletonElements = document.querySelectorAll('.animate-pulse');
    expect(skeletonElements.length).toBeGreaterThan(0);
  });

  it('2. Renderiza la lista de resultados cuando la API responde de forma exitosa', async () => {
    const mockResponse = {
      items: [
        { id: '1', name: 'Lago Villarrica', region: 'La Araucanía', status: 'Active' },
        { id: '2', name: 'Lago Calbuco', region: 'Los Lagos', status: 'Active' },
      ],
      page: 1,
      page_size: 10,
      total: 2,
    };

    vi.mocked(apiClient.get).mockResolvedValueOnce(mockResponse);

    renderWithRouter(<Catalog />);

    await waitFor(() => {
      expect(screen.getByText('Lago Villarrica')).toBeInTheDocument();
      expect(screen.getByText('Lago Calbuco')).toBeInTheDocument();
    });
  });

  it('3. Modifica la solicitud a la API al interactuar con los filtros', async () => {
    const mockResponse = {
      items: [{ id: '1', name: 'Lago Villarrica', region: 'La Araucanía', status: 'Active' }],
      page: 1,
      page_size: 10,
      total: 1,
    };
    vi.mocked(apiClient.get).mockResolvedValue(mockResponse);

    renderWithRouter(<Catalog />);

    await waitFor(() => {
      expect(screen.getByText('Lago Villarrica')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText(/buscar lago por nombre/i);
    const user = userEvent.setup();
    await user.type(searchInput, 'Villarrica');

    await waitFor(() => {
      expect(apiClient.get).toHaveBeenCalledWith(
        expect.stringContaining('search=Villarrica')
      );
    });
  });

  it('4. Renderiza el componente o mensaje de error cuando falla la petición', async () => {
    vi.mocked(apiClient.get).mockRejectedValueOnce(new Error('Internal Server Error'));

    renderWithRouter(<Catalog />);

    await waitFor(() => {
      expect(screen.getByText(/error de conexión/i)).toBeInTheDocument();
    });
  });

  it('5. Renderiza el estado vacío cuando la API retorna una lista sin registros', async () => {
    const mockEmptyResponse = {
      items: [],
      page: 1,
      page_size: 10,
      total: 0,
    };

    vi.mocked(apiClient.get).mockResolvedValueOnce(mockEmptyResponse);

    renderWithRouter(<Catalog />);

    await waitFor(() => {
      expect(screen.getByText(/catálogo vacío/i)).toBeInTheDocument();
    });
  });
});

