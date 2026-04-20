import { useEffect, useState } from 'react';
import { collection, onSnapshot } from 'firebase/firestore';
import { initFirebase, isFirebaseConfigured, COLLECTIONS } from '../lib/firebase';
import type { HWComputadora } from '../types/firestore';

function docToComputadora(id: string, data: Record<string, unknown>): HWComputadora {
  return {
    id,
    hostname: (data.hostname as string) ?? null,
    sistema_operativo: (data.sistema_operativo as string) ?? null,
    so: (data.so as string) ?? null,
    procesador: (data.procesador as string) ?? null,
    cpu_uso_porcentaje: (data.cpu_uso_porcentaje as number) ?? null,
    ram_uso_porcentaje: (data.ram_uso_porcentaje as number) ?? null,
    ram_total_gb: (data.ram_total_gb as number) ?? null,
    modulos_ram: (data.modulos_ram as HWComputadora['modulos_ram']) ?? null,
    discos: (data.discos as HWComputadora['discos']) ?? null,
    ip_publica: (data.ip_publica as string) ?? null,
    anydesk_id: (data.anydesk_id as string) ?? null,
    version_agente: (data.version_agente as string) ?? null,
    version: (data.version as string) ?? null,
    ultima_sincronizacion: data.ultima_sincronizacion as HWComputadora['ultima_sincronizacion'],
    ultima_sync: data.ultima_sync as HWComputadora['ultima_sync'],
    perifericos: (data.perifericos as HWComputadora['perifericos']) ?? null,
  };
}

export function useComputadorasHW() {
  const [computadoras, setComputadoras] = useState<HWComputadora[]>([]);
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
    const col = collection(firestore, COLLECTIONS.HW_COMPUTADORAS);

    const unsub = onSnapshot(
      col,
      (snap) => {
        const list = snap.docs.map((d) =>
          docToComputadora(d.id, d.data() as Record<string, unknown>)
        );
        setComputadoras(list);
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

  return { computadoras, loading, error };
}
