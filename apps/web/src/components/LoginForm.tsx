import { useState } from 'react';
import { supabase } from '../lib/supabase';

export default function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.trim() || !password.trim()) {
      setError('El correo y la contraseña son obligatorios.');
      return;
    }

    setIsLoading(true);
    
    try {
      const { error: signInError } = await supabase.auth.signInWithPassword({ email, password });
      
      if (signInError) {
        const msg = signInError.message;
        const status = signInError.status;

        // Evaluación de códigos y mensajes técnicos de Supabase
        if (status === 429 || msg.includes('Too many requests')) {
          setError('Demasiados intentos. Por favor, espera unos minutos e intenta nuevamente.');
        } else if (msg.includes('Invalid login credentials')) {
          setError('El correo o la contraseña son incorrectos.');
        } else if (msg.includes('Email not confirmed')) {
          setError('Debes confirmar tu correo electrónico antes de iniciar sesión.');
        } else if (msg.includes('Failed to fetch')) {
          setError('Error de red. Verifica tu conexión a internet.');
        } else {
          setError('Ocurrió un error al iniciar sesión. Intenta más tarde.');
        }
        return;
      }
    } catch {
      // Captura excepciones críticas a nivel de red (cuando el fetch ni siquiera alcanza a Supabase)
      setError('Error de red. Verifica tu conexión a internet.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 max-w-sm mx-auto p-6 border rounded-lg shadow-md bg-white">
      <h2 className="text-2xl font-semibold mb-2 text-gray-800">Iniciar Sesión</h2>
      
      {error && <p id="login-form-error" role="alert" className="text-red-500 text-sm font-medium">{error}</p>}
      
      <div className="flex flex-col gap-1">
        <label htmlFor="login-form-email" className="text-sm text-gray-600">Correo electrónico</label>
        <input 
          type="email" 
          id="login-form-email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? 'login-form-error' : undefined}
          className="border border-gray-300 p-2 rounded focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
          disabled={isLoading}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="login-form-password" className="text-sm text-gray-600">Contraseña</label>
        <input 
          type="password" 
          id="login-form-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? 'login-form-error' : undefined}
          className="border border-gray-300 p-2 rounded focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
          disabled={isLoading}
        />
      </div>

      <button 
        type="submit" 
        className="bg-blue-600 text-white font-medium p-2 rounded hover:bg-blue-700 transition-colors mt-2 disabled:bg-blue-400 disabled:cursor-not-allowed focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none"
        disabled={isLoading}
      >
        {isLoading ? 'Ingresando...' : 'Ingresar'}
      </button>

      <a 
        href="#" 
        className="text-sm text-gray-400 cursor-not-allowed pointer-events-none text-center mt-2 focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:outline-none" 
        aria-disabled="true"
        tabIndex={-1}
      >
        ¿Olvidaste tu contraseña? (Próximamente)
      </a>
    </form>
  );
}
