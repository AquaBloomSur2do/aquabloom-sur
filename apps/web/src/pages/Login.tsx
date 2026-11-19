import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/useAuth';

export const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const { login } = useAuth();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await login({ email, password });
      navigate('/dashboard', { replace: true });
    } catch (authError) {
      setError('Credenciales inválidas. Verifica tu correo y contraseña.');
      console.error(authError);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="login-page">
      <div className="login-card">
        <div className="login-heading">
          <span className="login-icon" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <path d="M16 3C12 9 7 14.2 7 20a9 9 0 0 0 18 0c0-5.8-5-11-9-17Z" />
              <path d="M11 20a5 5 0 0 0 5 5" />
            </svg>
          </span>
          <p className="login-eyebrow">Plataforma científica</p>
          <h1>AquaBloom Sur</h1>
          <h2>Iniciar Sesión</h2>
          <p className="login-intro">
            Ingresa a tu espacio de investigación y colaboración.
          </p>
        </div>

        <form onSubmit={handleLogin} className="login-form">
          <label htmlFor="login-email" className="login-label">
            <span>Correo Electrónico</span>
            <input
              type="email"
              id="login-email"
              aria-invalid={Boolean(error)}
              aria-describedby={error ? 'login-error' : undefined}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={isLoading}
              placeholder="tu@correo.cl"
            />
          </label>

          <label htmlFor="login-password" className="login-label">
            <span>Contraseña</span>
            <input
              type="password"
              id="login-password"
              aria-invalid={Boolean(error)}
              aria-describedby={error ? 'login-error' : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
              placeholder="••••••••"
            />
          </label>

          {error && (
            <p id="login-error" role="alert" className="login-error">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="login-submit"
          >
            {isLoading ? 'Verificando...' : 'Ingresar'}
          </button>
        </form>
      </div>
    </section>
  );
};
