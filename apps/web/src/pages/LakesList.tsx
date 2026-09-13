import { Link } from 'react-router-dom';

interface Lake {
  id: string;
  name: string;
  location: string;
  area: number;
}

export function LakesList() {
  // Datos de ejemplo - en una aplicación real, estos vendrían de una API
  const lakes: Lake[] = [
    { id: '1', name: 'Lago Argentino', location: 'Santa Cruz', area: 1468 },
    { id: '2', name: 'Lago Nahuel Huapi', location: 'Río Negro', area: 557 },
    { id: '3', name: 'Lago Viedma', location: 'Santa Cruz', area: 1080 },
    { id: '4', name: 'Lago San Martín', location: 'Santa Cruz', area: 1050 },
  ];

  return (
    <div className="lakes-list-page">
      <h1>Listado de Lagos</h1>
      
      <div className="lakes-container">
        <table className="lakes-table">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Ubicación</th>
              <th>Área (km²)</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {lakes.map((lake) => (
              <tr key={lake.id}>
                <td>{lake.name}</td>
                <td>{lake.location}</td>
                <td>{lake.area}</td>
                <td>
                  <Link to={`/lakes/${lake.id}`} className="btn-view">
                    Ver Detalle
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
