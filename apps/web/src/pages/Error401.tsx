import React from 'react';
import { useNavigate } from 'react-router-dom';

const Error401: React.FC = () => {
  const navigate = useNavigate();

  return (
    <div className="error-page-container">
      <h1>401 - Acceso No Autorizado</h1>
      <p>Tu sesión ha expirado o no estás autenticado en AquaBloom Sur.</p>
      <button onClick={() => navigate('/login')} className="btn-primary">
        Volver al Login
      </button>
    </div>
  );
};

export default Error401;
