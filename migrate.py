#!/usr/bin/env python3
"""
Migration: Index_v24.html → index.html
Replaces Google Apps Script calls with localStorage backend.
"""

with open('Index_v24.html', 'r', encoding='utf-8') as f:
    content = f.read()

# ────────────────────────────────────────────────────────────────
# 1. LOGIN CSS — inserir antes de </style>
# ────────────────────────────────────────────────────────────────
LOGIN_CSS = """
/* ══ LOGIN MODAL ══ */
#lpLoginModal{position:fixed;inset:0;background:rgba(0,0,0,0.88);z-index:9999;display:none;align-items:center;justify-content:center;}
#lpLoginModal.show{display:flex !important;}
.lp-login-box{background:var(--card);border:1px solid rgba(245,196,0,0.35);border-radius:14px;padding:40px 36px;width:380px;max-width:92vw;box-shadow:0 0 40px rgba(245,196,0,0.08);}
.lp-login-logo{text-align:center;margin-bottom:28px;}
.lp-login-logo h2{font-family:'Barlow Condensed',sans-serif;font-size:24px;font-weight:900;letter-spacing:3px;text-transform:uppercase;color:var(--yellow);}
.lp-login-logo p{font-size:11px;color:var(--text-muted);letter-spacing:1px;margin-top:4px;}
.lp-login-field{margin-bottom:16px;}
.lp-login-field label{display:block;font-size:10px;letter-spacing:2px;text-transform:uppercase;color:var(--text-muted);margin-bottom:6px;font-weight:600;}
.lp-login-field input{width:100%;background:var(--bg2);border:1px solid var(--border2);border-radius:7px;padding:11px 14px;color:var(--text);font-size:14px;transition:border .2s;}
.lp-login-field input:focus{outline:none;border-color:var(--yellow);}
.lp-login-btn{width:100%;background:var(--yellow);color:#000;border:none;border-radius:7px;padding:13px;font-family:'Barlow Condensed',sans-serif;font-size:17px;font-weight:900;letter-spacing:2px;text-transform:uppercase;cursor:pointer;margin-top:6px;transition:background .15s;}
.lp-login-btn:hover{background:var(--yellow2);}
.lp-login-err{color:var(--red);font-size:12px;text-align:center;margin-top:12px;display:none;padding:8px;background:rgba(239,68,68,0.08);border-radius:6px;}
.lp-login-err.show{display:block;}
.lp-login-skip{display:block;text-align:center;font-size:11px;color:var(--text-muted);margin-top:14px;cursor:pointer;text-decoration:underline;}
.lp-login-skip:hover{color:var(--text);}
#btnEntrar{background:transparent;border:1px solid rgba(245,196,0,0.35);color:var(--yellow);padding:5px 13px;border-radius:6px;font-size:10px;font-weight:700;letter-spacing:1.5px;cursor:pointer;text-transform:uppercase;display:none;transition:background .15s;}
#btnEntrar:hover{background:rgba(245,196,0,0.1);}
#btnSair{background:transparent;border:1px solid rgba(255,255,255,0.08);color:var(--text-muted);padding:4px 9px;border-radius:5px;font-size:10px;cursor:pointer;margin-left:6px;letter-spacing:1px;transition:all .15s;}
#btnSair:hover{border-color:var(--red);color:var(--red);}
#btnExport,#btnImport{background:transparent;border:1px solid var(--border2);color:var(--text-muted);padding:5px 10px;border-radius:5px;font-size:10px;cursor:pointer;display:none;letter-spacing:.5px;transition:all .15s;}
#btnExport:hover,#btnImport:hover{border-color:var(--yellow);color:var(--yellow);}
"""

content = content.replace('</style>', LOGIN_CSS + '</style>', 1)

# ────────────────────────────────────────────────────────────────
# 2. TOPBAR — adicionar botões Entrar / Sair / Backup / Restaurar
# ────────────────────────────────────────────────────────────────
OLD_BADGE = '      <span class="user-badge-role" id="userRoleBadge"></span>\n    </div>'
NEW_BADGE = '      <span class="user-badge-role" id="userRoleBadge"></span>\n      <button id="btnSair" onclick="doLogout()">Sair</button>\n    </div>'
content = content.replace(OLD_BADGE, NEW_BADGE, 1)

OLD_TOPBAR_BADGE = '    <span class="topbar-badge">🟢 Sistema Ativo</span>'
NEW_TOPBAR_BADGE = (
    '    <button id="btnEntrar" onclick="showLoginModal()">Entrar</button>\n'
    '    <button id="btnExport" onclick="exportarDados()" title="Exportar dados">⬇ Backup</button>\n'
    '    <button id="btnImport" onclick="importarDados()" title="Importar dados">⬆ Restaurar</button>\n'
    '    <span class="topbar-badge">🟢 Sistema Ativo</span>'
)
content = content.replace(OLD_TOPBAR_BADGE, NEW_TOPBAR_BADGE, 1)

# ────────────────────────────────────────────────────────────────
# 3. POLYFILL — injetar no início do bloco <script>
# ────────────────────────────────────────────────────────────────
GAS_POLYFILL = r"""
// ════════════════════════════════════════════════════════════════
// BACKEND LOCAL — substitui Google Apps Script
// Dados em localStorage · Usuários em config.json
// ════════════════════════════════════════════════════════════════
var _lpConfig = null;

var LP = {
  getData: function(){
    try{ return JSON.parse(localStorage.getItem('lp_data') || '{}'); }catch(e){ return {}; }
  },
  saveData: function(d){
    try{ localStorage.setItem('lp_data', JSON.stringify(d)); }
    catch(e){ alert('Armazenamento cheio. Exporte e limpe os dados antes de continuar.'); }
  },
  getSession: function(){
    try{ return JSON.parse(sessionStorage.getItem('lp_session') || 'null'); }catch(e){ return null; }
  },
  saveSession: function(s){ sessionStorage.setItem('lp_session', JSON.stringify(s)); },
  clearSession: function(){ sessionStorage.removeItem('lp_session'); }
};

var GAS_IMPL = {
  iniciarApp: function(){
    var cfg = _lpConfig || {users:[], unidades:[]};
    var allU = (cfg.unidades || []).map(function(u){ return u.nome || u; });
    var sess = LP.getSession();
    if(sess && sess.email){
      var found = null;
      (cfg.users || []).forEach(function(u){ if(u.email === sess.email) found = u; });
      if(found) return {permissao: found.permissao, email: found.email, unidadesUsuario: found.unidades || [], unidades: allU};
    }
    return {permissao: 'publico', email: '', unidadesUsuario: [], unidades: allU};
  },

  lerBase: function(tipo, unidades){
    var all = LP.getData();
    var records = all[tipo] || [];
    if(!unidades || !unidades.length) return records;
    return records.filter(function(r){
      var u = r['UNIDADE'] || r['Unidade'] || '';
      return unidades.indexOf(u) !== -1;
    });
  },

  atualizarRegistro: function(tipo, updated){
    var all = LP.getData();
    var records = all[tipo] || [];
    var idx = -1;
    for(var i = 0; i < records.length; i++){
      if(records[i]['ID'] === updated['ID']){ idx = i; break; }
    }
    if(idx >= 0) records[idx] = updated; else records.push(updated);
    all[tipo] = records;
    LP.saveData(all);
    return {ok: true};
  },

  salvarRegistro: function(tipo, dados){
    var all = LP.getData();
    var records = all[tipo] || [];
    var pfxMap = {
      selo:'SEL', cracha:'CRA', investigacao:'INV', cadeado:'CAD',
      cartao:'CAR', disciplinar:'DIS', ronda:'RON', bau:'BAU',
      pacote:'PAC', lacre:'LAC', acesso:'ACE'
    };
    var pfx = pfxMap[tipo] || tipo.slice(0,3).toUpperCase();
    var id  = pfx + '-' + String(records.length + 1).padStart(4, '0');
    var now = new Date();
    var d   = String(now.getDate()).padStart(2,'0') + '/' + String(now.getMonth()+1).padStart(2,'0') + '/' + now.getFullYear();
    var h   = String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
    var record = {ID: id, DATA: d, HORA: h, STATUS: 'Pendente'};
    Object.keys(dados).forEach(function(k){ record[k] = dados[k]; });
    records.push(record);
    all[tipo] = records;
    LP.saveData(all);
    return {id: id};
  },

  lerUnidadesComCoordenadas: function(){
    var cfg = _lpConfig || {};
    return (cfg.unidades || []).filter(function(u){ return u.lat && u.lng; });
  }
};

function _makeGasProxy(s, f){
  var _s = s || function(){}, _f = f || function(){};
  var p = {
    withSuccessHandler: function(fn){ _s = fn; return p; },
    withFailureHandler: function(fn){ _f = fn; return p; }
  };
  ['iniciarApp','lerBase','atualizarRegistro','salvarRegistro','lerUnidadesComCoordenadas'].forEach(function(m){
    p[m] = function(){
      var a = Array.prototype.slice.call(arguments), s = _s, f = _f;
      _s = function(){}; _f = function(){};
      setTimeout(function(){
        try{ if(s) s(GAS_IMPL[m].apply(null, a)); }
        catch(e){ if(f) f(String(e)); }
      }, 10);
    };
  });
  return p;
}

var google = {
  script: {
    run: {
      withSuccessHandler: function(fn){ return _makeGasProxy(fn, null); },
      withFailureHandler: function(fn){ return _makeGasProxy(null, fn); }
    }
  }
};

"""

content = content.replace('<script>\n// ══ TABS ══', '<script>\n' + GAS_POLYFILL + '// ══ TABS ══', 1)

# ────────────────────────────────────────────────────────────────
# 4. SUBSTITUIR chamada direta iniciarApp() por bootstrap com fetch
# ────────────────────────────────────────────────────────────────
OLD_INIT = (
    'google.script.run\n'
    '  .withSuccessHandler(_onAuthSuccess)\n'
    '  .withFailureHandler(_onAuthFail)\n'
    '  .iniciarApp();'
)
NEW_INIT = (
    '// Carrega config.json e então inicia app\n'
    '(function _bootstrapApp(){\n'
    '  fetch(\'./config.json?t=\' + Date.now())\n'
    '    .then(function(r){ return r.ok ? r.json() : Promise.reject(\'not found\'); })\n'
    '    .then(function(cfg){\n'
    '      _lpConfig = cfg;\n'
    '      try{ localStorage.setItem(\'lp_config\', JSON.stringify(cfg)); }catch(e){}\n'
    '    })\n'
    '    .catch(function(){\n'
    '      var c = localStorage.getItem(\'lp_config\');\n'
    '      if(c){ try{ _lpConfig = JSON.parse(c); }catch(e){} }\n'
    '      if(!_lpConfig) _lpConfig = {\n'
    '        users: [{email:\'admin@local\', senha:\'admin123\', permissao:\'Administrador\', unidades:[]}],\n'
    '        unidades: []\n'
    '      };\n'
    '    })\n'
    '    .finally(function(){\n'
    '      google.script.run\n'
    '        .withSuccessHandler(_onAuthSuccess)\n'
    '        .withFailureHandler(_onAuthFail)\n'
    '        .iniciarApp();\n'
    '    });\n'
    '})();'
)
content = content.replace(OLD_INIT, NEW_INIT, 1)

# ────────────────────────────────────────────────────────────────
# 5. LOGIN MODAL HTML + JS — adicionar antes de </script>\n</body>
# ────────────────────────────────────────────────────────────────
LOGIN_JS = """

// ════════════════════════════════════════════════════════════════
// LOGIN / LOGOUT
// ════════════════════════════════════════════════════════════════
function showLoginModal(){
  var modal = document.getElementById('lpLoginModal');
  if(modal) modal.classList.add('show');
  setTimeout(function(){ var e = document.getElementById('lpLoginEmail'); if(e) e.focus(); }, 80);
}
function hideLoginModal(){
  document.getElementById('lpLoginModal').classList.remove('show');
  document.getElementById('lpLoginErr').classList.remove('show');
}
function doLogin(){
  var email = (document.getElementById('lpLoginEmail').value || '').trim().toLowerCase();
  var senha = document.getElementById('lpLoginSenha').value || '';
  var cfg   = _lpConfig || {users:[]};
  var user  = null;
  (cfg.users || []).forEach(function(u){
    if((u.email || '').toLowerCase() === email && u.senha === senha) user = u;
  });
  if(!user){ document.getElementById('lpLoginErr').classList.add('show'); return; }
  LP.saveSession({email: user.email});
  hideLoginModal();
  document.getElementById('authLoading').style.display = 'flex';
  google.script.run.withSuccessHandler(_onAuthSuccess).withFailureHandler(_onAuthFail).iniciarApp();
}
function doLogout(){
  LP.clearSession();
  location.reload();
}

// ════════════════════════════════════════════════════════════════
// BOTÕES ENTRAR / SAIR / BACKUP — sincronizados com permissão
// ════════════════════════════════════════════════════════════════
(function(){
  var _orig = window.aplicarPermissoes;
  window.aplicarPermissoes = function(permissao, unidadesArr, email){
    _orig(permissao, unidadesArr, email);
    var bE   = document.getElementById('btnEntrar');
    var bS   = document.getElementById('btnSair');
    var bExp = document.getElementById('btnExport');
    var bImp = document.getElementById('btnImport');
    if(bE)   bE.style.display   = (permissao === 'publico' && !email) ? 'inline-block' : 'none';
    if(bS)   bS.style.display   = (email && permissao !== 'publico')  ? 'inline-block' : 'none';
    if(bExp) bExp.style.display = (permissao === 'Administrador')      ? 'inline-block' : 'none';
    if(bImp) bImp.style.display = (permissao === 'Administrador')      ? 'inline-block' : 'none';
  };
})();

// Enter no modal de login
document.addEventListener('keydown', function(e){
  if(e.key === 'Enter' && document.getElementById('lpLoginModal').classList.contains('show')) doLogin();
});

// ════════════════════════════════════════════════════════════════
// EXPORTAR / IMPORTAR DADOS (backup localStorage)
// ════════════════════════════════════════════════════════════════
function exportarDados(){
  var data = LP.getData();
  var json = JSON.stringify(data, null, 2);
  var blob = new Blob([json], {type: 'application/json'});
  var url  = URL.createObjectURL(blob);
  var a    = document.createElement('a');
  a.href = url;
  a.download = 'lp-backup-' + new Date().toISOString().split('T')[0] + '.json';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
function importarDados(){
  var inp = document.createElement('input');
  inp.type = 'file'; inp.accept = '.json';
  inp.onchange = function(e){
    var f = e.target.files[0]; if(!f) return;
    var r = new FileReader();
    r.onload = function(ev){
      try{
        var data = JSON.parse(ev.target.result);
        if(confirm('Isso vai SUBSTITUIR todos os dados atuais. Continuar?')){
          LP.saveData(data);
          location.reload();
        }
      }catch(err){ alert('Arquivo inválido: ' + err.message); }
    };
    r.readAsText(f);
  };
  inp.click();
}
"""

LOGIN_MODAL = """
<!-- ══ LOGIN MODAL ══ -->
<div id="lpLoginModal">
  <div class="lp-login-box">
    <div class="lp-login-logo">
      <h2>🔒 Loss Prevention</h2>
      <p>Acesse com suas credenciais</p>
    </div>
    <div class="lp-login-field">
      <label>E-mail</label>
      <input type="email" id="lpLoginEmail" placeholder="seu@email.com" autocomplete="username">
    </div>
    <div class="lp-login-field">
      <label>Senha</label>
      <input type="password" id="lpLoginSenha" placeholder="••••••••" autocomplete="current-password">
    </div>
    <button class="lp-login-btn" onclick="doLogin()">Entrar</button>
    <div class="lp-login-err" id="lpLoginErr">E-mail ou senha incorretos.</div>
    <span class="lp-login-skip" onclick="hideLoginModal()">Continuar como público</span>
  </div>
</div>
"""

# Inserir JS antes de </script> e modal antes de </body>
content = content.replace('\n\n\n</script>\n</body>\n</html>',
                           LOGIN_JS + '\n\n</script>\n' + LOGIN_MODAL + '</body>\n</html>', 1)

# ────────────────────────────────────────────────────────────────
# 6. Escrever index.html
# ────────────────────────────────────────────────────────────────
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ index.html gerado com sucesso")

# ────────────────────────────────────────────────────────────────
# Verificar substituições aplicadas
# ────────────────────────────────────────────────────────────────
checks = [
    ('google.script.run polyfill', 'var google = {'),
    ('GAS_IMPL', 'var GAS_IMPL = {'),
    ('LP namespace', 'var LP = {'),
    ('login modal', 'id="lpLoginModal"'),
    ('btnEntrar', 'id="btnEntrar"'),
    ('bootstrap fetch', '_bootstrapApp'),
    ('doLogin fn', 'function doLogin()'),
    ('exportarDados fn', 'function exportarDados()'),
]
for label, needle in checks:
    found = needle in content
    status = '✓' if found else '✗ MISSING'
    print(f"  {status}  {label}")
