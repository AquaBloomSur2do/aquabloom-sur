import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { PageState } from './PageState';

afterEach(cleanup);

describe('PageState', () => {
  it('renderiza estado de carga accesible', () => {
    render(<PageState variant="loading" message="Cargando datos..." />);

    expect(screen.getByRole('status')).toHaveTextContent('Cargando datos...');
  });

  it('renderiza estado vacío', () => {
    render(<PageState variant="empty" title="Sin resultados" message="No hay registros." />);

    expect(screen.getByText('Sin resultados')).toBeInTheDocument();
  });

  it('permite reintentar un error', async () => {
    const onRetry = vi.fn();
    render(<PageState variant="error" message="La API no respondió." onRetry={onRetry} />);

    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('renderiza acceso denegado sin ofrecer reintento', () => {
    render(<PageState variant="forbidden" message="No tienes permisos." />);

    expect(screen.getByRole('alert')).toHaveTextContent('Acceso denegado');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
