import { useEffect, useState } from 'react';
import { getPreparedInputs } from '../../services/ingestionService';
import type { PreparedInput } from '../../types/ingestion';

export function PreparedInputsTable() {
  const [inputs, setInputs] = useState<PreparedInput[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedInput, setSelectedInput] = useState<PreparedInput | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    getPreparedInputs()
      .then((data) => {
        if (active) {
          setInputs(data);
        }
      })
      .catch((loadError: unknown) => {
        console.error('No se pudieron cargar los insumos preparados.', loadError);
        if (active) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : 'No se pudieron cargar los insumos preparados.',
          );
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, []);

  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Origen / Source Key</th>
              <th>ID Importación</th>
              <th>Fecha</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4}>Cargando insumos...</td>
              </tr>
            ) : error ? (
              <tr>
                <td colSpan={4} role="alert">
                  {error}
                </td>
              </tr>
            ) : inputs.length === 0 ? (
              <tr>
                <td colSpan={4}>No hay insumos preparados</td>
              </tr>
            ) : (
              inputs.map((input) => (
                <tr key={input.id}>
                  <td>
                    <span className="cell-title">{input.source_key}</span>
                  </td>
                  <td>{input.original_import_id}</td>
                  <td>
                    <span className="cell-sub">
                      {new Date(input.created_at).toLocaleDateString()}
                    </span>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setSelectedInput(input)}
                    >
                      Ver Detalles
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <div className={`drawer ${selectedInput ? 'show' : ''}`}>
        <div className="drawer-head">
          <h3>Detalles del Insumo</h3>
          <button
            type="button"
            className="icon-btn"
            onClick={() => setSelectedInput(null)}
          >
            X
          </button>
        </div>
        <div className="drawer-body">
          <div className="detail-grid">
            {selectedInput &&
              Object.entries(selectedInput.metadata).map(([key, value]) => (
                <div className="detail" key={key}>
                  <span>{key}</span>
                  <b>{String(value)}</b>
                </div>
              ))}
          </div>
        </div>
      </div>
    </>
  );
}
