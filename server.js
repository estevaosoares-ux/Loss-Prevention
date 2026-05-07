const express = require('express');
const fs      = require('fs');
const path    = require('path');

const app  = express();
const PORT = process.env.PORT || 3000;
const DB   = path.join(__dirname, 'data', 'db.json');

// ── Helpers de persistência ──────────────────────────────────────
function loadDB() {
  try { return JSON.parse(fs.readFileSync(DB, 'utf8')); } catch { return {}; }
}
function saveDB(data) {
  fs.mkdirSync(path.dirname(DB), { recursive: true });
  fs.writeFileSync(DB, JSON.stringify(data, null, 2), 'utf8');
}

const PREFIX = {
  selo:'SEL', cracha:'CRA', investigacao:'INV', cadeado:'CAD',
  cartao:'CAR', disciplinar:'DIS', ronda:'RON', bau:'BAU',
  pacote:'PAC', lacre:'LAC', acesso:'ACE'
};

function now() {
  const d = new Date();
  const pad = n => String(n).padStart(2,'0');
  return {
    data: `${pad(d.getDate())}/${pad(d.getMonth()+1)}/${d.getFullYear()}`,
    hora: `${pad(d.getHours())}:${pad(d.getMinutes())}`
  };
}

// ── Middleware ───────────────────────────────────────────────────
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// ── API principal ────────────────────────────────────────────────
app.post('/api/gas', (req, res) => {
  const { action, tipo, dados, updated, unidades } = req.body;
  const db = loadDB();

  try {
    if (action === 'lerBase') {
      let recs = db[tipo] || [];
      if (unidades && unidades.length) {
        recs = recs.filter(r => unidades.includes(r['UNIDADE'] || r['Unidade'] || ''));
      }
      return res.json(recs);
    }

    if (action === 'salvarRegistro') {
      const recs = db[tipo] || [];
      const pfx  = PREFIX[tipo] || tipo.slice(0,3).toUpperCase();
      const id   = `${pfx}-${String(recs.length + 1).padStart(4,'0')}`;
      const { data, hora } = now();
      const rec  = { ID: id, DATA: data, HORA: hora, STATUS: 'Pendente', ...dados };
      recs.push(rec);
      db[tipo] = recs;
      saveDB(db);
      return res.json({ id });
    }

    if (action === 'atualizarRegistro') {
      const recs = db[tipo] || [];
      const idx  = recs.findIndex(r => r['ID'] === updated['ID']);
      if (idx >= 0) recs[idx] = { ...recs[idx], ...updated };
      else recs.push(updated);
      db[tipo] = recs;
      saveDB(db);
      return res.json({ ok: true });
    }

    if (action === 'lerUnidades') {
      const cfg = loadConfig();
      return res.json(cfg.unidades || []);
    }

    if (action === 'iniciarApp') {
      const cfg  = loadConfig();
      const allU = (cfg.unidades || []).map(u => u.nome || u);
      // auth é feita no frontend; aqui só devolve dados
      return res.json({ permissao: 'Administrador', email: '', unidadesUsuario: [], unidades: allU });
    }

    res.status(400).json({ error: 'action desconhecida: ' + action });
  } catch (e) {
    res.status(500).json({ error: String(e) });
  }
});

// ── Config dinâmica ──────────────────────────────────────────────
function loadConfig() {
  try { return JSON.parse(fs.readFileSync(path.join(__dirname, 'public', 'config.json'), 'utf8')); }
  catch { return { users: [], unidades: [] }; }
}

app.get('/api/config', (_req, res) => res.json(loadConfig()));

// ── Health check (Fury usa isso) ─────────────────────────────────
app.get('/health', (_req, res) => res.json({ status: 'ok' }));
app.get('/ping',   (_req, res) => res.send('pong'));

// ── Start ────────────────────────────────────────────────────────
app.listen(PORT, () => console.log(`Loss Prevention rodando na porta ${PORT}`));
