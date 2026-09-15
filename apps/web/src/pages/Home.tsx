import { Link } from 'react-router-dom';

export function Home() {
  return (
    <div className="home-page">
      <section className="home-hero">
        <h1>Bienvenido a AquaBloom Sur</h1>
        <p>Sistema de monitoreo y gestión de lagos en la Patagonia argentina</p>
        <Link to="/login" className="btn-primary">
          Iniciar Sesión
        </Link>
      </section>

      <section className="home-features">
        <h2>Características Principales</h2>
        <div className="features-grid">
          <div className="feature-card">
            <h3>Monitoreo en Tiempo Real</h3>
            <p>Visualiza datos actualizados de los lagos de la región.</p>
          </div>
          <div className="feature-card">
            <h3>Análisis Detallados</h3>
            <p>Obtén informes y estadísticas de cada cuerpo de agua.</p>
          </div>
          <div className="feature-card">
            <h3>Gestión Integral</h3>
            <p>Administra la información de forma centralizada y segura.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
