import { useEffect, useState } from 'react';
import { collection, onSnapshot, orderBy, query, limit } from 'firebase/firestore';
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

export function useLogsActualizacion(maxEntradas = 100) {
  const [logs, setLogs] = useState<LogActualizacion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    const q = query(col, orderBy('timestamp', 'desc'), limit(maxEntradas));

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
  }, [maxEntradas]);

  return { logs, loading, error };
}
