import { useEffect, useMemo, useState } from 'react';
import { useTareasHW } from '../hooks/useTareasHW';
import { useComputadorasHW } from '../hooks/useComputadorasHW';
import { useComandoHW, enviarComandoAMaquinas } from '../hooks/useComandoHW';
import {
  useLogsActualizacion,
  deleteLogsActualizacionCoinciden,
  type FiltroFechasLogs,
} from '../hooks/useLogsActualizacion';
import { formatTimestamp } from '../lib/format';
import { EVENTO_BADGE_HW } from '../lib/comandoLogBadges';
import type { HWTarea } from '../types/firestore';

function getLogTexto(t: HWTarea): string {
  if (t.log) return t.log;
  if (Array.isArray(t.logs) && t.logs.length > 0) return t.logs.join('\n');
  if (t.resultado) return t.resultado;
  return '';
}

/** `YYYY-MM-DD` → inicio del día en hora local */
function inicioDiaLocal(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d, 0, 0, 0, 0);
}

/** `YYYY-MM-DD` → fin del día en hora local */
function finDiaLocal(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d, 23, 59, 59, 999);
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
  const [logFechaDesde, setLogFechaDesde] = useState('');
  const [logFechaHasta, setLogFechaHasta] = useState('');
  const [borrandoLogs, setBorrandoLogs] = useState(false);
  const [feedbackBorrarLogs, setFeedbackBorrarLogs] = useState<{ ok: boolean; text: string } | null>(
    null
  );
  const [enviandoActualizarTodas, setEnviandoActualizarTodas] = useState(false);
  const [errorActualizarTodas, setErrorActualizarTodas] = useState<string | null>(null);

  const rangoFechasInvalido = Boolean(
    logFechaDesde && logFechaHasta && logFechaDesde > logFechaHasta
  );

  const filtroLogsActualizacion = useMemo((): FiltroFechasLogs | null => {
    if (rangoFechasInvalido) return null;
    return {
      desde: logFechaDesde ? inicioDiaLocal(logFechaDesde) : null,
      hasta: logFechaHasta ? finDiaLocal(logFechaHasta) : null,
    };
  }, [logFechaDesde, logFechaHasta, rangoFechasInvalido]);

  const filtroLogsFirestore = filtroLogsActualizacion ?? { desde: null, hasta: null };

  const { logs, loading: loadingLogs, error: errorLogs } = useLogsActualizacion(filtroLogsFirestore);

  useEffect(() => {
    setFeedbackBorrarLogs(null);
  }, [logFechaDesde, logFechaHasta]);

  async function handleBorrarLogs() {
    const hayFiltroFecha = Boolean(logFechaDesde || logFechaHasta) && !rangoFechasInvalido;
    const aclaracion = hayFiltroFecha
      ? `Solo se borrarán los registros cuyo timestamp cae en el rango de fechas (hora local) que elegiste.`
      : `Se borrarán todos los registros de la colección que tengan campo timestamp (los que ves en la tabla).`;
    if (
      !window.confirm(
        `¿Borrar esos logs en Firebase?\n\n${aclaracion}\n\nEsta acción no se puede deshacer.`
      )
    ) {
      return;
    }
    setFeedbackBorrarLogs(null);
    setBorrandoLogs(true);
    const res = await deleteLogsActualizacionCoinciden(filtroLogsFirestore);
    setBorrandoLogs(false);
    if (res.ok) {
      setFeedbackBorrarLogs({
        ok: true,
        text: `Se borraron ${res.deleted} registro${res.deleted !== 1 ? 's' : ''}.`,
      });
    } else {
      setFeedbackBorrarLogs({ ok: false, text: res.message });
    }
  }

  async function handleActualizarDatosTodas() {
    const n = computadoras.length;
    if (
      !window.confirm(
        `¿Enviar ACTUALIZAR_DATOS a las ${n} máquina${n !== 1 ? 's' : ''} listadas?\n\n` +
          'Cada agente hará una sincronización completa cuando lea el comando en Firestore.'
      )
    ) {
      return;
    }
    setErrorActualizarTodas(null);
    setEnviandoActualizarTodas(true);
    const res = await enviarComandoAMaquinas(
      computadoras.map((c) => c.id),
      'ACTUALIZAR_DATOS'
    );
    setEnviandoActualizarTodas(false);
    if (!res.ok) {
      setErrorActualizarTodas(res.message);
    }
  }

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
          <>
            <div className="actions" style={{ marginBottom: '1rem' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={enviandoActualizarTodas}
                onClick={() => void handleActualizarDatosTodas()}
              >
                {enviandoActualizarTodas
                  ? 'Enviando a todas…'
                  : `Actualizar datos en todas (${computadoras.length})`}
              </button>
            </div>
            {errorActualizarTodas && (
              <p className="error small" style={{ marginBottom: '0.75rem' }}>
                {errorActualizarTodas}
              </p>
            )}
            <div className="comandos-hw-list">
              {computadoras.map((c) => (
                <ComandosMaquina key={c.id} computadoraId={c.id} hostname={c.hostname ?? c.id} />
              ))}
            </div>
          </>
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
          Eventos en tiempo real desde <code>logs_actualizaciones</code>. Se listan todos los documentos
          de la colección (sin tope). Podés acotar por día usando las fechas (hora local).
        </p>
        <div className="filter-bar">
          <div className="filter-field">
            <label className="filter-label" htmlFor="logs-fecha-desde">
              Desde
            </label>
            <input
              id="logs-fecha-desde"
              type="date"
              className="filter-input"
              value={logFechaDesde}
              onChange={(e) => setLogFechaDesde(e.target.value)}
            />
          </div>
          <div className="filter-field">
            <label className="filter-label" htmlFor="logs-fecha-hasta">
              Hasta
            </label>
            <input
              id="logs-fecha-hasta"
              type="date"
              className="filter-input"
              value={logFechaHasta}
              onChange={(e) => setLogFechaHasta(e.target.value)}
            />
          </div>
          <div className="filter-field">
            <span className="filter-label" aria-hidden="true">
              &nbsp;
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={!logFechaDesde && !logFechaHasta}
              onClick={() => {
                setLogFechaDesde('');
                setLogFechaHasta('');
              }}
            >
              Quitar filtro de fechas
            </button>
          </div>
          <div className="filter-field">
            <span className="filter-label" aria-hidden="true">
              &nbsp;
            </span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              disabled={loadingLogs || borrandoLogs || !!errorLogs || logs.length === 0}
              onClick={() => void handleBorrarLogs()}
            >
              {borrandoLogs ? 'Borrando…' : 'Borrar logs'}
            </button>
          </div>
        </div>
        {feedbackBorrarLogs && (
          <p className={feedbackBorrarLogs.ok ? 'muted small' : 'error small'} style={{ marginBottom: '0.75rem' }}>
            {feedbackBorrarLogs.text}
          </p>
        )}
        {rangoFechasInvalido && (
          <p className="error small" style={{ marginBottom: '0.75rem' }}>
            La fecha &quot;Desde&quot; no puede ser posterior a &quot;Hasta&quot;. Se muestran todos los
            logs hasta corregir el rango.
          </p>
        )}
        {errorLogs && <p className="error small">Logs: {errorLogs}</p>}
        {!loadingLogs && !errorLogs && (
          <p className="muted small" style={{ marginBottom: '0.75rem' }}>
            {logs.length} registro{logs.length !== 1 ? 's' : ''}
            {logFechaDesde || logFechaHasta
              ? rangoFechasInvalido
                ? ' (sin filtro por rango inválido)'
                : ' (filtrado en Firestore por timestamp)'
              : ''}
          </p>
        )}
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
