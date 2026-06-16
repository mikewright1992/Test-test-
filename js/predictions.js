import { firebaseConfig, isFirebaseConfigured } from "./config.js";

const LOCAL_KEY = "wc_predictions_local_v1";
let mode = "local";
let db = null;
let collectionRef = null;
let firestoreFns = null;
const localListeners = new Set();

function readLocal() {
  try {
    return JSON.parse(localStorage.getItem(LOCAL_KEY) || "[]");
  } catch {
    return [];
  }
}

function writeLocal(list) {
  localStorage.setItem(LOCAL_KEY, JSON.stringify(list));
}

export async function initPredictions() {
  if (!isFirebaseConfigured) {
    mode = "local";
    return mode;
  }
  try {
    const [{ initializeApp }, firestore] = await Promise.all([
      import("https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js"),
      import("https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js"),
    ]);
    const app = initializeApp(firebaseConfig);
    db = firestore.getFirestore(app);
    collectionRef = firestore.collection(db, "predictions");
    firestoreFns = firestore;
    mode = "firebase";
  } catch (err) {
    console.warn("Firebase init failed, falling back to local-only picks.", err);
    mode = "local";
  }
  return mode;
}

export function getMode() {
  return mode;
}

function docKey(name, matchId) {
  return `${name.trim().toLowerCase()}__${matchId}`;
}

export async function submitPrediction({ name, matchId, homeScore, awayScore }) {
  const entry = {
    name: name.trim(),
    matchId,
    homeScore: Number(homeScore),
    awayScore: Number(awayScore),
    updatedAt: Date.now(),
  };

  if (mode === "firebase") {
    const ref = firestoreFns.doc(collectionRef, docKey(entry.name, matchId));
    await firestoreFns.setDoc(ref, entry);
    return;
  }

  const list = readLocal().filter((p) => docKey(p.name, p.matchId) !== docKey(entry.name, matchId));
  list.push(entry);
  writeLocal(list);
  localListeners.forEach((listener) => listener(list));
}

export function subscribePredictions(callback) {
  if (mode === "firebase") {
    return firestoreFns.onSnapshot(collectionRef, (snap) => {
      callback(snap.docs.map((d) => d.data()));
    });
  }
  callback(readLocal());
  localListeners.add(callback);
  return () => localListeners.delete(callback);
}

export function getMyPrediction(predictions, name, matchId) {
  return predictions.find((p) => docKey(p.name, p.matchId) === docKey(name, matchId));
}
