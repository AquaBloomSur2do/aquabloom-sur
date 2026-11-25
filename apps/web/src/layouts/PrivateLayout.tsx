import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
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
  {
    path: '/datasets/review',
    label: 'Revisión de datasets',
    allowedRoles: [
      'admin',
      'administrador',
      'supervisor',
      'investigador',
      'auditor',
    ],
  },
  {
    path: '/organizations',
    label: 'Administración',
    allowedRoles: ['administrador'],
  },
];

export const PrivateLayout = () => {
  const navigate = useNavigate();
  const { user, isLoading, logout } = useAuth();
  const role = user?.user_metadata?.role;
  const userRole = typeof role === 'string' ? role : null;

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  // Si userRole es 'sin_asignar', visibleMenuItems quedará vacío de forma segura
  const visibleMenuItems = MENU_ITEMS.filter(
    (item) => userRole && item.allowedRoles.includes(userRole)
  );

  if (isLoading) {
    return (
      <div
        className="flex min-h-screen items-center justify-center bg-gray-100"
        role="status"
        aria-live="polite"
      >
        <div className="flex items-center gap-3 text-gray-600">
          <span
            className="h-8 w-8 animate-spin rounded-full border-4 border-blue-200 border-t-blue-700"
            aria-hidden="true"
          />
          <span>Cargando sesión...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link className="app-brand" to="/dashboard" aria-label="AquaBloom Sur, inicio">
          <span className="app-brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <path d="M16 3C12 9 7 14.2 7 20a9 9 0 0 0 18 0c0-5.8-5-11-9-17Z" />
              <path d="M11 20a5 5 0 0 0 5 5" />
            </svg>
          </span>
          <span className="app-brand-copy">
            <strong>AquaBloom Sur</strong>
            <small>Ciencia colaborativa de lagos</small>
          </span>
        </Link>

        <nav className="app-nav" aria-label="Navegación principal">
          {visibleMenuItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `app-nav-link${isActive ? ' is-active' : ''}`
              }
            >
              {item.label}
            </NavLink>
          ))}
          <NavLink
            to="/profile"
            className={({ isActive }) =>
              `app-nav-link${isActive ? ' is-active' : ''}`
            }
          >
            Mi perfil
          </NavLink>
          {visibleMenuItems.length === 0 && (
            <p className="app-nav-help">
              Contacte a soporte para solicitar permisos.
            </p>
          )}
        </nav>

        <div className="app-account">
          <span className="app-role-badge">
            Rol: {userRole === 'sin_asignar' ? 'No asignado' : userRole || 'No asignado'}
          </span>
          <button className="app-logout" onClick={handleLogout}>
            Cerrar Sesión
          </button>
        </div>
      </header>

      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
};
