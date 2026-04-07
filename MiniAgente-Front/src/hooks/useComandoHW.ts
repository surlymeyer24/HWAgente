import { useState } from 'react';
import { doc, setDoc } from 'firebase/firestore';
import { initFirebase, isFirebaseConfigured, COLLECTIONS } from '../lib/firebase';

export type ComandoHW = 'ACTUALIZAR_DATOS' | 'ACTUALIZAR_AGENTE';

export function useComandoHW(computadoraId: string | null) {
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enviar = async (comando: ComandoHW) => {
    if (!computadoraId || !isFirebaseConfigured()) return;
    const firestore = initFirebase();
    if (!firestore) return;
    setSending(true);
    setError(null);
    try {
      const ref = doc(firestore, COLLECTIONS.HW_TAREAS, computadoraId);
      await setDoc(ref, { comando }, { merge: true });
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Error al enviar comando');
    } finally {
      setSending(false);
    }
  };

  return {
    enviarActualizarDatos: () => enviar('ACTUALIZAR_DATOS'),
    enviarActualizarAgente: () => enviar('ACTUALIZAR_AGENTE'),
    sending,
    error,
  };
}
