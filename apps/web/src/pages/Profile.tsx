import { useEffect, useState } from 'react';
import { apiClient } from '../services/apiClient';

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
    let isMounted = true;

    const fetchProfile = async () => {
      try {
        if (isMounted) setIsLoading(true);
        if (isMounted) setError('');
        
        // Llamada directa sin desestructurar para cumplir con la interfaz
        const data = await apiClient.get<UserProfile>('/profile');
        
        if (isMounted) {
          setProfile({
            name: data.name || 'Usuario Desconocido',
            email: data.email || 'Sin correo',
            organization: data.organization || 'Sin organización',
            role: data.role || 'Sin rol',
            status: data.status || 'inactivo'
          });
        }
      } catch (err: unknown) {
        if (isMounted) {
          // Moldeamos el error desconocido a la estructura segura esperada
          const apiError = err as { response?: { status?: number } };
          
          if (apiError?.response?.status === 404) {
            setProfile(null);
          } else {
            setError('No se pudo cargar la información del perfil.');
          }
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    void fetchProfile();

    return () => {
      isMounted = false;
    };
  }, []);

  if (isLoading) {
    return (
      <section className="profile-state" role="status">
        <span className="profile-spinner" aria-hidden="true" />
        <span>Cargando perfil...</span>
      </section>
    );
  }

  if (error) {
    return (
      <section className="profile-state profile-state--error" role="alert">
        {error}
      </section>
    );
  }

  if (!profile) {
    return (
      <section className="profile-state">
        El perfil no existe o no fue encontrado.
      </section>
    );
  }

  return (
    <section className="profile-page">
      <header className="profile-page-heading">
        <p className="profile-eyebrow">Cuenta</p>
        <h1>Perfil de Usuario</h1>
        <p>Información asociada a tu cuenta en AquaBloom Sur.</p>
      </header>
      <article className="profile-card">
        <div className="profile-card-heading">
          <span className="profile-avatar" aria-hidden="true">
            {profile.name.trim().charAt(0).toUpperCase()}
          </span>
          <div>
            <h2>{profile.name}</h2>
            <p>{profile.organization}</p>
          </div>
          <span className="profile-status">{profile.status}</span>
        </div>

        <dl className="profile-details">
          <div>
            <dt>Nombre</dt>
            <dd>{profile.name}</dd>
          </div>
          <div>
            <dt>Correo electrónico</dt>
            <dd>{profile.email}</dd>
          </div>
          <div>
            <dt>Organización activa</dt>
            <dd>{profile.organization}</dd>
          </div>
          <div>
            <dt>Rol</dt>
            <dd>{profile.role}</dd>
          </div>
          <div>
            <dt>Estado</dt>
            <dd className="profile-status-text">{profile.status}</dd>
          </div>
        </dl>
      </article>
    </section>
  );
}
