import { useState } from 'react';
import { doc, setDoc, writeBatch } from 'firebase/firestore';
import { initFirebase, isFirebaseConfigured, COLLECTIONS } from '../lib/firebase';

export type ComandoHW = 'ACTUALIZAR_DATOS' | 'ACTUALIZAR_AGENTE';

const ESCRITURA_LOTE = 500;

/** Escribe el mismo comando en `tareas/{id}` para cada UUID (merge), en lotes de 500. */
export async function enviarComandoAMaquinas(
  computadoraIds: string[],
  comando: ComandoHW
): Promise<{ ok: true } | { ok: false; message: string }> {
  if (computadoraIds.length === 0) {
    return { ok: true };
  }
  if (!isFirebaseConfigured()) {
    return { ok: false, message: 'Firebase no está configurado (.env).' };
  }
  const firestore = initFirebase();
  if (!firestore) {
    return { ok: false, message: 'No se pudo obtener Firestore.' };
  }
  try {
    for (let i = 0; i < computadoraIds.length; i += ESCRITURA_LOTE) {
      const chunk = computadoraIds.slice(i, i + ESCRITURA_LOTE);
      const batch = writeBatch(firestore);
      for (const id of chunk) {
        const ref = doc(firestore, COLLECTIONS.HW_TAREAS, id);
        batch.set(ref, { comando }, { merge: true });
      }
      await batch.commit();
    }
    return { ok: true };
  } catch (e) {
    const msg = e instanceof Error ? e.message : 'Error al enviar comando';
    return { ok: false, message: msg };
  }
}

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
