import React from 'react';
import { useNavigate } from 'react-router-dom';

const Error403: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="error-page-container">
      <h1>403 - Acceso Denegado</h1>
      <p>No tienes los permisos suficientes para visualizar este recurso.</p>
      <button onClick={() => navigate('/dashboard')} className="btn-secondary">
        Volver al Dashboard
      </button>
    </div>
  );
};

export default Error403;
