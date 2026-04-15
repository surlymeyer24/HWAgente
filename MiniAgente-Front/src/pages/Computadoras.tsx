import { useNavigate } from 'react-router-dom';
import { useComputadorasHW } from '../hooks/useComputadorasHW';
import { useComandoHW } from '../hooks/useComandoHW';
import { formatTimestamp, formatRelative } from '../lib/format';
import type { HWComputadora } from '../types/firestore';

const ACTIVE_THRESHOLD_SEC = 10 * 60;

function isActive(pc: HWComputadora): boolean {
  const ts = pc.ultima_sincronizacion ?? pc.ultima_sync ?? null;
  if (!ts || typeof ts.seconds !== 'number') return false;
  return Math.floor(Date.now() / 1000) - ts.seconds < ACTIVE_THRESHOLD_SEC;
}

function formatSync(ts: HWComputadora['ultima_sync']) {
  if (!ts || typeof (ts as { seconds?: number })?.seconds !== 'number') return '—';
  return formatTimestamp(ts as { seconds: number; nanoseconds: number });
}

function formatPct(val: number | string | null | undefined) {
  if (val == null) return null;
  if (typeof val === 'number') return val;
  const n = parseFloat(String(val));
  return isNaN(n) ? null : n;
}

function getUsageColor(pct: number): string {
  if (pct >= 85) return 'var(--color-danger)';
  if (pct >= 70) return '#f59e0b';
  return 'var(--color-sidebar-bar)';
}

function UsageBar({ pct }: { pct: number }) {
  return (
    <div className="pc-usage-bar">
      <div
        className="pc-usage-bar-fill"
        style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: getUsageColor(pct) }}
      />
    </div>
  );
}

// ── Card de computadora ───────────────────────────────────────────
function PCCard({ pc, onClick }: { pc: HWComputadora; onClick: () => void }) {
  const { enviarActualizarDatos, sending } = useComandoHW(pc.id);
  const active = isActive(pc);
  const cpuPct = formatPct(pc.cpu_uso_porcentaje ?? pc.cpu);
  const ramPct = formatPct(pc.ram_uso_porcentaje ?? pc.ram);
  const ts = pc.ultima_sincronizacion ?? pc.ultima_sync ?? null;

  return (
    <div className="pc-card">
      <div className="pc-card-header" onClick={onClick} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && onClick()}>
        <div className="pc-card-title-row">
          <span
            className="pc-card-status-dot"
            style={{ background: active ? '#2e7d32' : '#bbb' }}
            title={active ? 'Activo' : 'Sin actividad reciente'}
          />
          <span className="pc-card-hostname">{pc.hostname ?? pc.id}</span>
          {(pc.version_agente ?? pc.version) && (
            <code className="pc-card-version">v{pc.version_agente ?? pc.version}</code>
          )}
        </div>
        <div className="pc-card-so">{pc.sistema_operativo ?? pc.so ?? '—'}</div>
      </div>

      <div className="pc-card-body" onClick={onClick} role="button" tabIndex={-1} onKeyDown={(e) => e.key === 'Enter' && onClick()}>
        {cpuPct != null && (
          <div className="pc-card-metric">
            <div className="pc-card-metric-row">
              <span className="pc-card-metric-label">CPU</span>
              <span className="pc-card-metric-value" style={{ color: getUsageColor(cpuPct) }}>{cpuPct}%</span>
            </div>
            <UsageBar pct={cpuPct} />
          </div>
        )}
        {ramPct != null && (
          <div className="pc-card-metric">
            <div className="pc-card-metric-row">
              <span className="pc-card-metric-label">RAM{pc.ram_total_gb != null ? ` · ${pc.ram_total_gb} GB` : ''}</span>
              <span className="pc-card-metric-value" style={{ color: getUsageColor(ramPct) }}>{ramPct}%</span>
            </div>
            <UsageBar pct={ramPct} />
          </div>
        )}
        {pc.ip_publica && (
          <div className="pc-card-info-row">
            <span className="pc-card-info-label">IP publica</span>
            <span className="pc-card-info-value">{pc.ip_publica}</span>
          </div>
        )}
        {(pc.anydesk_id ?? pc.anydesk) && (
          <div className="pc-card-info-row">
            <span className="pc-card-info-label">AnyDesk</span>
            <span className="pc-card-info-value">{pc.anydesk_id ?? pc.anydesk}</span>
          </div>
        )}
        <div className="pc-card-info-row">
          <span className="pc-card-info-label">Ultima sync</span>
          <span className="pc-card-info-value" title={formatSync(ts)}>{formatRelative(ts)}</span>
        </div>
      </div>

      <div className="pc-card-footer">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          style={{ width: '100%' }}
          disabled={sending}
          onClick={(e) => { e.stopPropagation(); enviarActualizarDatos(); }}
        >
          {sending ? 'Enviando...' : 'Actualizar datos'}
        </button>
      </div>
    </div>
  );
}

// ── Pagina principal ──────────────────────────────────────────────
export function Computadoras() {
  const { computadoras, loading, error } = useComputadorasHW();
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className="page">
        <h1>Computadoras</h1>
        <p className="muted">Cargando...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <h1>Computadoras</h1>
        <p className="error">Error: {error}</p>
      </div>
    );
  }

  return (
    <div className="page">
      <h1>Computadoras — {computadoras.length} PC{computadoras.length !== 1 ? 's' : ''}</h1>
      <p className="muted">
        Hace clic en una tarjeta para ver el detalle completo. El boton envia el comando al agente.
      </p>

      {computadoras.length === 0 ? (
        <div className="dash-panel">
          <p className="muted">No hay documentos en <code>computadoras</code>.</p>
        </div>
      ) : (
        <div className="pc-card-grid">
          {computadoras.map((pc) => (
            <PCCard key={pc.id} pc={pc} onClick={() => navigate(`/computadoras/${pc.id}`)} />
          ))}
        </div>
      )}
    </div>
  );
}
