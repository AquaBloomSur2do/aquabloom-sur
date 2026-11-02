import { useState } from 'react';

type MetricDirection = 'lower_is_better' | 'higher_is_better';

interface MetricComparison {
  name: string;
  baseline: number;
  experiment: number;
  direction: MetricDirection;
}

interface BaselineComparison {
  experiment_name: string;
  condition: string;
  evaluation_size: number;
  metrics: MetricComparison[];
}

const MAX_FILE_SIZE = 1024 * 1024;
const numberFormatter = new Intl.NumberFormat('es-CL', {
  maximumSignificantDigits: 6,
});

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function parseBaselineComparison(value: unknown): BaselineComparison {
  if (!isRecord(value)) {
    throw new Error('El JSON debe contener un objeto de resultados.');
  }
  if (
    typeof value.experiment_name !== 'string' ||
    !value.experiment_name.trim()
  ) {
    throw new Error('Indica el nombre del experimento.');
  }
  if (typeof value.condition !== 'string' || !value.condition.trim()) {
    throw new Error('Indica la condición experimental.');
  }
  if (
    typeof value.evaluation_size !== 'number' ||
    !Number.isInteger(value.evaluation_size) ||
    value.evaluation_size <= 0
  ) {
    throw new Error('evaluation_size debe ser un entero mayor que cero.');
  }
  if (!Array.isArray(value.metrics) || value.metrics.length === 0) {
    throw new Error('Incluye al menos una métrica para comparar.');
  }

  const metricNames = new Set<string>();
  const metrics = value.metrics.map((metric, index): MetricComparison => {
    if (!isRecord(metric)) {
      throw new Error(`La métrica ${index + 1} debe ser un objeto.`);
    }

    const name =
      typeof metric.name === 'string' ? metric.name.trim() : '';
    if (!name) {
      throw new Error(`La métrica ${index + 1} no tiene nombre.`);
    }
    if (metricNames.has(name.toLocaleLowerCase())) {
      throw new Error(`La métrica "${name}" está repetida.`);
    }
    metricNames.add(name.toLocaleLowerCase());

    if (
      typeof metric.baseline !== 'number' ||
      !Number.isFinite(metric.baseline) ||
      typeof metric.experiment !== 'number' ||
      !Number.isFinite(metric.experiment)
    ) {
      throw new Error(
        `La métrica "${name}" debe tener valores numéricos finitos para baseline y experimento.`,
      );
    }
    if (
      metric.direction !== 'lower_is_better' &&
      metric.direction !== 'higher_is_better'
    ) {
      throw new Error(
        `La métrica "${name}" debe indicar direction como lower_is_better o higher_is_better.`,
      );
    }

    return {
      name,
      baseline: metric.baseline,
      experiment: metric.experiment,
      direction: metric.direction,
    };
  });

  return {
    experiment_name: value.experiment_name.trim(),
    condition: value.condition.trim(),
    evaluation_size: value.evaluation_size,
    metrics,
  };
}

function formatNumber(value: number): string {
  return numberFormatter.format(value);
}

function getMetricOutcome(metric: MetricComparison) {
  if (metric.experiment === metric.baseline) {
    return { label: 'Sin cambio', className: 'text-gray-700' };
  }

  const improved =
    metric.direction === 'lower_is_better'
      ? metric.experiment < metric.baseline
      : metric.experiment > metric.baseline;

  return improved
    ? { label: 'Mejora', className: 'text-green-700' }
    : { label: 'Empeora', className: 'text-red-700' };
}

export function BaselineMetrics() {
  const [comparison, setComparison] = useState<BaselineComparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = async (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;

    setComparison(null);
    setError(null);
    if (file.size > MAX_FILE_SIZE) {
      setError('El archivo supera el límite de 1 MiB.');
      return;
    }

    try {
      const contents: unknown = JSON.parse(await file.text());
      setComparison(parseBaselineComparison(contents));
    } catch (caught) {
      setError(
        caught instanceof SyntaxError
          ? 'El archivo no contiene un JSON válido.'
          : caught instanceof Error
          ? caught.message
          : 'No se pudo leer el archivo de resultados.',
      );
    }
  };

  return (
    <main className="mx-auto w-full max-w-6xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">
          Métricas frente al baseline
        </h1>
        <p className="mt-1 text-sm text-gray-600">
          Compara los resultados experimentales con su baseline e identifica el
          tamaño de evaluación y la condición usada.
        </p>
      </header>

      <section className="space-y-4 rounded-lg border border-gray-200 bg-white p-5">
        <div>
          <label
            htmlFor="baseline-results-file"
            className="block text-sm font-medium text-gray-700"
          >
            Cargar resultados en formato JSON
          </label>
          <input
            id="baseline-results-file"
            type="file"
            accept=".json,application/json"
            onChange={(event) => void handleFileChange(event)}
            className="mt-2 block w-full text-sm text-gray-700 file:mr-4 file:rounded-md file:border-0 file:bg-blue-50 file:px-4 file:py-2 file:font-semibold file:text-blue-700 hover:file:bg-blue-100"
          />
          <p className="mt-2 text-xs text-gray-500">
            El archivo se valida y procesa localmente; no se envía al servidor.
            Tamaño máximo: 1 MiB.
          </p>
        </div>

        <details className="text-sm text-gray-700">
          <summary className="cursor-pointer font-medium">
            Formato requerido
          </summary>
          <ul className="mt-2 list-inside list-disc space-y-1">
            <li>
              <code>experiment_name</code>: nombre del experimento.
            </li>
            <li>
              <code>condition</code>: condición experimental evaluada.
            </li>
            <li>
              <code>evaluation_size</code>: cantidad de ejemplos evaluados.
            </li>
            <li>
              <code>metrics</code>: lista de métricas con <code>name</code>,{' '}
              <code>baseline</code>, <code>experiment</code> y{' '}
              <code>direction</code> (<code>lower_is_better</code> o{' '}
              <code>higher_is_better</code>).
            </li>
          </ul>
        </details>

        {error && (
          <p className="text-sm text-red-700" role="alert">
            {error}
          </p>
        )}
      </section>

      {!comparison && !error && (
        <p className="rounded-lg border border-dashed border-gray-300 bg-white p-6 text-sm text-gray-600">
          Carga un archivo de resultados para ver la comparación. Aún no se han
          cargado métricas.
        </p>
      )}

      {comparison && (
        <section
          aria-label="Resultados experimentales"
          className="space-y-4 rounded-lg border border-gray-200 bg-white p-5"
        >
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                {comparison.experiment_name}
              </h2>
              <p className="mt-1 text-sm text-gray-600">
                Condición experimental: {comparison.condition}
              </p>
            </div>
            <p className="rounded-md bg-blue-50 px-3 py-2 text-sm font-medium text-blue-900">
              Tamaño de evaluación:{' '}
              {numberFormatter.format(comparison.evaluation_size)} ejemplos
            </p>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-left text-sm">
              <caption className="sr-only">
                Comparación de métricas contra el baseline
              </caption>
              <thead className="bg-gray-50 text-xs uppercase text-gray-600">
                <tr>
                  <th scope="col" className="px-4 py-3">
                    Métrica
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Baseline
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Experimento
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Diferencia
                  </th>
                  <th scope="col" className="px-4 py-3">
                    Comparación
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {comparison.metrics.map((metric) => {
                  const difference = metric.experiment - metric.baseline;
                  const outcome = getMetricOutcome(metric);
                  return (
                    <tr key={metric.name}>
                      <th
                        scope="row"
                        className="whitespace-nowrap px-4 py-3 font-medium text-gray-900"
                      >
                        {metric.name}
                      </th>
                      <td className="whitespace-nowrap px-4 py-3 text-gray-700">
                        {formatNumber(metric.baseline)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-gray-700">
                        {formatNumber(metric.experiment)}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-gray-700">
                        {difference > 0 ? '+' : ''}
                        {formatNumber(difference)}
                      </td>
                      <td
                        className={`whitespace-nowrap px-4 py-3 font-semibold ${outcome.className}`}
                      >
                        {outcome.label}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </main>
  );
}
