import type { FirestoreTimestamp } from '../types/firestore';

export function formatTimestamp(ts: FirestoreTimestamp | undefined | null): string {
  if (!ts || typeof ts.seconds !== 'number') return '—';
  const d = new Date(ts.seconds * 1000);
  return d.toLocaleString(undefined, {
    dateStyle: 'short',
    timeStyle: 'medium',
  });
}

export function formatRelative(ts: FirestoreTimestamp | undefined | null): string {
  if (!ts || typeof ts.seconds !== 'number') return '—';
  const sec = Math.floor(Date.now() / 1000 - ts.seconds);
  if (sec < 60) return 'hace un momento';
  if (sec < 3600) return `hace ${Math.floor(sec / 60)} min`;
  if (sec < 86400) return `hace ${Math.floor(sec / 3600)} h`;
  if (sec < 604800) return `hace ${Math.floor(sec / 86400)} días`;
  return formatTimestamp(ts);
}
