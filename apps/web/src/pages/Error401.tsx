import { useNavigate } from 'react-router-dom';

export default function Error401() {
  const navigate = useNavigate();

  return (
    <div style={{ textAlign: 'center', padding: '50px', color: '#fff', background: '#111', minHeight: '100vh' }}>
      <h1>AquaBloom Sur</h1>
      <h2>401 - Acceso No Autorizado</h2>
      <p>Tu sesión ha expirado o no estás autenticado.</p>
      <button onClick={() => navigate('/login')} style={{ padding: '10px 20px', cursor: 'pointer' }}>
        Volver al Login
      </button>
    </div>
  );
}
