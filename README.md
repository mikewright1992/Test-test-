# World Cup 2026 Dashboard

A single-page dashboard for tracking the World Cup with friends: live scores
and schedule, group standings, a knockout bracket, and a score-prediction
pool with a leaderboard. No build step — plain HTML/CSS/JS, ready for GitHub
Pages.

## What it does

- **Scores & Schedule** — fetches match data live from [TheSportsDB](https://www.thesportsdb.com/)'s
  free API, filterable by team or group.
- **Group Standings** — computed client-side from match results (no
  fabricated data — if the API hasn't published a result yet, that match
  just doesn't count toward the table).
- **Knockout Bracket** — renders whatever knockout-round matches the API
  has, grouped by round.
- **Prediction Pool** — anyone can enter their name and pick a score for any
  match that hasn't kicked off yet. Once a match finishes, picks are scored:
  **3 points** for an exact score, **1 point** for picking the correct
  winner/draw, **0** otherwise. The leaderboard tallies everyone's points.

## Important note on data

This was built without access to the actual 2026 World Cup draw or results
(that happened after the knowledge cutoff used to build this), so **no
groups, teams, or scores are hardcoded** — everything you see comes from the
live API at request time, computed fresh. If a section says "no data yet,"
that means the API doesn't have it yet, not that something is broken.

## Publish it on GitHub Pages

1. Push this branch, then merge it into `main` (or change the Pages source
   to this branch).
2. In the repo: **Settings → Pages → Build and deployment → Source**, choose
   "Deploy from a branch," pick the branch and `/ (root)` folder, save.
3. GitHub gives you a URL like `https://<username>.github.io/<repo>/` —
   that's the link to send your friends.

## Set up the shared prediction pool (optional, ~5 minutes)

By default, picks are only saved in each person's own browser (a banner on
the Pool tab tells you this). To make picks and the leaderboard shared across
everyone, connect a free Firebase project:

1. Go to [console.firebase.google.com](https://console.firebase.google.com/) → **Add project** (free Spark plan, no credit card needed).
2. In your new project, go to **Build → Firestore Database → Create database**. Start in **test mode** for now (or use the rules below).
3. Go to **Project settings → General → Your apps → Web app (`</>`)**, register an app, and copy the `firebaseConfig` object it gives you.
4. Paste those values into `js/config.js`, replacing the placeholders in `firebaseConfig`.
5. Commit and push — the banner on the Pool tab will disappear once it detects real config values, and picks will sync live for everyone.

Recommended Firestore rules (anyone with the link can write a pick, but only their own; no auth, since this is a casual pool — don't use this pattern for anything sensitive):

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /predictions/{docId} {
      allow read: if true;
      allow write: if request.resource.data.keys().hasAll(['name','matchId','homeScore','awayScore','updatedAt']);
    }
  }
}
```

## Run it locally

No build tools needed — just serve the folder, since browsers block `fetch`
and ES module imports from `file://` URLs:

```
python3 -m http.server 8000
# then open http://localhost:8000
```

## Limitations

- The prediction pool has no login — it trusts whatever name someone types.
  Fine for a friend group, not for anything competitive with stakes.
- TheSportsDB's free tier is community-maintained; scores may lag a few
  minutes behind live TV coverage.
- Country flags are matched by team name from a built-in list — if a team
  name doesn't match, it shows a soccer ball instead of breaking.
