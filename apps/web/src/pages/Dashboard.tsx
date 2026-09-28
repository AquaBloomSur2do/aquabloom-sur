import React from 'react';
import { DashboardCard } from '../components/DashboardCard';

export const Dashboard: React.FC = () => {
    return (
        <div style={{ padding: '32px' }}>
            <h1 style={{ marginBottom: '24px', fontSize: '2rem' }}>Dashboard General</h1>
            
            <div style={{ 
                display: 'grid', 
                gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', 
                gap: '24px' 
            }}>
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
