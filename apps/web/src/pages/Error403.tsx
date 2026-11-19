import { useNavigate } from 'react-router-dom';

export default function Error403() {
  const navigate = useNavigate();

  return (
    <main className="access-error-page">
      <section className="access-error-card">
        <span className="access-error-icon" aria-hidden="true">!</span>
        <p className="access-error-code">403</p>
        <h1>Acceso Denegado</h1>
        <p>No tienes los permisos necesarios para acceder a este recurso.</p>
        <button className="access-error-action" onClick={() => navigate('/dashboard')}>
        Ir al Dashboard
        </button>
      </section>
    </main>
  );
}
