import { Link } from 'react-router-dom';

export function Dashboard() {
  return (
    <div className="dashboard-page">
      <h1>Panel de Control</h1>
      <p>Bienvenido al panel administrativo de AquaBloom Sur.</p>
      
      <div className="dashboard-grid">
        <div className="dashboard-card">
          <h3>Lagos Registrados</h3>
          <p>Visualiza y gestiona todos los lagos en el sistema.</p>
          <Link to="/lakes" className="btn-link">Ir a Lagos</Link>
        </div>
        <div className="dashboard-card">
          <h3>Estadísticas</h3>
          <p>Análisis y métricas de los datos recopilados.</p>
        </div>
        <div className="dashboard-card">
          <h3>Configuración</h3>
          <p>Ajusta los parámetros del sistema.</p>
        </div>
      </div>
    </div>
  );
}
