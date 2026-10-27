/* Orchestra — Echtzeit-Sync: holt alle 3s den Dirigenten-Zustand und aktualisiert die Roboter. */
const VOTE_META = {
  1: { label: "BUY",  cls: "buy",  face: "😊", eyes: "◕‿◕" },
  0: { label: "HOLD", cls: "",     face: "🤖", eyes: "•‿•" },
  "-1": { label: "SELL", cls: "sell", face: "😠", eyes: ">‿<" },
};
const AGENT_ORDER = ["momentum", "meanrev", "vola", "quant", "news"];

let state = null;

function el(id) { return document.getElementById(id); }

function drawChart(series) {
  const canvas = el("sChart");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!series || series.length < 2) return;
  // Null-Linie
  ctx.strokeStyle = "rgba(255,255,255,.15)";
  ctx.beginPath(); ctx.moveTo(0, H/2); ctx.lineTo(W, H/2); ctx.stroke();
  const max = Math.max(0.5, ...series.map(Math.abs));
  const n = series.length;
  // Bereichsfüllung
  ctx.beginPath();
  ctx.moveTo(0, H/2);
  series.forEach((s, i) => {
    const x = (i / (n - 1)) * W;
    const y = H/2 - (s / max) * (H/2 - 10);
    ctx.lineTo(x, y);
  });
  ctx.strokeStyle = "#7c5cff";
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.lineTo(W, H/2);
  ctx.fillStyle = "rgba(124,92,255,.15)";
  ctx.fill();
  // letzter Punkt
  const lx = W, ly = H/2 - (series[n-1] / max) * (H/2 - 10);
  ctx.beginPath(); ctx.arc(W-2, ly, 4, 0, Math.PI*2);
  ctx.fillStyle = series[n-1] > 0.5 ? "#22c55e" : (series[n-1] < -0.5 ? "#ef4444" : "#94a3b8");
  ctx.fill();
}

function robotCard(v) {
  const meta = VOTE_META[String(v.a)] || VOTE_META[0];
  const isVeto = v.agent === "vola" || v.agent === "news";
  return `
    <div class="robot-card ${meta.cls} ${(isVeto && v.conf > 0.8) ? "veto-card" : ""}">
      <div class="robot-head">${v.icon || "🤖"}</div>
      <div class="eyes">${meta.eyes}</div>
      <div class="robot-name">${v.label}</div>
      <div class="robot-role">${v.role}</div>
      <div class="robot-vote" style="color:${v.a === 1 ? "var(--buy)" : (v.a === -1 ? "var(--sell)" : "var(--hold)")}">${meta.label}</div>
      <div class="robot-conf">conf ${(v.conf * 100).toFixed(0)}%</div>
      <div class="robot-weight">w ${(v.weight * 100).toFixed(0)}%</div>
      <div class="robot-reason">${v.reason || ""}</div>
    </div>`;
}

function render(state) {
  if (!state || state.empty) {
    el("decision").textContent = "…";
    return;
  }
  el("symbol").textContent = state.symbol || "—";
  const dec = el("decision");
  dec.textContent = state.decision;
  dec.style.color = state.color;
  el("sval").textContent = (state.S >= 0 ? "+" : "") + (state.S).toFixed(3);
  el("strength").textContent = (state.strength).toFixed(3);
  el("conf").textContent = (state.avg_confidence * 100).toFixed(0) + "%";
  el("time").textContent = (state.timestamp || "").replace("T", " ").slice(0, 19);
  el("veto").classList.toggle("hidden", !state.vetoed);
  // Roboter
  const grid = el("agents");
  const sorted = AGENT_ORDER.map(n => state.votes.find(v => v.agent === n)).filter(Boolean);
  grid.innerHTML = sorted.map(robotCard).join("");
  drawChart(state.history);
}

async function poll() {
  try {
    const r = await fetch("/api/state", { cache: "no-store" });
    state = await r.json();
    el("conn").classList.add("on");
    el("conn").classList.remove("off");
    el("connText").textContent = "live";
    render(state);
    el("upd").textContent = "aktualisiert " + new Date().toLocaleTimeString();
  } catch (e) {
    el("conn").classList.remove("on");
    el("conn").classList.add("off");
    el("connText").textContent = "offline";
  }
}

poll();
setInterval(poll, 3000);
