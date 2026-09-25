import { useEffect, useState } from 'react';

interface UserProfile {
  name: string;
  email: string;
  organization: string;
  role: string;
  status: string;
}

export default function Profile() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setIsLoading(true);
        setError('');
        
        // Llamada a la API para obtener los datos
        const response = await fetch('/api/v1/profile'); // Ajustaremos la ruta cuando el backend la defina
        
        if (!response.ok) {
          if (response.status === 404) {
            setProfile(null);
            return;
          }
          throw new Error('Error en la red');
        }

        const data = await response.json();
        
        setProfile({
          name: data.name || 'Usuario Desconocido',
          email: data.email || 'Sin correo',
          organization: data.organization || 'Sin organización',
          role: data.role || 'Sin rol',
          status: data.status || 'inactivo'
        });
      } catch {
        setError('No se pudo cargar la información del perfil.');
      } finally {
        setIsLoading(false);
      }
    };

    fetchProfile();
  }, []);

  if (isLoading) {
    return <div className="p-6 text-center text-gray-600 font-medium">Cargando perfil...</div>;
  }

  if (error) {
    return <div className="p-6 text-center text-red-500 font-medium">{error}</div>;
  }

  if (!profile) {
    return <div className="p-6 text-center text-gray-500 font-medium">El perfil no existe o no fue encontrado.</div>;
  }

  return (
    <div className="max-w-md mx-auto p-6 bg-white border rounded-lg shadow-md mt-10">
      <h2 className="text-2xl font-semibold mb-4 text-gray-800">Perfil de Usuario</h2>
      
      <div className="flex flex-col gap-4">
        <div>
          <span className="block text-sm text-gray-500">Nombre</span>
          <span className="text-gray-900 font-medium">{profile.name}</span>
        </div>
        <div>
          <span className="block text-sm text-gray-500">Correo electrónico</span>
          <span className="text-gray-900 font-medium">{profile.email}</span>
        </div>
        <div>
          <span className="block text-sm text-gray-500">Organización activa</span>
          <span className="text-gray-900 font-medium">{profile.organization}</span>
        </div>
        <div>
          <span className="block text-sm text-gray-500">Rol</span>
          <span className="text-gray-900 font-medium">{profile.role}</span>
        </div>
        <div>
          <span className="block text-sm text-gray-500">Estado</span>
          <span className="text-gray-900 font-medium capitalize">{profile.status}</span>
        </div>
      </div>
    </div>
  );
}
