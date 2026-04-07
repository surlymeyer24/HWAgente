import { useTareasHW } from '../hooks/useTareasHW';
import { useComputadorasHW } from '../hooks/useComputadorasHW';
import { useComandoHW } from '../hooks/useComandoHW';
import { useLogsActualizacion } from '../hooks/useLogsActualizacion';
import { formatTimestamp } from '../lib/format';
import { EVENTO_BADGE_HW } from '../lib/comandoLogBadges';
import type { HWTarea } from '../types/firestore';

function getLogTexto(t: HWTarea): string {
  if (t.log) return t.log;
  if (Array.isArray(t.logs) && t.logs.length > 0) return t.logs.join('\n');
  if (t.resultado) return t.resultado;
  return '';
}

function ComandosMaquina({ computadoraId, hostname }: { computadoraId: string; hostname: string }) {
  const { enviarActualizarDatos, enviarActualizarAgente, sending, error } = useComandoHW(computadoraId);
  return (
    <div className="comandos-hw">
      <span className="comandos-hw-host">{hostname || computadoraId}</span>
      <div className="actions">
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={sending}
          onClick={() => enviarActualizarDatos()}
        >
          Actualizar datos
        </button>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={sending}
          onClick={() => enviarActualizarAgente()}
        >
          Actualizar agente
        </button>
      </div>
      {error && <p className="error small">{error}</p>}
    </div>
  );
}

export function Tareas() {
  const { tareas, loading, error } = useTareasHW();
  const { computadoras, loading: loadingPcs } = useComputadorasHW();
  const { logs, loading: loadingLogs } = useLogsActualizacion(100);

  if (loading) {
    return (
      <div className="page">
        <h1>Tareas</h1>
        <p className="muted">Cargando…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page">
        <h1>Tareas</h1>
        <p className="error">Error: {error}</p>
      </div>
    );
  }

  return (
    <div className="page">
      <h1>Tareas — {tareas.length} tarea{tareas.length !== 1 ? 's' : ''}</h1>
      <p className="muted">
        Colección: <code>tareas</code>. Los comandos se escriben en Firestore y el agente los lee.
      </p>

      <section className="section">
        <h2>Comandos a máquinas</h2>
        <p className="muted">
          Envía <strong>Actualizar datos</strong> o <strong>Actualizar agente</strong>.
          El agente HW en esa máquina leerá el comando desde Firestore.
        </p>
        {loadingPcs ? (
          <p className="muted">Cargando computadoras…</p>
        ) : computadoras.length === 0 ? (
          <p className="muted">No hay computadoras en la BD.</p>
        ) : (
          <div className="comandos-hw-list">
            {computadoras.map((c) => (
              <ComandosMaquina key={c.id} computadoraId={c.id} hostname={c.hostname ?? c.id} />
            ))}
          </div>
        )}
      </section>

      <section className="section">
        <h2>Listado de tareas</h2>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Título</th>
                <th>Descripción</th>
                <th>Estado</th>
                <th>Hostname / Máquina</th>
                <th>Fecha</th>
                <th>Logs</th>
              </tr>
            </thead>
            <tbody>
              {tareas.length === 0 ? (
                <tr>
                  <td colSpan={6} className="table-empty">
                    No hay documentos en <code>tareas</code>.
                  </td>
                </tr>
              ) : (
                tareas.map((t) => {
                  const logTexto = getLogTexto(t);
                  return (
                    <tr key={t.id}>
                      <td>{t.titulo ?? '—'}</td>
                      <td>
                        {(t.descripcion ?? '—').slice(0, 50)}
                        {(t.descripcion?.length ?? 0) > 50 ? '…' : ''}
                      </td>
                      <td>{t.estado ?? '—'}</td>
                      <td>{t.hostname ?? t.maquinaId ?? '—'}</td>
                      <td>
                        {t.fechaHora && typeof (t.fechaHora as { seconds: number }).seconds === 'number'
                          ? formatTimestamp(t.fechaHora as { seconds: number; nanoseconds: number })
                          : '—'}
                      </td>
                      <td className="td-log">
                        {logTexto ? (
                          <pre className="tarea-log">{logTexto}</pre>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>—</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="section">
        <h2>Historial de comandos</h2>
        <p className="muted">
          Eventos en tiempo real desde <code>logs_actualizaciones</code>. Últimas 100 entradas.
        </p>
        {loadingLogs ? (
          <p className="muted">Cargando logs…</p>
        ) : logs.length === 0 ? (
          <p className="muted">Sin entradas aún. Se registran cuando el agente procesa un comando.</p>
        ) : (
          <div className="table-wrap table-wrap--scroll">
            <table className="table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>PC</th>
                  <th>Evento</th>
                  <th>Detalle</th>
                  <th>Versión</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id}>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {l.timestamp ? formatTimestamp(l.timestamp) : '—'}
                    </td>
                    <td>{l.hostname || l.uuid || '—'}</td>
                    <td>
                      <span className={`badge ${EVENTO_BADGE_HW[l.evento] ?? 'badge-neutral'}`}>
                        {l.evento}
                      </span>
                    </td>
                    <td className="td-detalle-log">{l.detalle || '—'}</td>
                    <td>{l.version_agente || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
