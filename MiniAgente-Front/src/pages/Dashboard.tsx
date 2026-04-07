import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useComputadorasHW } from '../hooks/useComputadorasHW';
import { formatRelative } from '../lib/format';
import type { HWComputadora } from '../types/firestore';

const ACTIVE_THRESHOLD_SEC = 10 * 60; // 10 minutos
const INACTIVE_THRESHOLD_SEC = 60 * 60; // 1 hora

function getLastSync(pc: HWComputadora) {
  return pc.ultima_sincronizacion ?? pc.ultima_sync ?? null;
}

function isActive(pc: HWComputadora): boolean {
  const ts = getLastSync(pc);
  if (!ts || typeof ts.seconds !== 'number') return false;
  return Math.floor(Date.now() / 1000) - ts.seconds < ACTIVE_THRESHOLD_SEC;
}

function isInactive(pc: HWComputadora): boolean {
  const ts = getLastSync(pc);
  if (!ts || typeof ts.seconds !== 'number') return true;
  return Math.floor(Date.now() / 1000) - ts.seconds >= INACTIVE_THRESHOLD_SEC;
}

function countPerifericos(pc: HWComputadora): number {
  const p = pc.perifericos;
  if (!p) return 0;
  return (
    (p.monitores?.length ?? 0) +
    (p.dispositivos_usb?.length ?? 0) +
    (p.impresoras?.filter(i => i.tipo_impresora !== 'virtual').length ?? 0) +
    (p.audio?.salida?.length ?? 0)
  );
}

function StatCard({
  label,
  value,
  sub,
  color,
  to,
}: {
  label: string;
  value: string | number;
  sub?: string;
  color: string;
  to?: string;
}) {
  const inner = (
    <>
      <span className="dash-stat-value">{value}</span>
      <span className="dash-stat-label">{label}</span>
      {sub && <span className="dash-stat-sub">{sub}</span>}
    </>
  );

  if (to) {
    return (
      <Link
        to={to}
        className="dash-stat-card"
        style={{ '--stat-accent': color } as React.CSSProperties}
      >
        {inner}
      </Link>
    );
  }
  return (
    <div
      className="dash-stat-card"
      style={{ '--stat-accent': color } as React.CSSProperties}
    >
      {inner}
    </div>
  );
}

export function Dashboard() {
  const { computadoras, loading, error } = useComputadorasHW();

  const stats = useMemo(() => {
    const total = computadoras.length;
    const activos = computadoras.filter(isActive).length;
    const inactivos = computadoras.filter(isInactive).length;
    const totalPerifericos = computadoras.reduce((acc, pc) => acc + countPerifericos(pc), 0);
    return { total, activos, inactivos, totalPerifericos };
  }, [computadoras]);

  // Últimas 8 PCs ordenadas por última sync
  const recentPcs = useMemo(() => {
    return [...computadoras]
      .sort((a, b) => {
        const ta = (getLastSync(a)?.seconds ?? 0);
        const tb = (getLastSync(b)?.seconds ?? 0);
        return tb - ta;
      })
      .slice(0, 8);
  }, [computadoras]);

  if (error) {
    return (
      <div className="page">
        <h1>Dashboard</h1>
        <p className="error">{error}</p>
      </div>
    );
  }

  return (
    <div className="page">
      <h1>Dashboard</h1>
      <p className="muted">
        {loading ? 'Cargando...' : `${stats.total} equipo${stats.total !== 1 ? 's' : ''} registrado${stats.total !== 1 ? 's' : ''}`}
      </p>

      {/* Stat cards */}
      <div className="dash-stats">
        <StatCard
          label="Total equipos"
          value={loading ? '…' : stats.total}
          sub="con agente instalado"
          color="#5c6bc0"
          to="/inventario"
        />
        <StatCard
          label="Activos"
          value={loading ? '…' : stats.activos}
          sub="sync < 10 min"
          color="#2e7d32"
        />
        <StatCard
          label="Sin actividad"
          value={loading ? '…' : stats.inactivos}
          sub="sin sync hace > 1 h"
          color="#D21312"
        />
        <StatCard
          label="Periféricos"
          value={loading ? '…' : stats.totalPerifericos}
          sub="detectados en total"
          color="#7b5ea7"
          to="/inventario"
        />
      </div>

      {/* Panel: equipos recientes */}
      <div className="dash-panel">
        <div className="dash-panel-header">
          <h2>Equipos recientes</h2>
          <Link to="/inventario" className="dash-panel-link">
            Ver inventario →
          </Link>
        </div>

        {loading ? (
          <p className="muted">Cargando equipos...</p>
        ) : recentPcs.length === 0 ? (
          <p className="muted">No hay equipos registrados.</p>
        ) : (
          <div className="dash-pc-list">
            {recentPcs.map((pc) => {
              const active = isActive(pc);
              const ts = getLastSync(pc);
              return (
                <div key={pc.id} className="dash-pc-row">
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: active ? '#2e7d32' : '#aaa',
                      flexShrink: 0,
                    }}
                  />
                  <span className="dash-pc-hostname">
                    {pc.hostname ?? pc.id}
                  </span>
                  {pc.version_agente && (
                    <code style={{ fontSize: '0.78rem', opacity: 0.7 }}>
                      v{pc.version_agente}
                    </code>
                  )}
                  <span className="dash-pc-meta">{formatRelative(ts)}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
