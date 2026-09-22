import { Outlet, Link, useNavigate } from 'react-router-dom';
import { supabase } from '../services/supabase';

export function PrivateLayout() {
  const navigate = useNavigate();
  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate('/login', { replace: true });
  };

  return (
    <div className="private-layout">
      <nav className="private-navbar">
        <div className="navbar-brand">
          <h2>AquaBloom Sur - Panel</h2>
        </div>
        <div className="navbar-menu">
          <Link to="/dashboard" className="nav-link">Dashboard</Link>
          <Link to="/lakes" className="nav-link">Lagos</Link>
          <button onClick={handleLogout} className="nav-link logout-btn">Cerrar sesión</button>
        </div>
      </nav>
      <div className="private-container">
        <aside className="private-sidebar">
          <ul className="sidebar-menu">
            <li><Link to="/dashboard">Inicio</Link></li>
            <li><Link to="/lakes">Listado de Lagos</Link></li>
          </ul>
        </aside>
        <main className="private-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
