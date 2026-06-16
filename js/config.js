// Shared pool storage: fill these in with your own Firebase project config
// (see README "Set up the shared prediction pool") to let predictions sync
// across everyone's browsers. Until then, the site falls back to saving
// picks only on each person's own device.
export const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_PROJECT.firebaseapp.com",
  projectId: "YOUR_PROJECT",
  storageBucket: "YOUR_PROJECT.appspot.com",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID",
};

export const isFirebaseConfigured = firebaseConfig.apiKey !== "YOUR_API_KEY";

export const SPORTSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3";
export const WORLD_CUP_SEASON = "2026";
// Used only if the dynamic league lookup (see api.js) can't find the league by name.
export const WORLD_CUP_LEAGUE_ID_FALLBACK = "4429";
