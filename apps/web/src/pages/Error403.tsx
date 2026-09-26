import { useNavigate } from 'react-router-dom';

export default function Error403() {
  const navigate = useNavigate();

  return (
    <div style={{ textAlign: 'center', padding: '50px', color: '#fff', background: '#111', minHeight: '100vh' }}>
      <h1>AquaBloom Sur</h1>
      <h2>403 - Acceso Denegado</h2>
      <p>No tienes los permisos necesarios para acceder a este recurso.</p>
      <button onClick={() => navigate('/dashboard')} style={{ padding: '10px 20px', cursor: 'pointer' }}>
        Ir al Dashboard
      </button>
    </div>
  );
}
