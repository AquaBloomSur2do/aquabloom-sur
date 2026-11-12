import React, { useEffect, useState } from 'react';
import { DashboardCard } from '../components/DashboardCard';
import { apiClient } from '../services/apiClient';

interface ProfileSummary {
  id: string;
  email?: string | null;
  name?: string | null;
}

export const Dashboard: React.FC = () => {
  // Estado para la API real de usuarios
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [usersCount, setUsersCount] = useState<number | null>(null);
  const [isLoadingUsers, setIsLoadingUsers] = useState<boolean>(true);
  const [usersError, setUsersError] = useState<string | null>(null);

  // Estado simulado para que Estaciones no quede en carga infinita
  const [stationsCount, setStationsCount] = useState<number | null>(null);
  const [isLoadingStations, setIsLoadingStations] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;

    // 1. Cargar perfiles reales del backend
    const fetchProfiles = async () => {
      try {
        const data = await apiClient.get<ProfileSummary[]>('dashboard/profiles');
        if (isMounted) {
          const profileData = Array.isArray(data) ? data : [];
          setProfiles(profileData);
          setUsersCount(profileData.length);
          setUsersError(null);
        }
      } catch (err) {
        if (isMounted) {
          setUsersError(err instanceof Error ? err.message : 'Error al cargar perfiles');
        }
      } finally {
        if (isMounted) {
          setIsLoadingUsers(false);
        }
      }
    };

    void fetchProfiles();

    // 2. Simular carga de estaciones para demostrar el Skeleton (1.5 segundos)
    const timer = setTimeout(() => {
      if (isMounted) {
        setStationsCount(8);
        setIsLoadingStations(false);
      }
    }, 1500);

    return () => {
      isMounted = false;
      clearTimeout(timer);
    };
  }, []);

  return (
    <div className="dashboard-container" style={{ padding: '2rem' }}>
      <h1 className="text-2xl md:text-3xl font-bold mb-6 text-gray-800">
        Dashboard General
      </h1>
      <p style={{ marginBottom: '2rem', color: '#555' }}>
        Resumen operativo de AquaBloom Sur.
      </p>

      <div className="dashboard-kpi-grid">
        {/* Tarjeta 1: Estática */}
        <DashboardCard
          title="Total de Lagos"
          count={14}
          isLoading={false}
          error={null}
          linkTo="/lakes"
          linkLabel="Ver lagos"
          icon="🌊"
        />

        {/* Tarjeta 2: Carga simulada (ya no es infinita) */}
        <DashboardCard
          title="Estaciones Activas"
          count={stationsCount}
          isLoading={isLoadingStations}
          error={null}
          linkTo="/stations"
          linkLabel="Ver estaciones"
          icon="📡"
        />

        {/* Tarjeta 3: Conectada al backend */}
        <DashboardCard
          title="Usuarios Registrados"
          count={usersCount}
          isLoading={isLoadingUsers}
          error={usersError}
          linkTo="/lakes"
          linkLabel="Ir al catálogo"
          icon="👥"
        />
      </div>

      <section>
        <h2 className="dashboard-section-title">Estado del Piloto Científico</h2>
        <div className="dashboard-summary-panel">
          <p><strong>Cobertura actual:</strong> Monitoreo activo en lagos del sur de Chile.</p>
          <p><strong>Revisión de datasets:</strong> Operativa. Ingrese a la sección de validación para aprobar candidatos pendientes.</p>
        </div>
      </section>

      {/* Nueva Sección: Tabla de perfiles solicitada por la revisión */}
      <section className="profiles-section">
        <h2 className="dashboard-section-title">Perfiles Registrados</h2>
        {isLoadingUsers ? (
          <div className="skeleton-loader" style={{ maxWidth: '100%', height: '80px' }}>
             <span className="visually-hidden">Cargando tabla de perfiles...</span>
          </div>
        ) : usersError ? (
          <div className="state-error" style={{ padding: '1rem', borderRadius: '8px' }}>
            ⚠️ {usersError}
          </div>
        ) : profiles.length === 0 ? (
          <p style={{ color: '#666' }}>No hay perfiles registrados en la plataforma.</p>
        ) : (
          <div className="profiles-table-wrap">
            <table className="profiles-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Nombre</th>
                  <th>Correo Electrónico</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => (
                  <tr key={profile.id}>
                    <td style={{ fontWeight: 600, color: '#0056b3' }}>
                      {profile.id.substring(0, 8)}...
                    </td>
                    <td>{profile.name || <span style={{ color: '#999', fontStyle: 'italic' }}>Sin nombre</span>}</td>
                    <td>{profile.email || <span style={{ color: '#999', fontStyle: 'italic' }}>Sin correo</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
};
