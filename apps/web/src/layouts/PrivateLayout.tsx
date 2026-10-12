import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/useAuth';

const MENU_ITEMS = [
  {
    path: '/dashboard',
    label: 'Dashboard',
    allowedRoles: ['administrador', 'investigador'],
  },
  {
    path: '/lakes',
    label: 'Catálogo de Lagos',
    allowedRoles: ['administrador', 'investigador'],
  },
  {
    path: '/stations',
    label: 'Estaciones',
    allowedRoles: ['administrador', 'investigador'],
  },
  { path: '/organizations', label: 'Administración', allowedRoles: ['administrador'] },
];

export const PrivateLayout = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const userRole = user?.role ?? null;

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  // Si userRole es 'sin_asignar', visibleMenuItems quedará vacío de forma segura
  const visibleMenuItems = MENU_ITEMS.filter((item) =>
    userRole && item.allowedRoles.includes(userRole)
  );

  return (
    <div className="flex h-screen bg-gray-100">
      <aside className="w-64 bg-white shadow-md flex flex-col">
        <div className="p-6 border-b">
          <h2 className="text-xl font-bold text-blue-800">AquaBloom Sur</h2>
          <p className="text-sm text-gray-500 mt-1 capitalize">
            Rol: {userRole === 'sin_asignar' ? 'No asignado' : userRole}
          </p>
        </div>

        <nav className="flex-1 p-4 space-y-2">
          {visibleMenuItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `block px-4 py-3 rounded-md transition-all ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-semibold border-l-4 border-blue-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-blue-600'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
          
          {visibleMenuItems.length === 0 && (
            <p className="text-sm text-red-500 px-4">Contacte a soporte para solicitar permisos.</p>
          )}
        </nav>

        <div className="p-4 border-t">
          <button
            onClick={handleLogout}
            className="w-full px-4 py-2 text-sm font-medium text-red-600 bg-red-50 hover:bg-red-100 rounded-md transition-colors"
          >
            Cerrar Sesión
          </button>
        </div>
      </aside>

      <main className="flex-1 p-8 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
};

