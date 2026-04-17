import { useEffect, useState } from 'react';
import {
  collection,
  getDocs,
  limit,
  onSnapshot,
  orderBy,
  query,
  where,
  Timestamp,
  writeBatch,
  type QueryConstraint,
} from 'firebase/firestore';
import { initFirebase, isFirebaseConfigured, COLLECTIONS } from '../lib/firebase';
import type { LogActualizacion } from '../types/firestore';

function docToLog(id: string, data: Record<string, unknown>): LogActualizacion {
  return {
    id,
    timestamp: (data.timestamp as LogActualizacion['timestamp']) ?? null,
    evento: (data.evento as string) ?? '',
    detalle: (data.detalle as string) ?? '',
    uuid: (data.uuid as string) ?? '',
    hostname: (data.hostname as string) ?? '',
    version_agente: (data.version_agente as string) ?? '',
  };
}

export type FiltroFechasLogs = {
  /** Inicio del día local (inclusive) */
  desde: Date | null;
  /** Fin del día local (inclusive) */
  hasta: Date | null;
};

function constraintsRangoTimestamp(desdeMs: number | null, hastaMs: number | null): QueryConstraint[] {
  const constraints: QueryConstraint[] = [];
  if (desdeMs != null) {
    constraints.push(where('timestamp', '>=', Timestamp.fromDate(new Date(desdeMs))));
  }
  if (hastaMs != null) {
    constraints.push(where('timestamp', '<=', Timestamp.fromDate(new Date(hastaMs))));
  }
  return constraints;
}

const BORRADO_LOTE = 500;

/**
 * Borra en Firebase los documentos de `logs_actualizaciones` que coinciden con el mismo criterio
 * que la lista (orden por `timestamp`; respeta `desde`/`hasta` si vienen informados).
 * Documentos sin `timestamp` no entran en esta consulta y no se borran.
 */
export async function deleteLogsActualizacionCoinciden(
  filtroFechas: FiltroFechasLogs
): Promise<{ ok: true; deleted: number } | { ok: false; message: string }> {
  if (!isFirebaseConfigured()) {
    return { ok: false, message: 'Firebase no está configurado (.env).' };
  }
  const firestore = initFirebase();
  if (!firestore) {
    return { ok: false, message: 'No se pudo obtener Firestore.' };
  }

  const desdeMs = filtroFechas.desde?.getTime() ?? null;
  const hastaMs = filtroFechas.hasta?.getTime() ?? null;
  const col = collection(firestore, COLLECTIONS.LOGS_ACTUALIZACIONES);

  let deleted = 0;
  try {
    while (true) {
      const q = query(
        col,
        ...constraintsRangoTimestamp(desdeMs, hastaMs),
        orderBy('timestamp', 'desc'),
        limit(BORRADO_LOTE)
      );
      const snap = await getDocs(q);
      if (snap.empty) break;

      const batch = writeBatch(firestore);
      for (const d of snap.docs) {
        batch.delete(d.ref);
      }
      await batch.commit();
      deleted += snap.docs.length;
    }
    return { ok: true, deleted };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return { ok: false, message: msg };
  }
}

/**
 * Suscripción en tiempo real a `logs_actualizaciones` (sin límite de documentos).
 * Opcionalmente filtra por `timestamp` en Firestore (rango inclusive).
 */
export function useLogsActualizacion(filtroFechas?: FiltroFechasLogs | null) {
  const [logs, setLogs] = useState<LogActualizacion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const desdeMs = filtroFechas?.desde?.getTime() ?? null;
  const hastaMs = filtroFechas?.hasta?.getTime() ?? null;

  useEffect(() => {
    if (!isFirebaseConfigured()) {
      setError('Configura las variables VITE_FIREBASE_* en .env (copia .env.example).');
      setLoading(false);
      return;
    }
    const firestore = initFirebase();
    if (!firestore) {
      setError('No se pudo conectar a Firebase. Revisa la consola.');
      setLoading(false);
      return;
    }

    const col = collection(firestore, COLLECTIONS.LOGS_ACTUALIZACIONES);
    const constraints: QueryConstraint[] = [
      ...constraintsRangoTimestamp(desdeMs, hastaMs),
      orderBy('timestamp', 'desc'),
    ];
    const q = query(col, ...constraints);

    const unsub = onSnapshot(
      q,
      (snap) => {
        const list = snap.docs.map((d) => docToLog(d.id, d.data() as Record<string, unknown>));
        setLogs(list);
        setLoading(false);
        setError(null);
      },
      (err) => {
        setError(err.message);
        setLoading(false);
      }
    );

    return () => unsub();
  }, [desdeMs, hastaMs]);

  return { logs, loading, error };
}
