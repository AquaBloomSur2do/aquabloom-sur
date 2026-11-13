import { Link, Outlet } from 'react-router-dom';

export function PublicLayout() {
  return (
    <div className="public-layout">
      <header className="public-header">
        <Link className="public-brand" to="/" aria-label="AquaBloom Sur, inicio">
          <span className="app-brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <path d="M16 3C12 9 7 14.2 7 20a9 9 0 0 0 18 0c0-5.8-5-11-9-17Z" />
              <path d="M11 20a5 5 0 0 0 5 5" />
            </svg>
          </span>
          <span className="app-brand-copy">
            <strong>AquaBloom Sur</strong>
            <small>Ciencia colaborativa de lagos</small>
          </span>
        </Link>
      </header>
      <main className="public-main">
        <Outlet />
      </main>
      <footer className="public-footer">
        <p>&copy; 2026 AquaBloom Sur. Todos los derechos reservados.</p>
      </footer>
    </div>
  );
}
