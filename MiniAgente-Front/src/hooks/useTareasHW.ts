import { useEffect, useState } from 'react';
import { collection, onSnapshot } from 'firebase/firestore';
import { initFirebase, isFirebaseConfigured, COLLECTIONS } from '../lib/firebase';
import type { HWTarea } from '../types/firestore';

function docToTarea(id: string, data: Record<string, unknown>): HWTarea {
  return {
    id,
    titulo: (data.titulo as string) ?? null,
    descripcion: (data.descripcion as string) ?? null,
    estado: (data.estado as string) ?? null,
    maquinaId: (data.maquinaId as string) ?? null,
    hostname: (data.hostname as string) ?? null,
    fechaHora: data.fechaHora as HWTarea['fechaHora'],
    log: (data.log as string) ?? null,
    logs: Array.isArray(data.logs) ? (data.logs as string[]) : null,
    resultado: (data.resultado as string) ?? null,
  };
}

export function useTareasHW() {
  const [tareas, setTareas] = useState<HWTarea[]>([]);
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
    const col = collection(firestore, COLLECTIONS.HW_TAREAS);

    const unsub = onSnapshot(
      col,
      (snap) => {
        const list = snap.docs.map((d) =>
          docToTarea(d.id, d.data() as Record<string, unknown>)
        );
        setTareas(list);
        setLoading(false);
        setError(null);
      },
      (err) => {
        setError(err.message);
        setLoading(false);
      }
    );

    return () => unsub();
  }, []);

  return { tareas, loading, error };
}
