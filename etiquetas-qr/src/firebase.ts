import { initializeApp } from 'firebase/app'
import { getAuth } from 'firebase/auth'
import { getFirestore } from 'firebase/firestore'

const firebaseConfig = {
  apiKey: 'AIzaSyCPsHnnh9aCsMG1W2ML5Vz-doZzQg1I__s',
  authDomain: 'devbac-42d14.firebaseapp.com',
  projectId: 'devbac-42d14',
  storageBucket: 'devbac-42d14.firebasestorage.app',
  messagingSenderId: '317393322844',
  appId: '1:317393322844:web:6215892f4779db5447f799',
}

const app = initializeApp(firebaseConfig)

export const auth = getAuth(app)
export const db = getFirestore(app)
