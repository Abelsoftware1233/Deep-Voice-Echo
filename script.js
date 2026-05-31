/* ── TIMESTAMP ── */
function updateTimestamp() {
    const el = document.getElementById('timestamp');
    if (el) el.textContent = new Date().toISOString().replace('T',' ').slice(0,19) + ' UTC';
}
updateTimestamp();
setInterval(updateTimestamp, 1000);

document.getElementById('sessionId').textContent =
    'Session: SES-' + Math.random().toString(36).substr(2,8).toUpperCase();

/* ── RADAR CHART ── */
function drawRadar(scores) {
    const canvas = document.getElementById('radarChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const cx = 140, cy = 140, r = 108;
    const labels = ['Cognitive','LLM','Audio DF','Adversarial','Crypto','Supply'];
    const n = labels.length;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (let ring = 1; ring <= 4; ring++) {
        const rr = (ring / 4) * r;
        ctx.beginPath();
        for (let i = 0; i < n; i++) {
            const a = (Math.PI * 2 * i / n) - Math.PI / 2;
            i === 0 ? ctx.moveTo(cx + rr*Math.cos(a), cy + rr*Math.sin(a))
                    : ctx.lineTo(cx + rr*Math.cos(a), cy + rr*Math.sin(a));
        }
        ctx.closePath();
        ctx.strokeStyle = 'rgba(30,80,130,.35)'; ctx.lineWidth = 1; ctx.stroke();
    }
    for (let i = 0; i < n; i++) {
        const a = (Math.PI * 2 * i / n) - Math.PI / 2;
        ctx.beginPath(); ctx.moveTo(cx, cy);
        ctx.lineTo(cx + r*Math.cos(a), cy + r*Math.sin(a));
        ctx.strokeStyle='rgba(30,80,130,.4)'; ctx.lineWidth=1; ctx.stroke();
    }

    ctx.beginPath();
    for (let i = 0; i < n; i++) {
        const a = (Math.PI*2*i/n) - Math.PI/2;
        const dr = (scores[i]/100) * r;
        i===0 ? ctx.moveTo(cx+dr*Math.cos(a), cy+dr*Math.sin(a))
              : ctx.lineTo(cx+dr*Math.cos(a), cy+dr*Math.sin(a));
    }
    ctx.closePath();
    const grad = ctx.createRadialGradient(cx,cy,0,cx,cy,r);
    grad.addColorStop(0,'rgba(255,59,59,.3)'); grad.addColorStop(1,'rgba(255,59,59,.05)');
    ctx.fillStyle=grad; ctx.fill();
    ctx.strokeStyle='rgba(255,80,80,.8)'; ctx.lineWidth=1.5; ctx.stroke();

    for (let i = 0; i < n; i++) {
        const a = (Math.PI*2*i/n) - Math.PI/2;
        const dr = (scores[i]/100) * r;
        ctx.beginPath(); ctx.arc(cx+dr*Math.cos(a), cy+dr*Math.sin(a), 3.5, 0, Math.PI*2);
        ctx.fillStyle='#ff5555'; ctx.shadowColor='#ff3b3b'; ctx.shadowBlur=8; ctx.fill(); ctx.shadowBlur=0;
    }

    ctx.font='600 10px Rajdhani,sans-serif'; ctx.fillStyle='#6a9fc0'; ctx.textAlign='center';
    const lr = r + 20;
    for (let i = 0; i < n; i++) {
        const a = (Math.PI*2*i/n) - Math.PI/2;
        ctx.fillText(labels[i], cx+lr*Math.cos(a), cy+lr*Math.sin(a)+4);
    }
}

let radarScores = [92,87,58,63,29,34];
drawRadar(radarScores);

/* ── ANIMATE GAUGE BARS ── */
function animateGauges() {
    document.querySelectorAll('.gauge-fill[data-target]').forEach(el => {
        el.style.width = '0%';
        setTimeout(() => { el.style.width = el.dataset.target; }, 200);
    });
}
window.addEventListener('load', animateGauges);

/* ── LIVE SNAPSHOT ── */
async function fetchSnapshot() {
    try {
        const res = await fetch('/api/snapshot');
        if (!res.ok) return;
        const { snapshot: s } = await res.json();
        document.getElementById('snapCpu').textContent   = s.cpu_pct + '%';
        document.getElementById('snapMem').textContent   = s.mem_pct + '%';
        document.getElementById('snapNet').textContent   = s.net_connections;
        document.getElementById('snapPorts').textContent = s.open_ports.length;
        document.getElementById('snapHost').textContent  = s.hostname;
        document.getElementById('snapDisk').textContent  = s.disk_pct + '%';

        // Color CPU/MEM by load
        colorSnap('snapCpu', s.cpu_pct, 70, 40);
        colorSnap('snapMem', s.mem_pct, 85, 60);
    } catch(e) {
        // Backend not running — silently skip
    }
}
function colorSnap(id, val, hi, med) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.color = val >= hi ? '#ff3b3b' : val >= med ? '#f5a623' : '#00e5a0';
}
fetchSnapshot();
setInterval(fetchSnapshot, 5000);

/* ── HISTORY ── */
async function fetchHistory() {
    try {
        const res = await fetch('/api/history?limit=15');
        if (!res.ok) return;
        const { history } = await res.json();
        renderHistory(history);
    } catch(e) {}
}

function renderHistory(rows) {
    const list = document.getElementById('historyList');
    const count = document.getElementById('historyCount');
    if (!rows.length) return;
    count.textContent = `(${rows.length})`;
    list.innerHTML = rows.map(r => {
        const level = r.risk_level.toLowerCase();
        const time = r.timestamp.slice(0,19).replace('T',' ');
        return `<div class="history-row">
            <span class="h-vector">${r.vector}</span>
            <span class="h-score ${level}">${r.risk_score}</span>
            <span class="h-level ${level}">${r.risk_level}</span>
            <span class="h-time">${time}</span>
        </div>`;
    }).join('');
}

/* ── TERMINAL ENGINE ── */
const terminal = document.getElementById('statusOutput');
const runBtn   = document.getElementById('runSimBtn');
const clearBtn = document.getElementById('clearBtn');
const histBtn  = document.getElementById('historyBtn');
const select   = document.getElementById('vectorSelect');
let scanning   = false;

function termLine(cls, text) {
    const d = document.createElement('div');
    d.className = 'term-line' + (cls ? ' ' + cls : '');
    d.textContent = text === '' ? '\u00a0' : '> ' + text;
    terminal.appendChild(d);
    terminal.scrollTop = terminal.scrollHeight;
}

function termClear() {
    terminal.innerHTML = '';
}

function showCursor() {
    const c = document.createElement('span');
    c.className = 'cursor';
    c.id = 'termCursor';
    terminal.appendChild(c);
}
function removeCursor() {
    const c = document.getElementById('termCursor');
    if (c) c.remove();
}

function replayLogs(logs) {
    termClear();
    showCursor();
    let i = 0;
    const iv = setInterval(() => {
        if (i < logs.length) {
            removeCursor();
            termLine(logs[i].cls, logs[i].text);
            showCursor();
            i++;
        } else {
            clearInterval(iv);
            removeCursor();
            scanning = false;
            runBtn.disabled = false;
            runBtn.textContent = '▶ Run Real Scan';
            fetchHistory();
        }
    }, 120);
}

async function runScan() {
    if (scanning) return;
    scanning = true;
    runBtn.disabled = true;
    runBtn.textContent = '⏳ Scanning...';
    termClear();
    termLine('dim', 'Connecting to Flask backend...');
    termLine('dim', 'POST /api/scan → vector: ' + select.value);
    termLine('', '');

    try {
        const res = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ vector: select.value })
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const { result } = await res.json();

        // Update overall threat level
        document.getElementById('overallThreat').textContent = result.risk_level;

        // Update crypto card if vector matches
        if (result.vector === 'crypto' || result.vector === 'full') {
            const score = result.risk_score;
            const el = document.getElementById('cryptoScore');
            if (el) el.textContent = score;
            const gauge = document.getElementById('cryptoGauge');
            if (gauge) { gauge.style.width = '0%'; setTimeout(()=>{ gauge.style.width = score+'%'; }, 100); }
        }

        // Update radar if full scan
        if (result.vector === 'full' && result.metrics) {
            // Rough update based on what was scanned
            drawRadar([92, result.risk_score, 58, 63, result.risk_score * 0.4, 34]);
        }

        // Replay logs with typewriter effect
        replayLogs(result.logs);

    } catch(e) {
        termLine('error', 'Connection failed: ' + e.message);
        termLine('warn',  'Is the Flask server running? → python app.py');
        scanning = false;
        runBtn.disabled = false;
        runBtn.textContent = '▶ Run Real Scan';
    }
}

runBtn.addEventListener('click', runScan);
clearBtn.addEventListener('click', () => {
    termClear();
    termLine('dim', '> Terminal cleared. Ready.');
});
histBtn.addEventListener('click', async () => {
    termClear();
    termLine('dim', 'Fetching scan history from database...');
    try {
        const res = await fetch('/api/history?limit=10');
        const { history } = await res.json();
        termLine('header', `── Last ${history.length} Scans ──`);
        history.forEach(r => {
            const level = r.risk_level;
            const cls = level === 'CRITICAL' || level === 'HIGH' ? 'error' : level === 'MEDIUM' ? 'warn' : 'ok';
            termLine(cls, `[${r.timestamp.slice(0,19)}] ${r.vector.padEnd(15)} ${r.risk_score}/100 ${level}`);
        });
        if (!history.length) termLine('dim', 'No scans in database yet.');
    } catch(e) {
        termLine('error', 'Could not fetch history: ' + e.message);
    }
});
