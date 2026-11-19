import { useNavigate } from 'react-router-dom';

export default function Error401() {
  const navigate = useNavigate();

  return (
    <main className="access-error-page">
      <section className="access-error-card">
        <span className="access-error-icon" aria-hidden="true">!</span>
        <p className="access-error-code">401</p>
        <h1>Acceso No Autorizado</h1>
        <p>Tu sesión ha expirado o no estás autenticado.</p>
        <button className="access-error-action" onClick={() => navigate('/login')}>
        Volver al Login
        </button>
      </section>
    </main>
  );
}
