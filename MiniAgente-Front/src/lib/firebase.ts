import { initializeApp, type FirebaseApp } from 'firebase/app';
import { getFirestore, type Firestore } from 'firebase/firestore';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

let app: FirebaseApp | null = null;
let db: Firestore | null = null;

export function isFirebaseConfigured(): boolean {
  return !!(
    firebaseConfig.projectId &&
    firebaseConfig.apiKey &&
    typeof firebaseConfig.projectId === 'string'
  );
}

export function initFirebase(): Firestore | null {
  if (db) return db;
  if (!isFirebaseConfigured()) return null;
  try {
    app = initializeApp(firebaseConfig);
    db = getFirestore(app);
    return db;
  } catch (e) {
    console.error('Firebase init error:', e);
    return null;
  }
}

export function getDb(): Firestore | null {
  if (!db) return initFirebase();
  return db;
}

export const COLLECTIONS = {
  HW_COMPUTADORAS: 'computadoras',
  HW_TAREAS: 'tareas',
  LOGS_ACTUALIZACIONES: 'logs_actualizaciones',
} as const;
