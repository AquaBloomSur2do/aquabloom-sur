import { useState } from 'react';

export default function LoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    // Validación: Evitar envío si hay campos vacíos
    if (!email.trim() || !password.trim()) {
      setError('El correo y la contraseña son obligatorios.');
      return;
    }

    // Aquí irá la llamada real a Supabase (solo se ejecuta si pasa la validación)
    try {
      console.log('Llamando a Supabase con:', email);
      // await supabaseClient.auth.signInWithPassword({ email, password });
    } catch {
      setError('Error al procesar la solicitud.');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4 max-w-sm mx-auto p-6 border rounded-lg shadow-md bg-white">
      <h2 className="text-2xl font-semibold mb-2 text-gray-800">Iniciar Sesión</h2>
      
      {error && <p className="text-red-500 text-sm font-medium">{error}</p>}
      
      <div className="flex flex-col gap-1">
        <label htmlFor="email" className="text-sm text-gray-600">Correo electrónico</label>
        <input 
          type="email" 
          id="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="border border-gray-300 p-2 rounded focus:outline-none focus:border-blue-500"
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="password" className="text-sm text-gray-600">Contraseña</label>
        <input 
          type="password" 
          id="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="border border-gray-300 p-2 rounded focus:outline-none focus:border-blue-500"
        />
      </div>

      <button 
        type="submit" 
        className="bg-blue-600 text-white font-medium p-2 rounded hover:bg-blue-700 transition-colors mt-2"
      >
        Ingresar
      </button>

      {/* Enlace de recuperación deshabilitado como función futura */}
      <a 
        href="#" 
        className="text-sm text-gray-400 cursor-not-allowed pointer-events-none text-center mt-2" 
        aria-disabled="true"
        tabIndex={-1}
      >
        ¿Olvidaste tu contraseña? (Próximamente)
      </a>
    </form>
  );
}
