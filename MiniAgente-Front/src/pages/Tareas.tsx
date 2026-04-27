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
import type { HWComputadora, HWTarea } from '../types/firestore';

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

function versionInstaladaTexto(c: HWComputadora): string {
  const v = c.version_agente ?? c.version;
  if (v == null || String(v).trim() === '') return '—';
  return String(v);
}

function ComandosMaquina({
  computadoraId,
  hostname,
  versionLabel,
  seleccionada,
  onToggleSeleccion,
}: {
  computadoraId: string;
  hostname: string;
  versionLabel: string;
  seleccionada: boolean;
  onToggleSeleccion: () => void;
}) {
  const { enviarActualizarDatos, enviarActualizarAgente, sending, error } = useComandoHW(computadoraId);
  const [enviandoReset, setEnviandoReset] = useState(false);
  const [errorReset, setErrorReset] = useState<string | null>(null);

  async function handleReset() {
    if (!window.confirm(`¿Enviar RESETEAR_ID a ${hostname || computadoraId}?\n\nEl agente borrará su ID del registro de Windows y se reiniciará con un ID limpio generado desde el hardware.`)) return;
    setEnviandoReset(true);
    setErrorReset(null);
    const res = await enviarComandoAMaquinas([computadoraId], 'RESETEAR_ID');
    setEnviandoReset(false);
    if (!res.ok) setErrorReset(res.message);
  }

  return (
    <div
      className="comandos-hw"
      role="presentation"
      onClick={onToggleSeleccion}
      style={{ cursor: 'pointer' }}
      title="Clic en la fila para marcar o desmarcar en actualización masiva del agente"
    >
      <label
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.35rem',
          cursor: 'pointer',
          flexShrink: 0,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <input
          type="checkbox"
          checked={seleccionada}
          onChange={onToggleSeleccion}
          aria-label={`Incluir ${hostname || computadoraId} en actualización masiva del agente`}
        />
      </label>
      <div style={{ flex: '1 1 12rem', minWidth: 0 }}>
        <div className="comandos-hw-host">{hostname || computadoraId}</div>
        <div className="muted small" style={{ marginTop: '0.15rem' }}>
          Versión instalada: <strong>{versionLabel}</strong>
        </div>
      </div>
      <div className="actions" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          disabled={sending || enviandoReset}
          onClick={() => enviarActualizarDatos()}
        >
          Actualizar datos
        </button>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={sending || enviandoReset}
          onClick={() => enviarActualizarAgente()}
        >
          Actualizar agente
        </button>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          style={{ color: '#dc3545', borderColor: '#dc3545' }}
          disabled={sending || enviandoReset}
          onClick={() => void handleReset()}
        >
          {enviandoReset ? 'Enviando...' : 'Resetear ID'}
        </button>
      </div>
      {(error || errorReset) && (
        <p
          className="error small"
          style={{ flexBasis: '100%', marginBottom: 0 }}
          onClick={(e) => e.stopPropagation()}
        >
          {error || errorReset}
        </p>
      )}
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
  const [idsAgenteSeleccion, setIdsAgenteSeleccion] = useState<Set<string>>(() => new Set());
  const [enviandoAgenteSeleccion, setEnviandoAgenteSeleccion] = useState(false);
  const [errorAgenteSeleccion, setErrorAgenteSeleccion] = useState<string | null>(null);
  const [enviandoResetSeleccion, setEnviandoResetSeleccion] = useState(false);

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

  const idsComputadorasValidos = useMemo(
    () => new Set(computadoras.map((c) => c.id)),
    [computadoras]
  );

  useEffect(() => {
    setIdsAgenteSeleccion((prev) => {
      const next = new Set<string>();
      for (const id of prev) {
        if (idsComputadorasValidos.has(id)) next.add(id);
      }
      if (next.size === prev.size) return prev;
      return next;
    });
  }, [idsComputadorasValidos]);

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

  function toggleSeleccionAgente(id: string) {
    setIdsAgenteSeleccion((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function seleccionarTodasAgente() {
    setIdsAgenteSeleccion(new Set(computadoras.map((c) => c.id)));
  }

  function deseleccionarTodasAgente() {
    setIdsAgenteSeleccion(new Set());
  }

  async function handleActualizarAgenteSeleccionadas() {
    const ids = [...idsAgenteSeleccion];
    const n = ids.length;
    if (n === 0) return;
    if (
      !window.confirm(
        `¿Enviar ACTUALIZAR_AGENTE a ${n} máquina${n !== 1 ? 's' : ''} seleccionada${n !== 1 ? 's' : ''}?\n\n` +
          'Cada una descargará el .exe desde la URL configurada en Firebase y reiniciará el servicio. ' +
          'Asegurate de tener la URL y el binario correctos antes de continuar.'
      )
    ) {
      return;
    }
    setErrorAgenteSeleccion(null);
    setEnviandoAgenteSeleccion(true);
    const res = await enviarComandoAMaquinas(ids, 'ACTUALIZAR_AGENTE');
    setEnviandoAgenteSeleccion(false);
    if (!res.ok) {
      setErrorAgenteSeleccion(res.message);
    }
  }

  async function handleResetearIdSeleccionadas() {
    const ids = [...idsAgenteSeleccion];
    const n = ids.length;
    if (n === 0) return;
    if (
      !window.confirm(
        `¿Enviar RESETEAR_ID a ${n} máquina${n !== 1 ? 's' : ''} seleccionada${n !== 1 ? 's' : ''}?\n\n` +
          'Los agentes borrarán su ID del registro de Windows y se reiniciarán para generar uno nuevo. Usar solo en caso de colisiones o IDs atascados.'
      )
    ) {
      return;
    }
    setErrorAgenteSeleccion(null);
    setEnviandoResetSeleccion(true);
    const res = await enviarComandoAMaquinas(ids, 'RESETEAR_ID');
    setEnviandoResetSeleccion(false);
    if (!res.ok) {
      setErrorAgenteSeleccion(res.message);
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
          Cada fila muestra la <strong>versión instalada</strong> que reporta la PC en Firestore (
          <code>version_agente</code> o, si no hay, <code>version</code>). Marcá equipos con la casilla y
          usá <strong>Actualizar agente en seleccionadas</strong> para mandar{' '}
          <code>ACTUALIZAR_AGENTE</code> solo a ellos. También podés usar los botones por máquina.
        </p>
        {loadingPcs ? (
          <p className="muted">Cargando computadoras…</p>
        ) : computadoras.length === 0 ? (
          <p className="muted">No hay computadoras en la BD.</p>
        ) : (
          <>
            <div className="actions" style={{ marginBottom: '1rem', flexWrap: 'wrap' }}>
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
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={computadoras.length === 0}
                onClick={seleccionarTodasAgente}
              >
                Seleccionar todas (agente)
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                disabled={idsAgenteSeleccion.size === 0}
                onClick={deseleccionarTodasAgente}
              >
                Deseleccionar
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={idsAgenteSeleccion.size === 0 || enviandoAgenteSeleccion}
                onClick={() => void handleActualizarAgenteSeleccionadas()}
              >
                {enviandoAgenteSeleccion
                  ? 'Enviando ACTUALIZAR_AGENTE…'
                  : `Actualizar agente en seleccionadas (${idsAgenteSeleccion.size})`}
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ color: '#dc3545', borderColor: '#dc3545' }}
                disabled={idsAgenteSeleccion.size === 0 || enviandoResetSeleccion}
                onClick={() => void handleResetearIdSeleccionadas()}
              >
                {enviandoResetSeleccion
                  ? 'Enviando RESETEAR_ID…'
                  : `Resetear ID en seleccionadas (${idsAgenteSeleccion.size})`}
              </button>
            </div>
            {errorActualizarTodas && (
              <p className="error small" style={{ marginBottom: '0.75rem' }}>
                {errorActualizarTodas}
              </p>
            )}
            {errorAgenteSeleccion && (
              <p className="error small" style={{ marginBottom: '0.75rem' }}>
                {errorAgenteSeleccion}
              </p>
            )}
            <div className="comandos-hw-list">
              {computadoras.map((c) => (
                <ComandosMaquina
                  key={c.id}
                  computadoraId={c.id}
                  hostname={c.hostname ?? c.id}
                  versionLabel={versionInstaladaTexto(c)}
                  seleccionada={idsAgenteSeleccion.has(c.id)}
                  onToggleSeleccion={() => toggleSeleccionAgente(c.id)}
                />
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
