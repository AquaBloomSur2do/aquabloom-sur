import React from 'react';
import { DashboardCard } from '../components/DashboardCard';

export const Dashboard: React.FC = () => {
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
          linkTo="/catalog"
        />

        {/* Tarjeta 2: Estado de Carga */}
        <DashboardCard
          title="Estaciones Activas"
          count={null}
          isLoading={true}
          error={null}
          linkTo="/catalog"
        />

        {/* Tarjeta 3: Estado de Error */}
        <DashboardCard
          title="Usuarios Registrados"
          count={null}
          isLoading={false}
          error="Error de conexión"
          linkTo="/catalog"
        />
      </div>
    </div>
  );
};
