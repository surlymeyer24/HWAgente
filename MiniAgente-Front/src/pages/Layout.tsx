import { useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="layout">
      {/* Mobile topbar */}
      <div className="mobile-topbar">
        <NavLink to="/" className="logo" onClick={() => setSidebarOpen(false)}>
          <span className="logo-icon">🖥</span>
          HW Dashboard
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
          <span className="logo-icon">🖥</span>
          HW Dashboard
        </NavLink>
        <nav className="nav">
          <NavLink
            to="/"
            end
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            onClick={() => setSidebarOpen(false)}
          >
            📊 Dashboard
          </NavLink>
          <NavLink
            to="/inventario"
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            onClick={() => setSidebarOpen(false)}
          >
            🗂 Inventario
          </NavLink>
          <NavLink
            to="/computadoras"
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            onClick={() => setSidebarOpen(false)}
          >
            💻 Computadoras
          </NavLink>
          <NavLink
            to="/tareas"
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            onClick={() => setSidebarOpen(false)}
          >
            ⚡ Tareas
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
