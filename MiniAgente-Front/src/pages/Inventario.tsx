import { useMemo, useState } from 'react';
import { useComputadorasHW } from '../hooks/useComputadorasHW';
import { formatRelative } from '../lib/format';
import type { HWComputadora } from '../types/firestore';

// ── Tipos de periférico ───────────────────────────────────────────
type TipoPeriferico =
  | 'Todos'
  | 'Monitor'
  | 'Teclado'
  | 'Mouse'
  | 'Almacenamiento USB'
  | 'Impresora'
  | 'Audio'
  | 'Otro USB';

interface PerifericoRow {
  hostname: string;
  pcId: string;
  tipo: TipoPeriferico;
  nombre: string;
  detalles: string;
  lastSync: string;
}

const TIPO_KEYWORDS: Record<Exclude<TipoPeriferico, 'Todos' | 'Otro USB'>, string[]> = {
  Monitor: ['monitor', 'display', 'pantalla'],
  Teclado: ['teclado', 'keyboard', 'hid keyboard'],
  Mouse: ['mouse', 'ratón', 'raton', 'pointing'],
  'Almacenamiento USB': ['almacenamiento', 'storage', 'mass storage', 'disk', 'usb drive', 'flash'],
  Impresora: ['impresora', 'printer'],
  Audio: ['audio', 'sonido', 'speaker', 'headset', 'auricular', 'parlante'],
};

function categorizarUSB(categoria?: string, clase?: string, nombre?: string): TipoPeriferico {
  const hay = [categoria, clase, nombre]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  for (const [tipo, keywords] of Object.entries(TIPO_KEYWORDS)) {
    if (keywords.some((k) => hay.includes(k))) {
      return tipo as TipoPeriferico;
    }
  }
  return 'Otro USB';
}

function extraerPerifericos(pc: HWComputadora): PerifericoRow[] {
  const rows: PerifericoRow[] = [];
  const p = pc.perifericos;
  if (!p) return rows;

  const hostname = pc.hostname ?? pc.id;
  const lastSync = formatRelative(pc.ultima_sincronizacion ?? pc.ultima_sync ?? null);

  // Monitores
  for (const m of p.monitores ?? []) {
    rows.push({
      hostname,
      pcId: pc.id,
      tipo: 'Monitor',
      nombre: m.nombre ?? '—',
      detalles: [m.resolucion, m.tamano_pulgadas ? `${m.tamano_pulgadas}"` : undefined]
        .filter(Boolean)
        .join(' · ') || '—',
      lastSync,
    });
  }

  // Dispositivos USB
  for (const u of p.dispositivos_usb ?? []) {
    const tipo = categorizarUSB(u.categoria, u.clase, u.nombre);
    rows.push({
      hostname,
      pcId: pc.id,
      tipo,
      nombre: u.nombre ?? '—',
      detalles: [u.fabricante, u.categoria]
        .filter(Boolean)
        .join(' · ') || '—',
      lastSync,
    });
  }

  // Impresoras
  for (const i of p.impresoras ?? []) {
    rows.push({
      hostname,
      pcId: pc.id,
      tipo: 'Impresora',
      nombre: i.nombre ?? '—',
      detalles: [i.tipo, i.estado].filter(Boolean).join(' · ') || '—',
      lastSync,
    });
  }

  // Audio
  for (const a of p.audio?.salida ?? []) {
    rows.push({
      hostname,
      pcId: pc.id,
      tipo: 'Audio',
      nombre: a.nombre ?? '—',
      detalles: 'Salida de audio',
      lastSync,
    });
  }

  return rows;
}

const TIPO_ICON: Record<TipoPeriferico, string> = {
  Todos: '🗂',
  Monitor: '🖥',
  Teclado: '⌨️',
  Mouse: '🖱',
  'Almacenamiento USB': '💾',
  Impresora: '🖨',
  Audio: '🔊',
  'Otro USB': '🔌',
};

const TIPOS: TipoPeriferico[] = [
  'Todos',
  'Monitor',
  'Teclado',
  'Mouse',
  'Almacenamiento USB',
  'Impresora',
  'Audio',
  'Otro USB',
];

export function Inventario() {
  const { computadoras, loading, error } = useComputadorasHW();
  const [tipoFiltro, setTipoFiltro] = useState<TipoPeriferico>('Todos');
  const [busqueda, setBusqueda] = useState('');

  const todasLasFilas = useMemo(
    () => computadoras.flatMap(extraerPerifericos),
    [computadoras]
  );

  const conteosPorTipo = useMemo(() => {
    const map: Partial<Record<TipoPeriferico, number>> = {};
    for (const row of todasLasFilas) {
      map[row.tipo] = (map[row.tipo] ?? 0) + 1;
    }
    return map;
  }, [todasLasFilas]);

  const filasFiltradas = useMemo(() => {
    let rows = todasLasFilas;

    if (tipoFiltro !== 'Todos') {
      rows = rows.filter((r) => r.tipo === tipoFiltro);
    }

    if (busqueda.trim()) {
      const q = busqueda.trim().toLowerCase();
      rows = rows.filter(
        (r) =>
          r.hostname.toLowerCase().includes(q) ||
          r.nombre.toLowerCase().includes(q) ||
          r.detalles.toLowerCase().includes(q)
      );
    }

    return rows;
  }, [todasLasFilas, tipoFiltro, busqueda]);

  if (error) {
    return (
      <div className="page">
        <h1>Inventario</h1>
        <p className="error">{error}</p>
      </div>
    );
  }

  return (
    <div className="page">
      <h1>Inventario de periféricos</h1>
      <p className="muted">
        {loading
          ? 'Cargando...'
          : `${todasLasFilas.length} periférico${todasLasFilas.length !== 1 ? 's' : ''} en ${computadoras.length} equipo${computadoras.length !== 1 ? 's' : ''}`}
      </p>

      {/* Chips de tipo */}
      <div className="inv-type-counts">
        {TIPOS.map((tipo) => {
          const count = tipo === 'Todos' ? todasLasFilas.length : (conteosPorTipo[tipo] ?? 0);
          if (tipo !== 'Todos' && count === 0) return null;
          return (
            <button
              key={tipo}
              className={`inv-type-chip${tipoFiltro === tipo ? ' active' : ''}`}
              onClick={() => setTipoFiltro(tipo)}
            >
              {TIPO_ICON[tipo]} {tipo}
              <span className="inv-type-chip-count">{count}</span>
            </button>
          );
        })}
      </div>

      {/* Barra de búsqueda */}
      <div className="filter-bar">
        <div className="filter-field filter-field--grow">
          <label className="filter-label" htmlFor="inv-busqueda">
            Buscar
          </label>
          <input
            id="inv-busqueda"
            type="text"
            className="filter-input"
            placeholder="Hostname, nombre, fabricante..."
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
        </div>
        <div className="filter-field">
          <label className="filter-label" htmlFor="inv-tipo">
            Tipo
          </label>
          <select
            id="inv-tipo"
            className="filter-select"
            value={tipoFiltro}
            onChange={(e) => setTipoFiltro(e.target.value as TipoPeriferico)}
          >
            {TIPOS.map((t) => (
              <option key={t} value={t}>
                {TIPO_ICON[t]} {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Tabla */}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Equipo</th>
              <th>Tipo</th>
              <th>Nombre / Modelo</th>
              <th>Detalles</th>
              <th>Última sync</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="table-empty">
                  Cargando periféricos...
                </td>
              </tr>
            ) : filasFiltradas.length === 0 ? (
              <tr>
                <td colSpan={5} className="table-empty">
                  No se encontraron periféricos.
                </td>
              </tr>
            ) : (
              filasFiltradas.map((row, i) => (
                <tr key={`${row.pcId}-${row.tipo}-${i}`}>
                  <td>
                    <strong style={{ color: 'var(--color-primary)' }}>
                      {row.hostname}
                    </strong>
                  </td>
                  <td>
                    <span className="badge badge-info">
                      {TIPO_ICON[row.tipo]} {row.tipo}
                    </span>
                  </td>
                  <td>{row.nombre}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    {row.detalles}
                  </td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.82rem', whiteSpace: 'nowrap' }}>
                    {row.lastSync}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
