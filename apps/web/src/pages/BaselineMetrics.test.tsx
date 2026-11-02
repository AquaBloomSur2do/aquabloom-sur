import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { BaselineMetrics } from './BaselineMetrics';

describe('BaselineMetrics', () => {
  afterEach(() => {
    cleanup();
  });

  it('muestra la comparación, la cantidad evaluada y la condición experimental', async () => {
    const file = new File(
      [
        JSON.stringify({
          experiment_name: 'Modelo piloto',
          condition: 'Sentinel-2, escenas despejadas',
          evaluation_size: 24,
          metrics: [
            {
              name: 'MAE',
              baseline: 1.4,
              experiment: 0.9,
              direction: 'lower_is_better',
            },
            {
              name: 'R²',
              baseline: 0.6,
              experiment: 0.6,
              direction: 'higher_is_better',
            },
          ],
        }),
      ],
      'results.json',
      { type: 'application/json' },
    );

    render(<BaselineMetrics />);
    fireEvent.change(screen.getByLabelText('Cargar resultados en formato JSON'), {
      target: { files: [file] },
    });

    expect(await screen.findByText('Modelo piloto')).toBeInTheDocument();
    expect(
      screen.getByText('Condición experimental: Sentinel-2, escenas despejadas'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Tamaño de evaluación: 24 ejemplos/)).toBeInTheDocument();
    expect(screen.getByRole('row', { name: /MAE/ })).toHaveTextContent(
      'Mejora',
    );
    expect(screen.getByRole('row', { name: /R²/ })).toHaveTextContent(
      'Sin cambio',
    );
  });

  it('rechaza resultados sin tamaño de evaluación válido', async () => {
    const file = new File(
      [
        JSON.stringify({
          experiment_name: 'Modelo piloto',
          condition: 'Condición de prueba',
          evaluation_size: 0,
          metrics: [
            {
              name: 'MAE',
              baseline: 1.4,
              experiment: 0.9,
              direction: 'lower_is_better',
            },
          ],
        }),
      ],
      'results.json',
      { type: 'application/json' },
    );

    render(<BaselineMetrics />);
    fireEvent.change(screen.getByLabelText('Cargar resultados en formato JSON'), {
      target: { files: [file] },
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'evaluation_size debe ser un entero mayor que cero.',
    );
    expect(
      screen.queryByRole('region', { name: 'Resultados experimentales' }),
    ).not.toBeInTheDocument();
  });

  it('muestra error para JSON mal formado', async () => {
    const file = new File(['{not-json'], 'results.json', {
      type: 'application/json',
    });

    render(<BaselineMetrics />);
    fireEvent.change(screen.getByLabelText('Cargar resultados en formato JSON'), {
      target: { files: [file] },
    });

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'El archivo no contiene un JSON válido.',
    );
  });
});
