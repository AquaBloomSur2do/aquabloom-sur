import { useEffect, useState } from 'react';
import { ApiError } from '../services/apiClient';
import { apiClient } from '../services/apiClient';
import { useAuth } from '../contexts/useAuth';

interface UserProfile {
  name: string;
  email: string;
  organization: string;
  role: string;
  status: string;
}

interface CurrentUserResponse {
  id: string;
  email: string | null;
  memberships: Array<{
    id: string;
    role: string;
    status: string;
    organization: {
      id: string;
      name: string;
      status: string;
    };
  }>;
}

export default function Profile() {
  const { user } = useAuth();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let isMounted = true;

    const fetchProfile = async () => {
      try {
        if (isMounted) setIsLoading(true);
        if (isMounted) setError('');

        const data = await apiClient.get<CurrentUserResponse>('auth/me');
        const membership = data.memberships[0];
        const metadataName =
          user?.user_metadata?.full_name ?? user?.user_metadata?.name;
        const email = data.email ?? user?.email ?? '';

        if (isMounted) {
          setProfile({
            name:
              (typeof metadataName === 'string' && metadataName.trim()) ||
              email.split('@')[0] ||
              'Usuario',
            email: email || 'Sin correo',
            organization: membership?.organization.name || 'Sin organización',
            role:
              membership?.role ||
              (typeof user?.user_metadata?.role === 'string'
                ? user.user_metadata.role
                : 'Sin rol'),
            status: membership?.status || 'Activo',
          });
        }
      } catch (err: unknown) {
        if (isMounted) {
          if (err instanceof ApiError && err.status === 404) {
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
  }, [user]);

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
