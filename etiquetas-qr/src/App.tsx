import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  GoogleAuthProvider,
  onAuthStateChanged,
  signInWithPopup,
  signOut,
  type User,
} from 'firebase/auth'
import {
  collection,
  doc,
  getDoc,
  getDocs,
  serverTimestamp,
  writeBatch,
} from 'firebase/firestore'
import { QRCodeSVG } from 'qrcode.react'
import {
  BrowserRouter,
  Route,
  Routes,
  useParams,
} from 'react-router-dom'
import './App.css'
import { auth, db } from './firebase'

type Computadora = {
  id: string
  hostname: string
  ubicacion: string
}

type EtiquetaAdmin = {
  token: string
  machineId: string
  hostname: string
  ubicacion: string
  activa: boolean
}

type FichaPublica = {
  hostname: string
  ubicacion: string
  activa: boolean
}

function Icon({ name }: { name: 'computer' | 'pin' | 'qr' | 'refresh' }) {
  const paths = {
    computer: <><rect x="3" y="4" width="18" height="12" rx="1.5" /><path d="M8 20h8M12 16v4" /></>,
    pin: <><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
    qr: <><rect x="3" y="3" width="6" height="6" /><rect x="15" y="3" width="6" height="6" /><rect x="3" y="15" width="6" height="6" /><path d="M15 15h2v2h-2zM19 15h2v6h-2M15 19h2v2h-2" /></>,
    refresh: <><path d="M20 7v5h-5" /><path d="M4 17v-5h5M6.1 8a7 7 0 0 1 11.2-1.8L20 9M4 15l2.7 2.8A7 7 0 0 0 18 16" /></>,
  }

  return (
    <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  )
}

function FichaEstacion() {
  const { token = '' } = useParams()
  const [ficha, setFicha] = useState<FichaPublica | null>(null)
  const [estado, setEstado] = useState<'cargando' | 'lista' | 'error'>('cargando')

  useEffect(() => {
    let activa = true

    getDoc(doc(db, 'fichas_qr', token))
      .then((snapshot) => {
        if (!activa || !snapshot.exists()) {
          setEstado('error')
          return
        }
        const data = snapshot.data() as FichaPublica
        if (!data.activa) {
          setEstado('error')
          return
        }
        setFicha(data)
        setEstado('lista')
      })
      .catch(() => activa && setEstado('error'))

    return () => {
      activa = false
    }
  }, [token])

  return (
    <main className="public-shell">
      <div className="public-brand">
        <span className="brand-mark"><Icon name="qr" /></span>
        <span>Inventario Bacarsa</span>
      </div>

      {estado === 'cargando' && (
        <section className="status-card" aria-live="polite">
          <span className="loader" />
          <p>Buscando equipo…</p>
        </section>
      )}

      {estado === 'error' && (
        <section className="status-card">
          <span className="status-symbol">?</span>
          <h1>Etiqueta no disponible</h1>
          <p>El código no existe o fue desactivado.</p>
        </section>
      )}

      {estado === 'lista' && ficha && (
        <article className="station-card">
          <div className="station-tag">Estación de trabajo</div>
          <div className="station-icon"><Icon name="computer" /></div>
          <p className="field-label">Hostname</p>
          <h1>{ficha.hostname}</h1>
          <div className="location-block">
            <Icon name="pin" />
            <div>
              <span>Ubicación</span>
              <strong>{ficha.ubicacion}</strong>
            </div>
          </div>
          <p className="scan-note">Ficha de identificación para traslado interno</p>
        </article>
      )}
    </main>
  )
}

function EtiquetaImprimible({
  etiqueta,
  onClose,
}: {
  etiqueta: EtiquetaAdmin
  onClose: () => void
}) {
  const url = `${window.location.origin}/e/${etiqueta.token}`

  return (
    <div className="print-overlay" role="dialog" aria-modal="true" aria-label="Vista previa de etiqueta">
      <div className="print-actions">
        <button type="button" className="button secondary" onClick={onClose}>Cerrar</button>
        <button type="button" className="button primary" onClick={() => window.print()}>Imprimir etiqueta</button>
      </div>
      <article className="print-label">
        <div className="label-copy">
          <span className="label-kicker">Estación de trabajo</span>
          <strong>{etiqueta.hostname}</strong>
          <span className="label-location"><Icon name="pin" />{etiqueta.ubicacion}</span>
          <small>Escaneá para identificar</small>
        </div>
        <QRCodeSVG
          value={url}
          size={164}
          level="M"
          marginSize={4}
          title={`QR de ${etiqueta.hostname}`}
        />
      </article>
    </div>
  )
}

function Administrador() {
  const [usuario, setUsuario] = useState<User | null>(null)
  const [authLista, setAuthLista] = useState(false)
  const [computadoras, setComputadoras] = useState<Computadora[]>([])
  const [etiquetas, setEtiquetas] = useState<EtiquetaAdmin[]>([])
  const [busqueda, setBusqueda] = useState('')
  const [cargando, setCargando] = useState(false)
  const [mensaje, setMensaje] = useState('')
  const [imprimiendo, setImprimiendo] = useState<EtiquetaAdmin | null>(null)

  const cargarDatos = useCallback(async () => {
    if (!auth.currentUser) return
    setCargando(true)
    setMensaje('')
    try {
      const [pcsSnapshot, etiquetasSnapshot] = await Promise.all([
        getDocs(collection(db, 'computadoras')),
        getDocs(collection(db, 'etiquetas_qr_admin')),
      ])

      setComputadoras(
        pcsSnapshot.docs
          .map((item) => ({
            id: item.id,
            hostname: String(item.data().hostname || 'SIN-HOSTNAME'),
            ubicacion: String(item.data().ubicacion || 'SIN UBICACIÓN'),
          }))
          .sort((a, b) => a.hostname.localeCompare(b.hostname)),
      )
      setEtiquetas(etiquetasSnapshot.docs.map((item) => ({
        token: item.id,
        machineId: String(item.data().machineId),
        hostname: String(item.data().hostname),
        ubicacion: String(item.data().ubicacion),
        activa: Boolean(item.data().activa),
      })))
    } catch {
      setMensaje('No se pudieron cargar los equipos. Verificá tu acceso.')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => onAuthStateChanged(auth, (user) => {
    setUsuario(user)
    setAuthLista(true)
    if (user) void cargarDatos()
  }), [cargarDatos])

  const etiquetaPorPc = useMemo(
    () => new Map(etiquetas.map((item) => [item.machineId, item])),
    [etiquetas],
  )

  const filtradas = useMemo(() => {
    const termino = busqueda.trim().toLocaleLowerCase()
    if (!termino) return computadoras
    return computadoras.filter((pc) =>
      `${pc.hostname} ${pc.ubicacion}`.toLocaleLowerCase().includes(termino),
    )
  }, [busqueda, computadoras])

  async function guardarEtiqueta(pc: Computadora) {
    setMensaje('')
    const existente = etiquetaPorPc.get(pc.id)
    const token = existente?.token ?? crypto.randomUUID().replaceAll('-', '')
    const batch = writeBatch(db)

    batch.set(doc(db, 'etiquetas_qr_admin', token), {
      machineId: pc.id,
      hostname: pc.hostname,
      ubicacion: pc.ubicacion,
      activa: true,
      ...(existente ? {} : { creadaEn: serverTimestamp() }),
      actualizadaEn: serverTimestamp(),
    }, { merge: Boolean(existente) })
    batch.set(doc(db, 'fichas_qr', token), {
      hostname: pc.hostname,
      ubicacion: pc.ubicacion,
      activa: true,
      actualizadaEn: serverTimestamp(),
    })

    try {
      await batch.commit()
      const etiqueta = { token, machineId: pc.id, hostname: pc.hostname, ubicacion: pc.ubicacion, activa: true }
      setEtiquetas((actuales) => [...actuales.filter((item) => item.machineId !== pc.id), etiqueta])
      setImprimiendo(etiqueta)
    } catch {
      setMensaje('No se pudo generar la etiqueta. Revisá las reglas de Firestore.')
    }
  }

  async function ingresar() {
    setMensaje('')
    try {
      await signInWithPopup(auth, new GoogleAuthProvider())
    } catch {
      setMensaje('No se pudo iniciar sesión con Google.')
    }
  }

  if (!authLista) {
    return <main className="admin-shell"><section className="status-card"><span className="loader" /></section></main>
  }

  if (!usuario) {
    return (
      <main className="login-shell">
        <div className="login-grid" aria-hidden="true" />
        <div className="login-glow" aria-hidden="true" />
        <div className="login-layout">
          <section className="login-brand">
            <p className="login-eyebrow">Inventario Bacarsa</p>
            <h1>
              Etiquetas de
              <br />
              traslado<span className="login-dot">.</span>
            </h1>
            <p>Módulo independiente: un QR por computadora con hostname y ubicación registrada.</p>
          </section>
          <section className="login-panel">
            <h2>
              BACAR<span className="login-dot">.</span>it
            </h2>
            <div className="login-card">
              <p className="eyebrow">Acceso</p>
              <p className="login-card-copy">Ingresá con la cuenta corporativa para generar e imprimir etiquetas.</p>
              <button type="button" className="button primary wide" onClick={ingresar}>
                Ingresar con Google
              </button>
              {mensaje && <p className="message error">{mensaje}</p>}
            </div>
          </section>
        </div>
      </main>
    )
  }

  return (
    <main className="admin-shell">
      <header className="admin-header">
        <div className="admin-title">
          <span className="title-bar" aria-hidden="true" />
          <div>
            <p className="eyebrow">Inventario físico</p>
            <h1>Etiquetas de traslado</h1>
          </div>
        </div>
        <div className="header-actions">
          <button type="button" className="icon-button" onClick={() => void cargarDatos()} title="Actualizar">
            <Icon name="refresh" />
          </button>
          <button type="button" className="button secondary" onClick={() => void signOut(auth)}>Salir</button>
        </div>
      </header>

      <section className="summary-strip">
        <div><strong>{computadoras.length}</strong><span>computadoras</span></div>
        <div><strong>{etiquetas.filter((item) => item.activa).length}</strong><span>etiquetas activas</span></div>
        <label className="search">
          <span>Buscar</span>
          <input
            value={busqueda}
            onChange={(event) => setBusqueda(event.target.value)}
            placeholder="Hostname o ubicación"
          />
        </label>
      </section>

      {mensaje && <p className="message error">{mensaje}</p>}

      <section className="equipment-list" aria-busy={cargando}>
        <div className="list-heading">
          <span>Equipo</span>
          <span>Ubicación</span>
          <span>Etiqueta</span>
        </div>
        {filtradas.map((pc) => {
          const etiqueta = etiquetaPorPc.get(pc.id)
          return (
            <article className="equipment-row" key={pc.id}>
              <div className="equipment-name"><Icon name="computer" /><strong>{pc.hostname}</strong></div>
              <div className="equipment-location"><Icon name="pin" /><span>{pc.ubicacion}</span></div>
              <button
                type="button"
                className={etiqueta ? 'button secondary' : 'button primary'}
                onClick={() => etiqueta ? setImprimiendo(etiqueta) : void guardarEtiqueta(pc)}
              >
                <Icon name="qr" />
                {etiqueta ? 'Ver QR' : 'Generar QR'}
              </button>
            </article>
          )
        })}
        {!cargando && filtradas.length === 0 && <p className="empty">No hay equipos que coincidan con la búsqueda.</p>}
      </section>

      {imprimiendo && <EtiquetaImprimible etiqueta={imprimiendo} onClose={() => setImprimiendo(null)} />}
    </main>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/e/:token" element={<FichaEstacion />} />
        <Route path="*" element={<Administrador />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
