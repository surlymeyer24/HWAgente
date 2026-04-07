import React, { useState } from 'react';
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

// ── Mini bar ──────────────────────────────────────────────────────
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
            <span className="pc-card-info-label">IP pública</span>
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
          <span className="pc-card-info-label">Última sync</span>
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
          {sending ? 'Enviando…' : '↻ Actualizar datos'}
        </button>
      </div>
    </div>
  );
}

// ── Modal de detalle ──────────────────────────────────────────────
function ModalDetallePC({ pc, onClose }: { pc: HWComputadora; onClose: () => void }) {
  const sw: HWSoftwareCritico | null = pc.software_critico ?? null;
  const perif: HWPerifericos | null = pc.perifericos ?? null;
  const red: HWRed | null = pc.red ?? null;
  const apps = (pc.aplicaciones_activas ?? []) as HWAplicacionActiva[];
  const servicios = (pc.servicios_criticos ?? []) as HWServicioCritico[];
  const wu = pc.windows_updates;
  const pendientes = wu && Array.isArray((wu as { pendientes?: unknown[] }).pendientes) ? (wu as { pendientes: Record<string, unknown>[] }).pendientes : [];
  const historial = wu && Array.isArray((wu as { historial_reciente?: unknown[] }).historial_reciente) ? (wu as { historial_reciente: Record<string, unknown>[] }).historial_reciente : [];
  const cpuPct = formatPct(pc.cpu_uso_porcentaje ?? pc.cpu);
  const ramPct = formatPct(pc.ram_uso_porcentaje ?? pc.ram);

  return (
    <div className="pc-modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="pc-modal" onClick={(e) => e.stopPropagation()}>
        <div className="pc-modal-header">
          <h2>{pc.hostname ?? pc.id}</h2>
          <button type="button" className="pc-modal-close" onClick={onClose} aria-label="Cerrar">×</button>
        </div>
        <div className="pc-modal-body">

          {/* General */}
          <section className="pc-modal-section">
            <h3>General</h3>
            <dl className="dl dl-compact">
              <dt>SO</dt><dd>{pc.sistema_operativo ?? pc.so ?? '—'}</dd>
              <dt>IP pública</dt><dd>{pc.ip_publica ?? '—'}</dd>
              <dt>AnyDesk</dt><dd>{pc.anydesk_id ?? pc.anydesk ?? '—'}</dd>
              <dt>Versión agente</dt><dd>{pc.version_agente ?? pc.version ?? '—'}</dd>
              <dt>Última sync</dt><dd>{formatSync(pc.ultima_sincronizacion ?? pc.ultima_sync)}</dd>
              <dt>Estado comando</dt><dd>{pc.cmd_estado ?? pc.estado_conexion ?? '—'}</dd>
            </dl>
          </section>

          {/* Componentes */}
          <section className="pc-modal-section">
            <h3>Componentes</h3>

            {(pc.procesador || cpuPct != null) && (
              <div className="pc-comp-item">
                <div className="pc-comp-header">
                  <span className="pc-comp-label">Procesador{(pc as Record<string, unknown>).nucleos_fisicos != null ? ` · ${(pc as Record<string, unknown>).nucleos_fisicos} núcleos` : ''}</span>
                  {cpuPct != null && <span className="pc-comp-usage">{cpuPct}%</span>}
                </div>
                {pc.procesador && <div className="pc-comp-value">{pc.procesador}</div>}
                {cpuPct != null && <UsageBar pct={cpuPct} />}
              </div>
            )}

            {(pc.ram_total_gb != null || ramPct != null) && (
              <div className="pc-comp-item">
                <div className="pc-comp-header">
                  <span className="pc-comp-label">RAM{pc.ram_total_gb != null ? ` · ${pc.ram_total_gb} GB` : ''}</span>
                  {ramPct != null && <span className="pc-comp-usage">{ramPct}%</span>}
                </div>
                {ramPct != null && <UsageBar pct={ramPct} />}
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
              </div>
            )}

            {pc.discos != null && (() => {
              const list: HWDisco[] = typeof pc.discos === 'string' ? [] : Array.isArray(pc.discos) ? pc.discos as HWDisco[] : [pc.discos as HWDisco];
              if (list.length === 0) return null;
              const groups = new Map<string, HWDisco[]>();
              list.forEach((d, i) => {
                const key = d.disco_fisico_index != null ? String(d.disco_fisico_index) : `__solo_${i}`;
                if (!groups.has(key)) groups.set(key, []);
                groups.get(key)!.push(d);
              });
              return (
                <div className="pc-comp-item">
                  <div className="pc-comp-header"><span className="pc-comp-label">Discos</span></div>
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
                </div>
              );
            })()}
          </section>

          {/* Software crítico */}
          {(sw?.antivirus?.length || sw?.navegadores?.length) ? (
            <section className="pc-modal-section">
              <h3>Software crítico</h3>
              {sw?.antivirus && sw.antivirus.length > 0 && (
                <>
                  <div className="pc-modal-sub">Antivirus</div>
                  <ul className="pc-modal-list">
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
                  <div className="pc-modal-sub">Navegadores</div>
                  <ul className="pc-modal-list">
                    {sw.navegadores.map((br, i) => (
                      <li key={i}>{br.nombre ?? '—'} {br.version && <span className="pc-muted">{br.version}</span>}</li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          ) : null}

          {/* Periféricos */}
          {perif && (perif.monitores?.length || perif.dispositivos_usb?.length || perif.impresoras?.length || perif.audio?.salida?.length) ? (
            <section className="pc-modal-section">
              <h3>Periféricos</h3>
              {perif.monitores && perif.monitores.length > 0 && (
                <>
                  <div className="pc-modal-sub">Monitores</div>
                  <ul className="pc-modal-list">
                    {perif.monitores.map((m, i) => (
                      <li key={i}>{m.nombre ?? '—'} {m.resolucion && <span className="pc-muted">{m.resolucion}</span>}</li>
                    ))}
                  </ul>
                </>
              )}
              {perif.dispositivos_usb && perif.dispositivos_usb.length > 0 && (
                <>
                  <div className="pc-modal-sub">USB</div>
                  <ul className="pc-modal-list">
                    {perif.dispositivos_usb.map((u, i) => (
                      <li key={i}>
                        {u.nombre ?? '—'}
                        {u.categoria && u.categoria !== u.nombre && <span className="pc-muted"> ({u.categoria})</span>}
                        {u.fabricante && u.fabricante !== '—' && !u.nombre?.startsWith(u.fabricante) && <span className="pc-muted"> — {u.fabricante}</span>}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {perif.impresoras && perif.impresoras.length > 0 && (
                <>
                  <div className="pc-modal-sub">Impresoras</div>
                  <ul className="pc-modal-list">
                    {perif.impresoras.map((imp, i) => <li key={i}>{imp.nombre ?? '—'}</li>)}
                  </ul>
                </>
              )}
              {perif.audio?.salida && perif.audio.salida.length > 0 && (
                <>
                  <div className="pc-modal-sub">Audio salida</div>
                  <ul className="pc-modal-list">
                    {perif.audio.salida.map((au, i) => <li key={i}>{au.nombre ?? '—'}</li>)}
                  </ul>
                </>
              )}
            </section>
          ) : null}

          {/* Red */}
          {red && (red.trafico || (red.adaptadores && red.adaptadores.length > 0)) && (
            <section className="pc-modal-section">
              <h3>Red</h3>
              {red.trafico && (
                <dl className="dl dl-compact">
                  <dt>Enviado</dt><dd>{red.trafico.enviado_mb != null ? `${red.trafico.enviado_mb} MB` : '—'}</dd>
                  <dt>Recibido</dt><dd>{red.trafico.recibido_mb != null ? `${red.trafico.recibido_mb} MB` : '—'}</dd>
                </dl>
              )}
              {red.adaptadores && red.adaptadores.length > 0 && (
                <>
                  <div className="pc-modal-sub">Adaptadores</div>
                  <ul className="pc-modal-list">
                    {red.adaptadores.map((ad, i) => (
                      <li key={i}>{ad.nombre ?? '—'} {ad.ip && <span className="pc-muted">{ad.ip}</span>}</li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )}

          {/* Usuarios */}
          {pc.usuarios && Object.keys(pc.usuarios).length > 0 && (
            <section className="pc-modal-section">
              <h3>Usuarios</h3>
              <dl className="dl dl-compact">
                {Object.entries(pc.usuarios).map(([k, v]) => (
                  <React.Fragment key={k}><dt>{k}</dt><dd>{String(v)}</dd></React.Fragment>
                ))}
              </dl>
            </section>
          )}

          {/* Servicios críticos */}
          {servicios.length > 0 && (
            <section className="pc-modal-section">
              <h3>Servicios críticos</h3>
              <ul className="pc-modal-list">
                {servicios.map((sc, i) => (
                  <li key={i}>
                    {sc.nombre ?? '—'}{' '}
                    <span className={sc.estado === 'Running' ? 'pc-status-ok' : 'pc-status-bad'}>{sc.estado ?? '—'}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {/* Aplicaciones activas */}
          {apps.length > 0 && (
            <section className="pc-modal-section">
              <h3>Aplicaciones (RAM / CPU)</h3>
              <ul className="pc-modal-list pc-modal-apps">
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

          {/* Windows Updates */}
          {(pendientes.length > 0 || historial.length > 0) && (
            <section className="pc-modal-section">
              <h3>Windows Updates</h3>
              {pendientes.length > 0 && (
                <>
                  <div className="pc-modal-sub">Pendientes</div>
                  <ul className="pc-modal-list">
                    {pendientes.map((up: Record<string, unknown>, i) => (
                      <li key={i}>{String(up.titulo ?? up.kb ?? '—')}</li>
                    ))}
                  </ul>
                </>
              )}
              {historial.length > 0 && (
                <>
                  <div className="pc-modal-sub">Historial reciente</div>
                  <ul className="pc-modal-list">
                    {historial.slice(0, 5).map((uh: Record<string, unknown>, i) => (
                      <li key={i}>{String(uh.titulo ?? uh.kb ?? '—')}</li>
                    ))}
                  </ul>
                </>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────
export function Computadoras() {
  const { computadoras, loading, error } = useComputadorasHW();
  const [selected, setSelected] = useState<HWComputadora | null>(null);

  if (loading) {
    return (
      <div className="page">
        <h1>Computadoras</h1>
        <p className="muted">Cargando…</p>
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
        Hacé clic en una tarjeta para ver el detalle completo. El botón envía el comando al agente.
      </p>

      {computadoras.length === 0 ? (
        <div className="dash-panel">
          <p className="muted">No hay documentos en <code>computadoras</code>.</p>
        </div>
      ) : (
        <div className="pc-card-grid">
          {computadoras.map((pc) => (
            <PCCard key={pc.id} pc={pc} onClick={() => setSelected(pc)} />
          ))}
        </div>
      )}

      {selected && (
        <ModalDetallePC pc={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}
