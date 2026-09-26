import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { supabase } from '../lib/supabase';

export const Login = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      setError('Credenciales inválidas. Verifica tu correo y contraseña.');
      setIsLoading(false);
      console.error(authError);
    } else {
      navigate('/dashboard', { replace: true });
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-900 text-white">
      <h1 className="text-3xl font-bold mb-6">AquaBloom Sur</h1>
      <h2 className="text-xl mb-4">Iniciar Sesión</h2>

      <form onSubmit={handleLogin} className="flex flex-col items-center gap-4">
        <label className="flex flex-col gap-1 w-full">
          <span>Correo Electrónico</span>
          <input
            type="email"
            className="text-black px-3 py-2 rounded"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={isLoading}
          />
        </label>

        <label className="flex flex-col gap-1 w-full">
          <span>Contraseña</span>
          <input
            type="password"
            className="text-black px-3 py-2 rounded"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            disabled={isLoading}
          />
        </label>

        {error && (
          <p className="text-red-500 text-sm max-w-xs text-center">{error}</p>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="mt-2 px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded font-medium transition-colors w-full"
        >
          {isLoading ? 'Verificando...' : 'Ingresar'}
        </button>
      </form>
    </div>
  );
};
