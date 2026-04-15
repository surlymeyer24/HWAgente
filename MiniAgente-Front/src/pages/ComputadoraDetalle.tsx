import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useComputadorasHW } from '../hooks/useComputadorasHW';
import { useComandoHW } from '../hooks/useComandoHW';
import { formatTimestamp, formatRelative } from '../lib/format';
import type {
  HWComputadora,
  HWDisco,
  HWModuloRAM,
  HWPerifericos,
  HWRed,
  HWSoftwareCritico,
  HWAplicacionActiva,
  HWServicioCritico,
} from '../types/firestore';

const ACTIVE_THRESHOLD_SEC = 10 * 60;

type TabId = 'general' | 'hardware' | 'red' | 'software' | 'perifericos';

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

// ── Tab: General ─────────────────────────────────────────────────
function TabGeneral({ pc }: { pc: HWComputadora }) {
  return (
    <>
      <section className="detail-section">
        <h3>Informacion del equipo</h3>
        <dl className="dl dl-compact">
          <dt>SO</dt><dd>{pc.sistema_operativo ?? pc.so ?? '—'}</dd>
          <dt>IP publica</dt><dd>{pc.ip_publica ?? '—'}</dd>
          <dt>AnyDesk</dt><dd>{pc.anydesk_id ?? pc.anydesk ?? '—'}</dd>
          <dt>Version agente</dt><dd>{pc.version_agente ?? pc.version ?? '—'}</dd>
          <dt>Ultima sync</dt><dd>{formatSync(pc.ultima_sincronizacion ?? pc.ultima_sync)}</dd>
          <dt>Estado comando</dt><dd>{pc.cmd_estado ?? pc.estado_conexion ?? '—'}</dd>
        </dl>
      </section>

      {pc.usuarios && Object.keys(pc.usuarios).length > 0 && (
        <section className="detail-section">
          <h3>Usuarios</h3>
          <dl className="dl dl-compact">
            {Object.entries(pc.usuarios).map(([k, v]) => (
              <React.Fragment key={k}><dt>{k}</dt><dd>{String(v)}</dd></React.Fragment>
            ))}
          </dl>
        </section>
      )}
    </>
  );
}

// ── Tab: Hardware ────────────────────────────────────────────────
function TabHardware({ pc }: { pc: HWComputadora }) {
  const cpuPct = formatPct(pc.cpu_uso_porcentaje ?? pc.cpu);
  const ramPct = formatPct(pc.ram_uso_porcentaje ?? pc.ram);

  const discosList: HWDisco[] = (() => {
    if (!pc.discos || typeof pc.discos === 'string') return [];
    return Array.isArray(pc.discos) ? pc.discos as HWDisco[] : [pc.discos as HWDisco];
  })();

  const groups = new Map<string, HWDisco[]>();
  discosList.forEach((d, i) => {
    const key = d.disco_fisico_index != null ? String(d.disco_fisico_index) : `__solo_${i}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(d);
  });

  return (
    <>
      {(pc.procesador || cpuPct != null) && (
        <section className="detail-section">
          <h3>Procesador{(pc as Record<string, unknown>).nucleos_fisicos != null ? ` — ${(pc as Record<string, unknown>).nucleos_fisicos} nucleos` : ''}</h3>
          {pc.procesador && <div className="detail-value">{pc.procesador}</div>}
          {cpuPct != null && (
            <div className="detail-metric">
              <span className="detail-metric-value" style={{ color: getUsageColor(cpuPct) }}>{cpuPct}%</span>
              <UsageBar pct={cpuPct} />
            </div>
          )}
        </section>
      )}

      {(pc.ram_total_gb != null || ramPct != null) && (
        <section className="detail-section">
          <h3>RAM{pc.ram_total_gb != null ? ` — ${pc.ram_total_gb} GB` : ''}</h3>
          {ramPct != null && (
            <div className="detail-metric">
              <span className="detail-metric-value" style={{ color: getUsageColor(ramPct) }}>{ramPct}%</span>
              <UsageBar pct={ramPct} />
            </div>
          )}
          {pc.modulos_ram && (pc.modulos_ram as HWModuloRAM[]).length > 0 && (
            <div className="pc-ram-chips">
              {(pc.modulos_ram as HWModuloRAM[]).map((m, i) => (
                <span key={i} className="pc-ram-chip">
                  {m.fabricante && m.fabricante !== 'Desconocido' ? m.fabricante : '—'}
                  {m.capacidad_gb != null && ` · ${m.capacidad_gb} GB`}
                  {m.velocidad_mhz != null && m.velocidad_mhz > 0 && ` · ${m.velocidad_mhz} MHz`}
                </span>
              ))}
            </div>
          )}
        </section>
      )}

      {discosList.length > 0 && (
        <section className="detail-section">
          <h3>Discos</h3>
          {Array.from(groups.entries()).map(([key, partitions]) => {
            const rep = partitions[0];
            const tipo = (rep.tipo_disco ?? '').trim().toLowerCase();
            return (
              <div key={key} className="pc-disk-physical">
                <div className="pc-disk-physical-header">
                  {rep.tipo_disco && <span className={`pc-disk-badge pc-disk-badge-${tipo}`}>{rep.tipo_disco}</span>}
                  {rep.modelo_disco && <span className="pc-muted">{rep.modelo_disco}</span>}
                </div>
                {partitions.map((d, i) => {
                  const pct = d.porcentaje_usado ?? (d.total_gb && d.total_gb > 0 ? Math.round(((d.usado_gb ?? 0) / d.total_gb) * 100) : null);
                  return (
                    <div key={i} className="pc-disk-row">
                      <div className="pc-disk-info">
                        <span className="pc-disk-mount">{d.punto_montaje ?? d.dispositivo ?? '?'}</span>
                        {d.total_gb != null && d.total_gb > 0 && (
                          <span className="pc-disk-space">{d.usado_gb ?? 0} / {d.total_gb} GB</span>
                        )}
                      </div>
                      {pct != null && <UsageBar pct={pct} />}
                    </div>
                  );
                })}
              </div>
            );
          })}
        </section>
      )}
    </>
  );
}

// ── Tab: Red ─────────────────────────────────────────────────────
function TabRed({ pc }: { pc: HWComputadora }) {
  const red: HWRed | null = pc.red ?? null;
  if (!red) return <p className="muted">Sin datos de red.</p>;

  return (
    <>
      {(red.wifi_ssid || red.trafico) && (
        <section className="detail-section">
          <h3>Conexion</h3>
          <dl className="dl dl-compact">
            {red.wifi_ssid && <><dt>Wi-Fi (SSID)</dt><dd>{red.wifi_ssid}</dd></>}
            {red.trafico && (
              <>
                <dt>Enviado</dt>
                <dd>
                  {red.trafico.enviado_mb != null
                    ? `${red.trafico.enviado_mb} MB`
                    : red.trafico.bytes_enviados_mb != null
                      ? `${red.trafico.bytes_enviados_mb} MB`
                      : '—'}
                </dd>
                <dt>Recibido</dt>
                <dd>
                  {red.trafico.recibido_mb != null
                    ? `${red.trafico.recibido_mb} MB`
                    : red.trafico.bytes_recibidos_mb != null
                      ? `${red.trafico.bytes_recibidos_mb} MB`
                      : '—'}
                </dd>
              </>
            )}
          </dl>
        </section>
      )}

      {red.adaptadores && red.adaptadores.length > 0 && (
        <section className="detail-section">
          <h3>Adaptadores</h3>
          <ul className="detail-list">
            {red.adaptadores.map((ad, i) => {
              const ipTxt = ad.ip ?? (ad.ips?.length ? ad.ips.join(', ') : '');
              const redTxt = [ad.perfil_red, ad.categoria_red].filter(Boolean).join(' · ');
              return (
                <li key={i}>
                  <strong>{ad.nombre ?? '—'}</strong>
                  {redTxt && <span className="pc-muted"> — {redTxt}</span>}
                  {ipTxt && <span className="pc-muted"> {ipTxt}</span>}
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </>
  );
}

// ── Tab: Software ────────────────────────────────────────────────
function TabSoftware({ pc }: { pc: HWComputadora }) {
  const sw: HWSoftwareCritico | null = pc.software_critico ?? null;
  const servicios = (pc.servicios_criticos ?? []) as HWServicioCritico[];
  const apps = (pc.aplicaciones_activas ?? []) as HWAplicacionActiva[];
  const wu = pc.windows_updates;
  const pendientes = wu && Array.isArray((wu as { pendientes?: unknown[] }).pendientes) ? (wu as { pendientes: Record<string, unknown>[] }).pendientes : [];
  const historial = wu && Array.isArray((wu as { historial_reciente?: unknown[] }).historial_reciente) ? (wu as { historial_reciente: Record<string, unknown>[] }).historial_reciente : [];

  const hasContent = sw?.antivirus?.length || sw?.navegadores?.length || servicios.length > 0 || apps.length > 0 || pendientes.length > 0 || historial.length > 0;
  if (!hasContent) return <p className="muted">Sin datos de software.</p>;

  return (
    <>
      {(sw?.antivirus?.length || sw?.navegadores?.length) ? (
        <section className="detail-section">
          <h3>Software critico</h3>
          {sw?.antivirus && sw.antivirus.length > 0 && (
            <>
              <div className="detail-sub">Antivirus</div>
              <ul className="detail-list">
                {sw.antivirus.map((av, i) => (
                  <li key={i}>
                    {av.nombre ?? '—'}{' '}
                    <span className={av.activo === true || av.activo === 'True' ? 'pc-status-ok' : 'pc-status-bad'}>
                      {av.activo === true || av.activo === 'True' ? 'activo' : 'inactivo'}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {sw?.navegadores && sw.navegadores.length > 0 && (
            <>
              <div className="detail-sub">Navegadores</div>
              <ul className="detail-list">
                {sw.navegadores.map((br, i) => (
                  <li key={i}>{br.nombre ?? '—'} {br.version && <span className="pc-muted">{br.version}</span>}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      ) : null}

      {servicios.length > 0 && (
        <section className="detail-section">
          <h3>Servicios criticos</h3>
          <ul className="detail-list">
            {servicios.map((sc, i) => (
              <li key={i}>
                {sc.nombre ?? '—'}{' '}
                <span className={sc.estado === 'Running' ? 'pc-status-ok' : 'pc-status-bad'}>{sc.estado ?? '—'}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {apps.length > 0 && (
        <section className="detail-section">
          <h3>Aplicaciones activas (RAM / CPU)</h3>
          <ul className="detail-list detail-apps">
            {apps
              .slice()
              .sort((a, b) => (Number(b.ram_mb) || 0) - (Number(a.ram_mb) || 0))
              .slice(0, 15)
              .map((ap, i) => (
                <li key={i}>
                  <span className="pc-app-name">{ap.nombre ?? '—'}</span>
                  {ap.ram_mb != null && <span className="pc-app-ram">{ap.ram_mb} MB</span>}
                  {ap.cpu != null && <span className="pc-muted">CPU {ap.cpu}%</span>}
                </li>
              ))}
          </ul>
        </section>
      )}

      {(pendientes.length > 0 || historial.length > 0) && (
        <section className="detail-section">
          <h3>Windows Updates</h3>
          {pendientes.length > 0 && (
            <>
              <div className="detail-sub">Pendientes</div>
              <ul className="detail-list">
                {pendientes.map((up: Record<string, unknown>, i) => (
                  <li key={i}>{String(up.titulo ?? up.kb ?? '—')}</li>
                ))}
              </ul>
            </>
          )}
          {historial.length > 0 && (
            <>
              <div className="detail-sub">Historial reciente</div>
              <ul className="detail-list">
                {historial.slice(0, 5).map((uh: Record<string, unknown>, i) => (
                  <li key={i}>{String(uh.titulo ?? uh.kb ?? '—')}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </>
  );
}

// ── Tab: Perifericos ─────────────────────────────────────────────
function TabPeripherals({ pc }: { pc: HWComputadora }) {
  const perif: HWPerifericos | null = pc.perifericos ?? null;
  if (!perif || !(perif.monitores?.length || perif.dispositivos_usb?.length || perif.impresoras?.length || perif.audio?.salida?.length)) {
    return <p className="muted">Sin perifericos detectados.</p>;
  }

  return (
    <>
      {perif.monitores && perif.monitores.length > 0 && (
        <section className="detail-section">
          <h3>Monitores</h3>
          <ul className="detail-list">
            {perif.monitores.map((m, i) => (
              <li key={i}>{m.nombre ?? '—'} {m.resolucion && <span className="pc-muted">{m.resolucion}</span>}</li>
            ))}
          </ul>
        </section>
      )}

      {perif.dispositivos_usb && perif.dispositivos_usb.length > 0 && (
        <section className="detail-section">
          <h3>Dispositivos USB</h3>
          <ul className="detail-list">
            {perif.dispositivos_usb.map((u, i) => {
              const cx = u.conexion;
              const cxLbl =
                cx === 'bluetooth' ? 'Bluetooth'
                : cx === 'inalambrico_usb' ? 'Inalambrico (receptor USB)'
                : cx === 'usb' ? 'USB cableado'
                : null;
              return (
                <li key={i}>
                  {u.nombre ?? '—'}
                  {u.categoria && u.categoria !== u.nombre && <span className="pc-muted"> ({u.categoria})</span>}
                  {u.fabricante && u.fabricante !== '—' && !u.nombre?.startsWith(u.fabricante) && (
                    <span className="pc-muted"> — {u.fabricante}</span>
                  )}
                  {cxLbl && <span className="pc-muted"> · {cxLbl}</span>}
                </li>
              );
            })}
          </ul>
        </section>
      )}

      {perif.impresoras && perif.impresoras.length > 0 && (
        <section className="detail-section">
          <h3>Impresoras</h3>
          <ul className="detail-list">
            {perif.impresoras.map((imp, i) => <li key={i}>{imp.nombre ?? '—'}</li>)}
          </ul>
        </section>
      )}

      {perif.audio?.salida && perif.audio.salida.length > 0 && (
        <section className="detail-section">
          <h3>Audio salida</h3>
          <ul className="detail-list">
            {perif.audio.salida.map((au, i) => <li key={i}>{au.nombre ?? '—'}</li>)}
          </ul>
        </section>
      )}
    </>
  );
}

// ── Tabs config ──────────────────────────────────────────────────
const TABS: { id: TabId; label: string }[] = [
  { id: 'general', label: 'General' },
  { id: 'hardware', label: 'Hardware' },
  { id: 'red', label: 'Red' },
  { id: 'software', label: 'Software' },
  { id: 'perifericos', label: 'Perifericos' },
];

// ── Pagina principal ─────────────────────────────────────────────
export function ComputadoraDetalle() {
  const { id } = useParams<{ id: string }>();
  const { computadoras, loading, error } = useComputadorasHW();
  const { enviarActualizarDatos, sending } = useComandoHW(id ?? '');
  const [activeTab, setActiveTab] = useState<TabId>('general');

  if (loading) {
    return (
      <div className="page">
        <Link to="/computadoras" className="btn btn-secondary btn-sm">Volver</Link>
        <p className="muted">Cargando...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <Link to="/computadoras" className="btn btn-secondary btn-sm">Volver</Link>
        <p className="error">Error: {error}</p>
      </div>
    );
  }

  const pc = computadoras.find(c => c.id === id);
  if (!pc) {
    return (
      <div className="page">
        <Link to="/computadoras" className="btn btn-secondary btn-sm">Volver</Link>
        <p className="muted">Equipo no encontrado.</p>
      </div>
    );
  }

  const active = isActive(pc);
  const ts = pc.ultima_sincronizacion ?? pc.ultima_sync ?? null;

  return (
    <div className="page">
      <Link to="/computadoras" className="btn btn-secondary btn-sm">Volver</Link>

      {/* Header */}
      <div className="detail-header">
        <div className="detail-header-left">
          <span
            className="pc-card-status-dot"
            style={{ background: active ? '#2e7d32' : '#bbb', width: 10, height: 10 }}
            title={active ? 'Activo' : 'Sin actividad reciente'}
          />
          <h1 className="detail-hostname">{pc.hostname ?? pc.id}</h1>
          {(pc.version_agente ?? pc.version) && (
            <code className="pc-card-version">v{pc.version_agente ?? pc.version}</code>
          )}
        </div>
        <div className="detail-header-right">
          <span className="detail-sync" title={formatSync(ts)}>{formatRelative(ts)}</span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={sending}
            onClick={enviarActualizarDatos}
          >
            {sending ? 'Enviando...' : 'Actualizar datos'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="detail-tabs">
        {TABS.map(tab => (
          <button
            key={tab.id}
            type="button"
            className={`detail-tab${activeTab === tab.id ? ' detail-tab--active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="detail-content">
        {activeTab === 'general' && <TabGeneral pc={pc} />}
        {activeTab === 'hardware' && <TabHardware pc={pc} />}
        {activeTab === 'red' && <TabRed pc={pc} />}
        {activeTab === 'software' && <TabSoftware pc={pc} />}
        {activeTab === 'perifericos' && <TabPeripherals pc={pc} />}
      </div>
    </div>
  );
}
