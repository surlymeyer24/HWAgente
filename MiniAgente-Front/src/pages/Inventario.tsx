import { useMemo, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useComputadorasHW } from '../hooks/useComputadorasHW';
import { formatRelative } from '../lib/format';
import type { HWComputadora, HWDisco } from '../types/firestore';

type SortBy = 'hostname-asc' | 'hostname-desc' | 'sync-desc' | 'sync-asc';

// ── Tipos de item ──────────────────────────────────────────────────
type InventarioTipo =
  | 'Todos'
  | 'CPU'
  | 'RAM'
  | 'SSD'
  | 'HDD'
  | 'Disco'
  | 'Monitor'
  | 'Teclado'
  | 'Mouse'
  | 'Almacenamiento USB'
  | 'Impresora'
  | 'Audio'
  | 'Otro USB';

interface InventarioRow {
  hostname: string;
  pcId: string;
  tipo: InventarioTipo;
  nombre: string;
  detalles: string;
  lastSync: string;
}

const TIPO_KEYWORDS: Record<
  Exclude<InventarioTipo, 'Todos' | 'Otro USB' | 'CPU' | 'RAM' | 'SSD' | 'HDD' | 'Disco'>,
  string[]
> = {
  Monitor: ['monitor', 'display', 'pantalla'],
  Teclado: ['teclado', 'keyboard', 'hid keyboard'],
  Mouse: ['mouse', 'ratón', 'raton', 'pointing'],
  'Almacenamiento USB': ['almacenamiento', 'storage', 'mass storage', 'disk', 'usb drive', 'flash'],
  Impresora: ['impresora', 'printer'],
  Audio: ['audio', 'sonido', 'speaker', 'headset', 'auricular', 'parlante'],
};

function normalizarDiscos(discos: HWComputadora['discos']): HWDisco[] {
  if (!discos) return [];
  if (typeof discos === 'string') return [];
  if (Array.isArray(discos)) return discos.filter(Boolean) as HWDisco[];
  return [discos as HWDisco];
}

function tipoFilaDesdeTipoDisco(tipoDiscoRaw: unknown): 'SSD' | 'HDD' | 'Disco' {
  const t = String(tipoDiscoRaw ?? '').trim().toUpperCase();
  if (t === 'SSD') return 'SSD';
  if (t === 'HDD') return 'HDD';
  return 'Disco';
}

function etiquetaTipoInventario(t: InventarioTipo): string {
  switch (t) {
    case 'SSD': return 'Disco SSD';
    case 'HDD': return 'Disco duro';
    case 'Disco': return 'Disco';
    default: return t;
  }
}

function etiquetaConexionPeriferico(conexion?: string): string | null {
  if (!conexion) return null;
  if (conexion === 'usb') return 'USB cableado';
  if (conexion === 'bluetooth') return 'Bluetooth';
  if (conexion === 'inalambrico_usb') return 'Inalambrico (receptor USB)';
  return conexion;
}

function categorizarUSB(categoria?: string, clase?: string, nombre?: string): InventarioTipo {
  const hay = [categoria, clase, nombre].filter(Boolean).join(' ').toLowerCase();
  for (const [tipo, keywords] of Object.entries(TIPO_KEYWORDS)) {
    if (keywords.some((k) => hay.includes(k))) return tipo as InventarioTipo;
  }
  return 'Otro USB';
}

function extraerHardware(pc: HWComputadora, lastSync: string): InventarioRow[] {
  const rows: InventarioRow[] = [];
  const hostname = pc.hostname ?? pc.id;

  const proc = (pc.procesador ?? '').trim();
  if (proc) {
    const so = [pc.sistema_operativo, pc.so].filter(Boolean).join(' · ');
    rows.push({ hostname, pcId: pc.id, tipo: 'CPU', nombre: proc, detalles: so || '—', lastSync });
  }

  const mods = pc.modulos_ram;
  if (mods && mods.length > 0) {
    for (const m of mods) {
      const nombre = [m.fabricante, m.modelo].filter(Boolean).join(' ').trim() || 'Modulo RAM';
      const detalles = [
        m.capacidad_gb != null ? `${m.capacidad_gb} GB` : null,
        m.velocidad_mhz ? `${m.velocidad_mhz} MHz` : null,
      ].filter(Boolean).join(' · ');
      rows.push({ hostname, pcId: pc.id, tipo: 'RAM', nombre, detalles: detalles || '—', lastSync });
    }
  } else if (pc.ram_total_gb != null && pc.ram_total_gb > 0) {
    rows.push({ hostname, pcId: pc.id, tipo: 'RAM', nombre: 'RAM (total)', detalles: `${pc.ram_total_gb} GB`, lastSync });
  }

  const discos = normalizarDiscos(pc.discos);
  if (discos.length > 0) {
    const groups = new Map<string, HWDisco[]>();
    for (const d of discos) {
      const idx = d.disco_fisico_index;
      const key = idx != null && String(idx).length > 0
        ? `i:${idx}`
        : `d:${d.dispositivo ?? ''}|${d.modelo_disco ?? ''}|${d.tipo_disco ?? ''}`;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(d);
    }
    for (const parts of groups.values()) {
      const first = parts[0];
      const tipoFila = tipoFilaDesdeTipoDisco(first.tipo_disco);
      const tipoDisco = (first.tipo_disco || '').toString().trim();
      const modelo = (first.modelo_disco || '—').toString();
      const vols = parts.map((p) => {
        const letra = (p.dispositivo ?? '').replace(/\\/g, '') || (p.punto_montaje ?? '').replace(/\\/g, '');
        const gb = p.total_gb != null ? `${p.total_gb} GB` : '';
        return [letra, gb].filter(Boolean).join(' ');
      });
      const detalles = [
        tipoFila === 'Disco' && tipoDisco && tipoDisco !== 'Desconocido' ? tipoDisco : null,
        vols.filter(Boolean).join(' · '),
        parts.length > 1 ? `${parts.length} volumenes` : null,
      ].filter(Boolean).join(' · ');
      rows.push({ hostname, pcId: pc.id, tipo: tipoFila, nombre: modelo !== '—' ? modelo : 'Disco sin modelo', detalles: detalles || '—', lastSync });
    }
  }
  return rows;
}

function extraerPerifericos(pc: HWComputadora, lastSync: string): InventarioRow[] {
  const rows: InventarioRow[] = [];
  const p = pc.perifericos;
  if (!p) return rows;
  const hostname = pc.hostname ?? pc.id;

  for (const m of p.monitores ?? []) {
    rows.push({
      hostname, pcId: pc.id, tipo: 'Monitor', nombre: m.nombre ?? '—',
      detalles: [m.resolucion, m.tamano_pulgadas ? `${m.tamano_pulgadas}"` : undefined].filter(Boolean).join(' · ') || '—',
      lastSync,
    });
  }
  for (const u of p.dispositivos_usb ?? []) {
    const tipo = categorizarUSB(u.categoria, u.clase, u.nombre);
    const conexionLbl = etiquetaConexionPeriferico(u.conexion);
    rows.push({
      hostname, pcId: pc.id, tipo, nombre: u.nombre ?? '—',
      detalles: [u.fabricante, u.categoria, conexionLbl].filter(Boolean).join(' · ') || '—',
      lastSync,
    });
  }
  for (const i of p.impresoras ?? []) {
    rows.push({ hostname, pcId: pc.id, tipo: 'Impresora', nombre: i.nombre ?? '—', detalles: [i.tipo, i.estado, i.ip_red ? `IP: ${i.ip_red}` : undefined].filter(Boolean).join(' · ') || '—', lastSync });
  }
  for (const a of p.audio?.salida ?? []) {
    rows.push({ hostname, pcId: pc.id, tipo: 'Audio', nombre: a.nombre ?? '—', detalles: 'Salida de audio', lastSync });
  }
  return rows;
}

function extraerFilasDePc(pc: HWComputadora): InventarioRow[] {
  const lastSync = formatRelative(pc.ultima_sincronizacion ?? pc.ultima_sync ?? null);
  return [...extraerHardware(pc, lastSync), ...extraerPerifericos(pc, lastSync)];
}

const TIPOS: InventarioTipo[] = [
  'Todos', 'CPU', 'RAM', 'SSD', 'HDD', 'Disco',
  'Monitor', 'Teclado', 'Mouse', 'Almacenamiento USB', 'Impresora', 'Audio', 'Otro USB',
];

// ── Accordion item row ─────────────────────────────────────────────
function ItemRow({ row }: { row: InventarioRow }) {
  return (
    <div className="inv-item-row">
      <span className="inv-item-tipo">{etiquetaTipoInventario(row.tipo)}</span>
      <span className="inv-item-nombre">{row.nombre}</span>
      <span className="inv-item-detalles">{row.detalles}</span>
    </div>
  );
}

// ── Accordion group ────────────────────────────────────────────────
function AccordionGroup({ hostname, pcId, rows, defaultOpen }: {
  hostname: string;
  pcId: string;
  rows: InventarioRow[];
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const lastSync = rows[0]?.lastSync ?? '—';

  return (
    <div className={`inv-accordion${open ? ' inv-accordion--open' : ''}`}>
      <button
        type="button"
        className="inv-accordion-header"
        onClick={() => setOpen(o => !o)}
      >
        <span className="inv-accordion-arrow">{open ? '\u25BC' : '\u25B6'}</span>
        <span className="inv-accordion-hostname">{hostname}</span>
        <span className="inv-accordion-meta">
          {rows.length} item{rows.length !== 1 ? 's' : ''}
        </span>
        <span className="inv-accordion-sync">{lastSync}</span>
        <Link
          to={`/computadoras/${pcId}`}
          className="inv-accordion-link"
          onClick={(e) => e.stopPropagation()}
        >
          Ver detalle
        </Link>
      </button>
      {open && (
        <div className="inv-accordion-body">
          {rows.map((row, i) => (
            <ItemRow key={`${row.tipo}-${row.nombre}-${i}`} row={row} />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Page ───────────────────────────────────────────────────────────
export function Inventario() {
  const { computadoras, loading, error } = useComputadorasHW();
  const [searchParams] = useSearchParams();
  const [tipoFiltro, setTipoFiltro] = useState<InventarioTipo>(
    (searchParams.get('tipo') as InventarioTipo) || 'Todos'
  );
  const [busqueda, setBusqueda] = useState(searchParams.get('q') || '');
  const [sortBy, setSortBy] = useState<SortBy>('hostname-asc');

  const todasLasFilas = useMemo(() => computadoras.flatMap(extraerFilasDePc), [computadoras]);

  const conteosPorTipo = useMemo(() => {
    const map: Partial<Record<InventarioTipo, number>> = {};
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
      rows = rows.filter((r) => {
        const tipoTxt = etiquetaTipoInventario(r.tipo).toLowerCase();
        return (
          r.hostname.toLowerCase().includes(q) ||
          r.nombre.toLowerCase().includes(q) ||
          r.detalles.toLowerCase().includes(q) ||
          tipoTxt.includes(q) ||
          r.tipo.toLowerCase().includes(q)
        );
      });
    }
    return rows;
  }, [todasLasFilas, tipoFiltro, busqueda]);

  const filasAgrupadas = useMemo(() => {
    const groups = new Map<string, { pcId: string; rows: InventarioRow[] }>();
    for (const row of filasFiltradas) {
      if (!groups.has(row.hostname)) groups.set(row.hostname, { pcId: row.pcId, rows: [] });
      groups.get(row.hostname)!.rows.push(row);
    }
    const entries = Array.from(groups.entries());
    entries.sort((a, b) => {
      switch (sortBy) {
        case 'hostname-asc': return a[0].localeCompare(b[0]);
        case 'hostname-desc': return b[0].localeCompare(a[0]);
        case 'sync-desc': return (b[1].rows[0]?.lastSync ?? '').localeCompare(a[1].rows[0]?.lastSync ?? '');
        case 'sync-asc': return (a[1].rows[0]?.lastSync ?? '').localeCompare(b[1].rows[0]?.lastSync ?? '');
        default: return 0;
      }
    });
    return entries;
  }, [filasFiltradas, sortBy]);

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
      <h1>Inventario</h1>
      <p className="muted">
        {loading
          ? 'Cargando...'
          : `${todasLasFilas.length} item${todasLasFilas.length !== 1 ? 's' : ''} en ${computadoras.length} equipo${computadoras.length !== 1 ? 's' : ''}`}
      </p>

      {/* Filter bar */}
      <div className="filter-bar">
        <div className="filter-field filter-field--grow">
          <label className="filter-label" htmlFor="inv-busqueda">Buscar</label>
          <input
            id="inv-busqueda"
            type="text"
            className="filter-input"
            placeholder="Hostname, modelo, fabricante..."
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
        </div>
        <div className="filter-field">
          <label className="filter-label" htmlFor="inv-tipo">Tipo</label>
          <select
            id="inv-tipo"
            className="filter-select"
            value={tipoFiltro}
            onChange={(e) => setTipoFiltro(e.target.value as InventarioTipo)}
          >
            {TIPOS.map((t) => {
              const count = t === 'Todos' ? todasLasFilas.length : (conteosPorTipo[t] ?? 0);
              if (t !== 'Todos' && count === 0) return null;
              return (
                <option key={t} value={t}>
                  {etiquetaTipoInventario(t)} ({count})
                </option>
              );
            })}
          </select>
        </div>
        <div className="filter-field">
          <label className="filter-label" htmlFor="inv-sort">Ordenar</label>
          <select
            id="inv-sort"
            className="filter-select"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortBy)}
          >
            <option value="hostname-asc">Hostname A-Z</option>
            <option value="hostname-desc">Hostname Z-A</option>
            <option value="sync-desc">Mas reciente</option>
            <option value="sync-asc">Mas antiguo</option>
          </select>
        </div>
      </div>

      {/* Accordion list */}
      {loading ? (
        <p className="muted">Cargando inventario...</p>
      ) : filasAgrupadas.length === 0 ? (
        <div className="dash-panel">
          <p className="muted" style={{ textAlign: 'center' }}>No se encontraron items.</p>
        </div>
      ) : (
        <div className="inv-accordion-list">
          {filasAgrupadas.map(([hostname, { pcId, rows }], i) => (
            <AccordionGroup
              key={hostname}
              hostname={hostname}
              pcId={pcId}
              rows={rows}
              defaultOpen={i === 0}
            />
          ))}
        </div>
      )}
    </div>
  );
}
