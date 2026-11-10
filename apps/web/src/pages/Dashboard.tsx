import React, { useEffect, useState } from 'react';
import { DashboardCard } from '../components/DashboardCard';
import { apiClient } from '../services/apiClient';

interface ProfileSummary {
  id: string;
  email?: string | null;
  name?: string | null;
}

export const Dashboard: React.FC = () => {
  const [usersCount, setUsersCount] = useState<number | null>(null);
  const [isLoadingUsers, setIsLoadingUsers] = useState<boolean>(true);
  const [usersError, setUsersError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const fetchProfiles = async () => {
      try {
        const data = await apiClient.get<ProfileSummary[]>('dashboard/profiles');
        if (isMounted) {
          setUsersCount(Array.isArray(data) ? data.length : 0);
          setUsersError(null);
        }
      } catch (err) {
        if (isMounted) {
          setUsersError(
            err instanceof Error ? err.message : 'Error al cargar perfiles',
          );
        }
      } finally {
        if (isMounted) {
          setIsLoadingUsers(false);
        }
      }
    };

    void fetchProfiles();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="p-4 md:p-8 max-w-7xl mx-auto w-full">
      <h1 className="text-2xl md:text-3xl font-bold mb-6 text-gray-800">
        Dashboard General
      </h1>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 md:gap-6">
        {/* Tarjeta 1: Estado Exitoso (Valor) */}
        <DashboardCard
          title="Total de Lagos"
          count={14}
          isLoading={false}
          error={null}
          linkTo="/lakes"
          linkLabel="Ver lagos"
        />

        {/* Tarjeta 2: Estado de Carga */}
        <DashboardCard
          title="Estaciones Activas"
          count={null}
          isLoading={true}
          error={null}
          linkTo="/stations"
          linkLabel="Ver estaciones"
        />

        {/* Tarjeta 3: Usuarios Registrados conectada al backend */}
        <DashboardCard
          title="Usuarios Registrados"
          count={usersCount}
          isLoading={isLoadingUsers}
          error={usersError}
          linkTo="/lakes"
          linkLabel="Ir al catálogo"
        />
      </div>
    </div>
  );
};
