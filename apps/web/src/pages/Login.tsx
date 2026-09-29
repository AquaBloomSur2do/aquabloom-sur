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
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white px-4 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <h1 className="text-3xl font-bold mb-2">AquaBloom Sur</h1>
          <h2 className="text-xl text-gray-300 mb-8">Iniciar Sesión</h2>
        </div>

        <form
          onSubmit={handleLogin}
          className="flex flex-col gap-5 bg-gray-800 p-6 md:p-8 rounded-xl shadow-lg border border-gray-700"
        >
          <label htmlFor="login-email" className="flex flex-col gap-1.5 w-full">
            <span className="text-sm font-medium text-gray-300">
              Correo Electrónico
            </span>
            <input
              type="email"
              id="login-email"
              aria-invalid={Boolean(error)}
              aria-describedby={error ? 'login-error' : undefined}
              className="text-black px-4 py-2.5 rounded-lg w-full focus:ring-2 focus:ring-blue-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 transition-shadow"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={isLoading}
              placeholder="tu@correo.cl"
            />
          </label>

          <label htmlFor="login-password" className="flex flex-col gap-1.5 w-full">
            <span className="text-sm font-medium text-gray-300">
              Contraseña
            </span>
            <input
              type="password"
              id="login-password"
              aria-invalid={Boolean(error)}
              aria-describedby={error ? 'login-error' : undefined}
              className="text-black px-4 py-2.5 rounded-lg w-full focus:ring-2 focus:ring-blue-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 transition-shadow"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
              placeholder="••••••••"
            />
          </label>

          {error && (
            <p id="login-error" role="alert" className="text-red-400 text-sm text-center bg-red-900/30 p-2 rounded border border-red-800">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="mt-4 px-6 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg font-semibold transition-colors w-full shadow-md focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:outline-none"
          >
            {isLoading ? 'Verificando...' : 'Ingresar'}
          </button>
        </form>
      </div>
    </div>
  );
};

