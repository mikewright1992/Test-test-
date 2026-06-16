import { getMatches, computeGroupStandings, groupKnockoutRounds } from "./api.js";
import { flagFor } from "./flags.js";
import { initPredictions, getMode, submitPrediction, subscribePredictions, getMyPrediction } from "./predictions.js";

const NAME_KEY = "wc_my_name";

let allMatches = [];
let allPredictions = [];

function setStatus(el, message, isError = false) {
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.classList.toggle("hidden", !message);
}

function formatKickoff(match) {
  try {
    const d = new Date(match.kickoff);
    return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  } catch {
    return match.date || "";
  }
}

function matchStatusLabel(match) {
  if (match.finished) return { text: "Final", cls: "finished" };
  if (match.live) return { text: "Live", cls: "live" };
  return { text: "Upcoming", cls: "" };
}

function scoreText(match) {
  if (match.homeScore === null || match.awayScore === null) return "vs";
  return `${match.homeScore} – ${match.awayScore}`;
}

function renderMatchCard(match) {
  const status = matchStatusLabel(match);
  return `
    <div class="match-card">
      <div class="meta">
        <span>${match.group || match.round || "Match"}</span>
        <span class="status-pill ${status.cls}">${status.text}</span>
      </div>
      <div class="teams">
        <div class="team home"><span class="flag">${flagFor(match.home)}</span>${match.home || "TBD"}</div>
        <div class="score">${scoreText(match)}</div>
        <div class="team away">${match.away || "TBD"}<span class="flag">${flagFor(match.away)}</span></div>
      </div>
      <div class="meta"><span>${formatKickoff(match)}</span><span></span></div>
    </div>`;
}

function renderScores(filterText = "") {
  const list = document.getElementById("scores-list");
  const filtered = allMatches.filter((m) => {
    if (!filterText) return true;
    const haystack = `${m.home} ${m.away} ${m.group} ${m.round}`.toLowerCase();
    return haystack.includes(filterText.toLowerCase());
  });
  list.innerHTML = filtered.map(renderMatchCard).join("") || `<p class="status-msg">No matches found.</p>`;
}

function renderStandings() {
  const grid = document.getElementById("standings-grid");
  const groups = computeGroupStandings(allMatches);
  const groupNames = Object.keys(groups).sort();

  if (groupNames.length === 0) {
    setStatus(document.getElementById("standings-status"), "No group-stage data available yet.");
    grid.innerHTML = "";
    return;
  }
  setStatus(document.getElementById("standings-status"), "");

  grid.innerHTML = groupNames
    .map((name) => {
      const rows = groups[name]
        .map(
          (t) => `<tr>
            <td>${flagFor(t.team)} ${t.team}</td>
            <td>${t.played}</td><td>${t.won}</td><td>${t.drawn}</td><td>${t.lost}</td>
            <td>${t.gf - t.ga}</td><td>${t.points}</td>
          </tr>`
        )
        .join("");
      return `
        <div class="group-table">
          <h3>${name}</h3>
          <table>
            <thead><tr><th>Team</th><th>P</th><th>W</th><th>D</th><th>L</th><th>GD</th><th>Pts</th></tr></thead>
            <tbody>${rows}</tbody>
          </table>
        </div>`;
    })
    .join("");
}

function renderBracket() {
  const board = document.getElementById("bracket-board");
  const rounds = groupKnockoutRounds(allMatches);

  if (rounds.length === 0) {
    setStatus(document.getElementById("bracket-status"), "Knockout bracket isn't set yet — check back once the group stage wraps up.");
    board.innerHTML = "";
    return;
  }
  setStatus(document.getElementById("bracket-status"), "");

  board.innerHTML = rounds
    .map(([roundName, matches]) => {
      const cards = matches
        .map((m) => {
          const homeWin = m.finished && m.homeScore > m.awayScore;
          const awayWin = m.finished && m.awayScore > m.homeScore;
          return `
            <div class="bracket-match">
              <div class="row ${homeWin ? "winner" : ""}"><span>${flagFor(m.home)} ${m.home || "TBD"}</span><span>${m.homeScore ?? ""}</span></div>
              <div class="row ${awayWin ? "winner" : ""}"><span>${flagFor(m.away)} ${m.away || "TBD"}</span><span>${m.awayScore ?? ""}</span></div>
            </div>`;
        })
        .join("");
      return `<div class="bracket-round"><h3>${roundName}</h3>${cards}</div>`;
    })
    .join("");
}

function computeLeaderboard() {
  const matchById = new Map(allMatches.map((m) => [m.id, m]));
  const totals = new Map();

  for (const p of allPredictions) {
    const match = matchById.get(p.matchId);
    if (!match || !match.finished || match.homeScore === null) continue;

    let points = 0;
    if (p.homeScore === match.homeScore && p.awayScore === match.awayScore) {
      points = 3;
    } else {
      const predictedResult = Math.sign(p.homeScore - p.awayScore);
      const actualResult = Math.sign(match.homeScore - match.awayScore);
      if (predictedResult === actualResult) points = 1;
    }

    const key = p.name.trim();
    const current = totals.get(key) || { name: key, points: 0, picks: 0 };
    current.points += points;
    current.picks += 1;
    totals.set(key, current);
  }

  return [...totals.values()].sort((a, b) => b.points - a.points || b.picks - a.picks);
}

function renderLeaderboard() {
  const el = document.getElementById("leaderboard");
  const rows = computeLeaderboard();
  if (rows.length === 0) {
    el.innerHTML = `<div class="empty">No scored picks yet. Make some predictions below!</div>`;
    return;
  }
  el.innerHTML = `
    <table>
      <thead><tr><th>#</th><th>Name</th><th>Picks scored</th><th>Points</th></tr></thead>
      <tbody>
        ${rows.map((r, i) => `<tr><td>${i + 1}</td><td>${r.name}</td><td>${r.picks}</td><td class="points">${r.points}</td></tr>`).join("")}
      </tbody>
    </table>`;
}

function renderPredictionCard(match, myName) {
  const mine = myName ? getMyPrediction(allPredictions, myName, match.id) : null;
  const locked = match.live || match.finished || new Date(match.kickoff) <= new Date();
  const homeVal = mine ? mine.homeScore : "";
  const awayVal = mine ? mine.awayScore : "";

  let noteHtml = "";
  if (locked) {
    noteHtml = `<div class="locked-note">Picks closed${mine ? ` — you predicted ${mine.homeScore}-${mine.awayScore}` : ""}</div>`;
  } else if (mine) {
    noteHtml = `<div class="pick-note">Saved: ${mine.homeScore}-${mine.awayScore}</div>`;
  } else {
    noteHtml = `<div class="pick-note"></div>`;
  }

  return `
    <div class="match-card prediction-card" data-match-id="${match.id}">
      <div class="meta"><span>${match.group || match.round || "Match"}</span><span>${formatKickoff(match)}</span></div>
      <div class="teams">
        <div class="team home"><span class="flag">${flagFor(match.home)}</span>${match.home || "TBD"}</div>
        <div class="team away">${match.away || "TBD"}<span class="flag">${flagFor(match.away)}</span></div>
      </div>
      <div class="pick-row">
        <input type="number" min="0" max="20" class="pick-home" value="${homeVal}" ${locked ? "disabled" : ""}>
        <span>–</span>
        <input type="number" min="0" max="20" class="pick-away" value="${awayVal}" ${locked ? "disabled" : ""}>
      </div>
      ${locked ? "" : `<button class="save-btn">Save pick</button>`}
      ${noteHtml}
    </div>`;
}

function renderPredictionsList() {
  const myName = document.getElementById("player-name").value.trim();
  const list = document.getElementById("predictions-list");
  const upcomingFirst = [...allMatches].sort((a, b) => new Date(a.kickoff) - new Date(b.kickoff));
  list.innerHTML = upcomingFirst.map((m) => renderPredictionCard(m, myName)).join("");

  list.querySelectorAll(".prediction-card").forEach((card) => {
    const btn = card.querySelector(".save-btn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      const name = document.getElementById("player-name").value.trim();
      if (!name) {
        alert("Enter your name first so your picks are saved under your name.");
        return;
      }
      const home = card.querySelector(".pick-home").value;
      const away = card.querySelector(".pick-away").value;
      if (home === "" || away === "") {
        alert("Pick a score for both teams.");
        return;
      }
      btn.disabled = true;
      btn.textContent = "Saving…";
      try {
        await submitPrediction({ name, matchId: card.dataset.matchId, homeScore: home, awayScore: away });
        localStorage.setItem(NAME_KEY, name);
      } finally {
        btn.disabled = false;
        btn.textContent = "Save pick";
      }
    });
  });
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });
}

function setupPoolBanner() {
  const banner = document.getElementById("pool-mode-banner");
  if (getMode() === "local") {
    banner.textContent = "Heads up: shared pool isn't connected yet, so picks are only saved on this device. See the README to connect Firebase and share the pool with friends.";
    banner.classList.remove("hidden");
  } else {
    banner.classList.add("hidden");
  }
}

async function loadMatchesAndRender() {
  const scoresStatus = document.getElementById("scores-status");
  try {
    allMatches = await getMatches();
    setStatus(scoresStatus, allMatches.length ? "" : "No matches found yet — check back closer to kickoff.");
    renderScores(document.getElementById("scores-search").value);
    renderStandings();
    renderBracket();
    setStatus(document.getElementById("pool-status"), "");
    renderPredictionsList();
    renderLeaderboard();
  } catch (err) {
    console.error(err);
    setStatus(scoresStatus, "Couldn't load match data right now. Try refreshing in a bit.", true);
    setStatus(document.getElementById("standings-status"), "Couldn't load standings.", true);
    setStatus(document.getElementById("bracket-status"), "Couldn't load bracket.", true);
    setStatus(document.getElementById("pool-status"), "Couldn't load matches for the pool.", true);
  }
}

async function init() {
  setupTabs();

  const nameInput = document.getElementById("player-name");
  nameInput.value = localStorage.getItem(NAME_KEY) || "";
  nameInput.addEventListener("input", () => {
    renderPredictionsList();
  });

  document.getElementById("scores-search").addEventListener("input", (e) => renderScores(e.target.value));

  await initPredictions();
  setupPoolBanner();

  subscribePredictions((predictions) => {
    allPredictions = predictions;
    renderPredictionsList();
    renderLeaderboard();
  });

  await loadMatchesAndRender();
  setInterval(loadMatchesAndRender, 60 * 1000);
}

init();
