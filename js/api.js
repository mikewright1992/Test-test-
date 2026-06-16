import { SPORTSDB_BASE, WORLD_CUP_SEASON, WORLD_CUP_LEAGUE_ID_FALLBACK } from "./config.js";

const LEAGUE_ID_CACHE_KEY = "wc_league_id_v1";
const EVENTS_CACHE_KEY = "wc_events_v1";
const EVENTS_CACHE_TTL_MS = 60 * 1000;

async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Request failed: ${res.status}`);
  return res.json();
}

async function findWorldCupLeagueId() {
  const cached = localStorage.getItem(LEAGUE_ID_CACHE_KEY);
  if (cached) return cached;

  try {
    const data = await fetchJson(`${SPORTSDB_BASE}/all_leagues.php`);
    const match = (data.leagues || []).find(
      (l) => l.strSport === "Soccer" && /fifa world cup$/i.test(l.strLeague || "")
    );
    const id = match ? match.idLeague : WORLD_CUP_LEAGUE_ID_FALLBACK;
    localStorage.setItem(LEAGUE_ID_CACHE_KEY, id);
    return id;
  } catch {
    return WORLD_CUP_LEAGUE_ID_FALLBACK;
  }
}

function isFinished(event) {
  const status = (event.strStatus || "").toLowerCase();
  if (status.includes("ft") || status.includes("finished") || status.includes("match finished")) return true;
  return event.intHomeScore !== null && event.intAwayScore !== null && status !== "" && status !== "ns";
}

function isLive(event) {
  const status = (event.strStatus || "").toLowerCase();
  return status !== "" && !isFinished(event) && status !== "ns" && status !== "not started";
}

export async function getMatches({ forceRefresh = false } = {}) {
  if (!forceRefresh) {
    const cachedRaw = localStorage.getItem(EVENTS_CACHE_KEY);
    if (cachedRaw) {
      const cached = JSON.parse(cachedRaw);
      if (Date.now() - cached.savedAt < EVENTS_CACHE_TTL_MS) return cached.matches;
    }
  }

  const leagueId = await findWorldCupLeagueId();
  const data = await fetchJson(`${SPORTSDB_BASE}/eventsseason.php?id=${leagueId}&s=${WORLD_CUP_SEASON}`);
  const events = data.events || [];

  const matches = events
    .map((e) => ({
      id: e.idEvent,
      home: e.strHomeTeam,
      away: e.strAwayTeam,
      homeScore: e.intHomeScore !== null && e.intHomeScore !== undefined ? Number(e.intHomeScore) : null,
      awayScore: e.intAwayScore !== null && e.intAwayScore !== undefined ? Number(e.intAwayScore) : null,
      date: e.dateEvent,
      time: e.strTime,
      kickoff: e.strTimestamp ? `${e.strTimestamp.replace(" ", "T")}Z` : `${e.dateEvent}T${e.strTime || "00:00:00"}Z`,
      group: (e.strGroup || (/^group/i.test(e.strRound || "") ? e.strRound : "")) || "",
      round: e.strRound || "",
      finished: isFinished(e),
      live: isLive(e),
    }))
    .sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`));

  localStorage.setItem(EVENTS_CACHE_KEY, JSON.stringify({ savedAt: Date.now(), matches }));
  return matches;
}

export function computeGroupStandings(matches) {
  const groups = {};
  for (const m of matches) {
    if (!m.group || !/group/i.test(m.group)) continue;
    groups[m.group] = groups[m.group] || {};
    const g = groups[m.group];
    for (const team of [m.home, m.away]) {
      if (team && !g[team]) {
        g[team] = { team, played: 0, won: 0, drawn: 0, lost: 0, gf: 0, ga: 0, points: 0 };
      }
    }
    if (!m.finished || m.homeScore === null || m.awayScore === null) continue;

    const home = g[m.home];
    const away = g[m.away];
    if (!home || !away) continue;

    home.played++; away.played++;
    home.gf += m.homeScore; home.ga += m.awayScore;
    away.gf += m.awayScore; away.ga += m.homeScore;

    if (m.homeScore > m.awayScore) {
      home.won++; home.points += 3; away.lost++;
    } else if (m.homeScore < m.awayScore) {
      away.won++; away.points += 3; home.lost++;
    } else {
      home.drawn++; away.drawn++; home.points += 1; away.points += 1;
    }
  }

  const result = {};
  for (const [groupName, teams] of Object.entries(groups)) {
    result[groupName] = Object.values(teams).sort((a, b) => {
      if (b.points !== a.points) return b.points - a.points;
      const gdA = a.gf - a.ga, gdB = b.gf - b.ga;
      if (gdB !== gdA) return gdB - gdA;
      if (b.gf !== a.gf) return b.gf - a.gf;
      return a.team.localeCompare(b.team);
    });
  }
  return result;
}

const ROUND_ORDER = [
  "Round of 32", "Round of 16", "Quarter-final", "Quarterfinal",
  "Semi-final", "Semifinal", "3rd Place Play-off", "Final",
];

export function groupKnockoutRounds(matches) {
  const rounds = {};
  for (const m of matches) {
    if (!m.round || /group/i.test(m.round)) continue;
    rounds[m.round] = rounds[m.round] || [];
    rounds[m.round].push(m);
  }
  return Object.entries(rounds).sort((a, b) => {
    const ia = ROUND_ORDER.indexOf(a[0]);
    const ib = ROUND_ORDER.indexOf(b[0]);
    if (ia === -1 && ib === -1) return a[0].localeCompare(b[0]);
    if (ia === -1) return 1;
    if (ib === -1) return -1;
    return ia - ib;
  });
}
