import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useComputadorasHW } from '../hooks/useComputadorasHW';
import { formatRelative } from '../lib/format';
import type { HWComputadora, HWDisco } from '../types/firestore';


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

function getDiscosArray(pc: HWComputadora): HWDisco[] {
  if (!pc.discos || typeof pc.discos === 'string') return [];
  return Array.isArray(pc.discos) ? pc.discos : [pc.discos];
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

function BarRow({ label, count, total, color, to }: { label: string; count: number; total: number; color: string; to?: string }) {
  const navigate = useNavigate();
  if (count === 0) return null;
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  const row = (
    <div className="dash-bar-row" style={{ cursor: to ? 'pointer' : undefined }} onClick={to ? () => navigate(to) : undefined}>
      <span className="dash-bar-label">{label}</span>
      <div className="dash-bar-track">
        <div className="dash-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="dash-bar-count">{count}</span>
    </div>
  );
  return row;
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
  const navigate = useNavigate();

  const stats = useMemo(() => {
    const total = computadoras.length;
    const activos = computadoras.filter(isActive).length;
    const inactivos = computadoras.filter(isInactive).length;
    const totalPerifericos = computadoras.reduce((acc, pc) => acc + countPerifericos(pc), 0);

    // CPU brand
    const cpuIntel = computadoras.filter(pc => pc.procesador?.toLowerCase().includes('intel')).length;
    const cpuAMD = computadoras.filter(pc => pc.procesador?.toLowerCase().includes('amd')).length;
    const cpuOtro = total - cpuIntel - cpuAMD;

    // OS version
    const win11 = computadoras.filter(pc => (pc.sistema_operativo ?? pc.so ?? '').includes('Windows 11')).length;
    const win10 = computadoras.filter(pc => (pc.sistema_operativo ?? pc.so ?? '').includes('Windows 10')).length;
    const soOtro = total - win11 - win10;

    // Peripherals by connection type
    let periInalamb = 0;
    let periCableado = 0;
    for (const pc of computadoras) {
      for (const dev of pc.perifericos?.dispositivos_usb ?? []) {
        if (dev.conexion === 'inalambrico_usb' || dev.conexion === 'bluetooth') periInalamb++;
        else if (dev.conexion === 'usb') periCableado++;
      }
    }

    // Discs
    const ssd = computadoras.filter(pc => getDiscosArray(pc).some(d => d.tipo_disco === 'SSD')).length;
    const hdd = computadoras.filter(pc => getDiscosArray(pc).some(d => d.tipo_disco === 'HDD')).length;
    const discoOtro = computadoras.filter(pc => !getDiscosArray(pc).some(d => d.tipo_disco === 'SSD' || d.tipo_disco === 'HDD')).length;

    return { total, activos, inactivos, totalPerifericos, cpuIntel, cpuAMD, cpuOtro, win11, win10, soOtro, periInalamb, periCableado, ssd, hdd, discoOtro };
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

      {/* Panel: Resumen */}
      {!loading && stats.total > 0 && (
        <div className="dash-breakdown-grid">
          <div className="dash-panel">
            <h2>Procesadores</h2>
            <div className="dash-bar-group">
              <BarRow label="Intel" count={stats.cpuIntel} total={stats.total} color="#1565c0" to="/inventario?tipo=CPU&q=intel" />
              <BarRow label="AMD" count={stats.cpuAMD} total={stats.total} color="#d84315" to="/inventario?tipo=CPU&q=amd" />
              <BarRow label="Otro" count={stats.cpuOtro} total={stats.total} color="#9e9e9e" to="/inventario?tipo=CPU" />
            </div>
          </div>
          <div className="dash-panel">
            <h2>Sistema operativo</h2>
            <div className="dash-bar-group">
              <BarRow label="Windows 11" count={stats.win11} total={stats.total} color="#6a1b9a" to="/inventario?tipo=CPU&q=windows+11" />
              <BarRow label="Windows 10" count={stats.win10} total={stats.total} color="#1976d2" to="/inventario?tipo=CPU&q=windows+10" />
              <BarRow label="Otro" count={stats.soOtro} total={stats.total} color="#9e9e9e" to="/inventario?tipo=CPU" />
            </div>
          </div>
          <div className="dash-panel">
            <h2>Discos</h2>
            <div className="dash-bar-group">
              <BarRow label="SSD" count={stats.ssd} total={stats.total} color="#283593" to="/inventario?tipo=SSD" />
              <BarRow label="HDD" count={stats.hdd} total={stats.total} color="#4e342e" to="/inventario?tipo=HDD" />
              <BarRow label="Otro" count={stats.discoOtro} total={stats.total} color="#9e9e9e" to="/inventario?tipo=Disco" />
            </div>
          </div>
          <div className="dash-panel">
            <h2>Perifericos</h2>
            <div className="dash-bar-group">
              <BarRow label="Inalambrico" count={stats.periInalamb} total={stats.periInalamb + stats.periCableado || 1} color="#2e7d32" />
              <BarRow label="Cableado" count={stats.periCableado} total={stats.periInalamb + stats.periCableado || 1} color="#e65100" />
            </div>
          </div>
        </div>
      )}

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
                <div key={pc.id} className="dash-pc-row" style={{ cursor: 'pointer' }} onClick={() => navigate(`/computadoras/${pc.id}`)}>
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
