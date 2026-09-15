import { Outlet } from 'react-router-dom';

export function PublicLayout() {
  return (
    <div className="public-layout">
      <header className="public-header">
        <h1>AquaBloom Sur</h1>
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
