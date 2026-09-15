import { useParams, Link } from 'react-router-dom';

interface LakeInfo {
  id: string;
  name: string;
  location: string;
  area: number;
  depth: number;
  coordinates: {
    latitude: number;
    longitude: number;
  };
}

export function LakeDetail() {
  const { id } = useParams<{ id: string }>();

  // Datos de ejemplo - en una aplicación real, estos vendrían de una API
  const lakesData: Record<string, LakeInfo> = {
    '1': {
      id: '1',
      name: 'Lago Argentino',
      location: 'Santa Cruz, Argentina',
      area: 1468,
      depth: 532,
      coordinates: { latitude: -50.333, longitude: -73.189 },
    },
    '2': {
      id: '2',
      name: 'Lago Nahuel Huapi',
      location: 'Río Negro, Argentina',
      area: 557,
      depth: 464,
      coordinates: { latitude: -41.137, longitude: -71.588 },
    },
    '3': {
      id: '3',
      name: 'Lago Viedma',
      location: 'Santa Cruz, Argentina',
      area: 1080,
      depth: 423,
      coordinates: { latitude: -50.306, longitude: -72.606 },
    },
    '4': {
      id: '4',
      name: 'Lago San Martín',
      location: 'Santa Cruz, Argentina',
      area: 1050,
      depth: 395,
      coordinates: { latitude: -48.800, longitude: -71.000 },
    },
  };

  const lake = id ? lakesData[id] : null;

  if (!lake) {
    return (
      <div className="lake-detail-page">
        <h1>Lago no encontrado</h1>
        <p>El lago solicitado no existe.</p>
        <Link to="/lakes" className="btn-back">
          Volver al listado
        </Link>
      </div>
    );
  }

  return (
    <div className="lake-detail-page">
      <div className="detail-header">
        <Link to="/lakes" className="btn-back">
          ← Volver
        </Link>
        <h1>{lake.name}</h1>
      </div>

      <div className="detail-content">
        <div className="detail-section">
          <h2>Información General</h2>
          <div className="info-grid">
            <div className="info-item">
              <label>Ubicación:</label>
              <p>{lake.location}</p>
            </div>
            <div className="info-item">
              <label>Área:</label>
              <p>{lake.area} km²</p>
            </div>
            <div className="info-item">
              <label>Profundidad Máxima:</label>
              <p>{lake.depth} m</p>
            </div>
            <div className="info-item">
              <label>Coordenadas:</label>
              <p>
                {lake.coordinates.latitude.toFixed(3)}, {lake.coordinates.longitude.toFixed(3)}
              </p>
            </div>
          </div>
        </div>

        <div className="detail-section">
          <h2>Identificador</h2>
          <p>ID del lago: <strong>{lake.id}</strong></p>
        </div>
      </div>
    </div>
  );
}
