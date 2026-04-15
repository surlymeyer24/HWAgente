import { useState } from 'react';
import {
  ClipboardList,
  LayoutDashboard,
  Monitor,
  Zap,
} from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';

const navIconProps = {
  size: 20,
  strokeWidth: 1.75,
  'aria-hidden': true as const,
};

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="layout">
      {/* Mobile topbar */}
      <div className="mobile-topbar">
        <NavLink to="/" className="logo" onClick={() => setSidebarOpen(false)}>
          <span className="logo-icon">
            <Monitor size={16} strokeWidth={2} aria-hidden />
          </span>
          AgenteBacar
        </NavLink>
        <button
          className="hamburger"
          onClick={() => setSidebarOpen((o) => !o)}
          aria-label="Abrir menú"
        >
          <span />
          <span />
          <span />
        </button>
      </div>

      {/* Sidebar overlay (mobile) */}
      {sidebarOpen && (
        <div
          className="sidebar-overlay"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`sidebar${sidebarOpen ? ' sidebar--open' : ''}`}>
        <NavLink to="/" className="logo" onClick={() => setSidebarOpen(false)}>
          <span className="logo-icon">
            <Monitor size={16} strokeWidth={2} aria-hidden />
          </span>
          AgenteBacar
        </NavLink>
        <nav className="nav">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            onClick={() => setSidebarOpen(false)}
          >
            <LayoutDashboard {...navIconProps} />
            Dashboard
          </NavLink>
          <NavLink
            to="/inventario"
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            onClick={() => setSidebarOpen(false)}
          >
            <ClipboardList {...navIconProps} />
            Inventario
          </NavLink>
          <NavLink
            to="/computadoras"
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            onClick={() => setSidebarOpen(false)}
          >
            <Monitor {...navIconProps} />
            Computadoras
          </NavLink>
          <NavLink
            to="/tareas"
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            onClick={() => setSidebarOpen(false)}
          >
            <Zap {...navIconProps} />
            Tareas
          </NavLink>
        </nav>
      </aside>

      {/* Content */}
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
