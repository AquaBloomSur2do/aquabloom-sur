import { Link } from 'react-router-dom';

export function NotFound() {
  return (
    <main className="access-error-page">
      <section className="access-error-card">
        <span className="access-error-icon" aria-hidden="true">?</span>
        <p className="access-error-code">404</p>
        <h1>Página no encontrada</h1>
        <p>La página que buscas no existe o fue movida.</p>
        <Link className="access-error-action" to="/">
          Volver al inicio
        </Link>
      </section>
    </main>
  );
}
