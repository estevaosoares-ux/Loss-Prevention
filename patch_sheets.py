#!/usr/bin/env python3
"""
Patch: substituir GAS Web App → Google Sheets API v4 direta
"""

with open('index.html', 'r', encoding='utf-8') as f:
    c = f.read()

# ──────────────────────────────────────────────────────────────────
# 1. Adicionar GIS (Google Identity Services) antes de </head>
# ──────────────────────────────────────────────────────────────────
GIS_TAG = '<script src="https://accounts.google.com/gsi/client" onload="window._gisReady=true;if(window._onGisReady)window._onGisReady();" async defer></script>\n'
c = c.replace('</head>', GIS_TAG + '</head>', 1)

# ──────────────────────────────────────────────────────────────────
# 2. Corrigir declaração google para não destruir objeto GIS
# ──────────────────────────────────────────────────────────────────
c = c.replace(
    'var google = {\n  script: {\n    run: {\n      withSuccessHandler: function(fn){ return _makeGasProxy(fn, null); },\n      withFailureHandler: function(fn){ return _makeGasProxy(null, fn); }\n    }\n  }\n};',
    'window.google = window.google || {};\nwindow.google.script = {\n  run: {\n    withSuccessHandler: function(fn){ return _makeGasProxy(fn, null); },\n    withFailureHandler: function(fn){ return _makeGasProxy(null, fn); }\n  }\n};',
    1
)

# ──────────────────────────────────────────────────────────────────
# 3. Substituir GAS_IMPL completo por versão Sheets API
# ──────────────────────────────────────────────────────────────────
OLD_IMPL_START = 'var GAS_IMPL = {'
OLD_IMPL_END   = "  lerUnidadesComCoordenadas: function(){\n    if(_lpConfig && _lpConfig.gasWebAppUrl){\n      return GAS_IMPL._post({action:'lerUnidades'});\n    }\n    return (_lpConfig&&_lpConfig.unidades||[]).filter(function(u){return u.lat&&u.lng;});\n  }\n};"

NEW_IMPL = r"""// ── Token Google OAuth ─────────────────────────────────────────
var _gToken        = null;  // { token, expiresAt }
var _tokenClient   = null;

function _onGisReady() {
  _initTokenClient();
}

function _initTokenClient() {
  var cid = _lpConfig && _lpConfig.googleClientId;
  if (!cid || !window.google || !window.google.accounts) return;
  _tokenClient = window.google.accounts.oauth2.initTokenClient({
    client_id: cid,
    scope: 'https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/userinfo.email',
    callback: ''  // definido por chamada
  });
}

function _getGoogleToken() {
  if (_gToken && Date.now() < _gToken.expiresAt) return Promise.resolve(_gToken.token);
  if (!_tokenClient) return Promise.reject('Configure o Google Client ID em ⚙ Configurações.');
  return new Promise(function(resolve, reject) {
    _tokenClient.callback = function(resp) {
      if (resp.error) { reject(resp.error_description || resp.error); return; }
      _gToken = { token: resp.access_token, expiresAt: Date.now() + (resp.expires_in * 1000) - 60000 };
      resolve(_gToken.token);
    };
    _tokenClient.requestAccessToken({ prompt: '' });
  });
}

// ── Chamada à Sheets API ────────────────────────────────────────
function _sheetsReq(method, path, body) {
  var sid = _lpConfig && _lpConfig.spreadsheetId;
  if (!sid) return Promise.reject('spreadsheetId não configurado em ⚙ Configurações.');
  return _getGoogleToken().then(function(tok) {
    var opts = { method: method, headers: { Authorization: 'Bearer ' + tok, 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    return fetch('https://sheets.googleapis.com/v4/spreadsheets/' + sid + path, opts);
  }).then(function(r) {
    return r.json().then(function(d) {
      if (!r.ok) throw new Error((d.error && d.error.message) || 'HTTP ' + r.status);
      return d;
    });
  });
}

function _getSheetName(tipo) {
  var n = (_lpConfig && _lpConfig.sheetNames && _lpConfig.sheetNames[tipo]);
  return n || tipo.toUpperCase();
}

function _parseSheet(data) {
  if (!data.values || data.values.length < 2) return [];
  var h = data.values[0];
  return data.values.slice(1).map(function(row) {
    var o = {};
    h.forEach(function(k, i) { o[k] = row[i] !== undefined ? String(row[i]) : ''; });
    return o;
  }).filter(function(r) { return r['ID'] || r['id']; });
}

// ── GAS_IMPL ────────────────────────────────────────────────────
var GAS_IMPL = {

  iniciarApp: function() {
    var cfg  = _lpConfig || {users:[], unidades:[]};
    var allU = (cfg.unidades || []).map(function(u) { return u.nome || u; });
    var sess = LP.getSession();
    if (sess && sess.email) {
      var found = null;
      (cfg.users || []).forEach(function(u) { if (u.email === sess.email) found = u; });
      if (found) return { permissao: found.permissao, email: sess.email, unidadesUsuario: found.unidades || [], unidades: allU };
      // Email não cadastrado → público mas autenticado
      return { permissao: 'publico', email: sess.email, unidadesUsuario: [], unidades: allU };
    }
    return { permissao: 'publico', email: '', unidadesUsuario: [], unidades: allU };
  },

  lerBase: function(tipo, unidades) {
    if (!(_lpConfig && _lpConfig.spreadsheetId)) {
      var all = LP.getData(), recs = all[tipo] || [];
      if (!unidades || !unidades.length) return recs;
      return recs.filter(function(r) { return unidades.indexOf(r['UNIDADE'] || r['Unidade'] || '') !== -1; });
    }
    var sheet = _getSheetName(tipo);
    return _sheetsReq('GET', '/values/' + encodeURIComponent(sheet))
      .then(function(data) {
        var recs = _parseSheet(data);
        if (!unidades || !unidades.length) return recs;
        return recs.filter(function(r) { return unidades.indexOf(r['UNIDADE'] || r['Unidade'] || '') !== -1; });
      });
  },

  atualizarRegistro: function(tipo, updated) {
    if (!(_lpConfig && _lpConfig.spreadsheetId)) {
      var all = LP.getData(), recs = all[tipo] || [], idx = -1;
      for (var i = 0; i < recs.length; i++) { if (recs[i]['ID'] === updated['ID']) { idx = i; break; } }
      if (idx >= 0) recs[idx] = updated; else recs.push(updated);
      all[tipo] = recs; LP.saveData(all);
      return {ok: true};
    }
    var sheet = _getSheetName(tipo);
    return _sheetsReq('GET', '/values/' + encodeURIComponent(sheet))
      .then(function(data) {
        if (!data.values || data.values.length < 2) throw new Error('Aba vazia: ' + sheet);
        var headers = data.values[0];
        var idCol   = headers.indexOf('ID');
        if (idCol === -1) throw new Error('Coluna ID não encontrada em ' + sheet);
        var rowIdx  = -1;
        for (var i = 1; i < data.values.length; i++) {
          if (String(data.values[i][idCol]) === String(updated['ID'])) { rowIdx = i; break; }
        }
        if (rowIdx === -1) throw new Error('ID não encontrado: ' + updated['ID']);
        var row   = headers.map(function(h) { return updated[h] !== undefined ? String(updated[h]) : String(data.values[rowIdx][headers.indexOf(h)] || ''); });
        var range = encodeURIComponent(sheet + '!A' + (rowIdx + 1));
        return _sheetsReq('PUT', '/values/' + range + '?valueInputOption=USER_ENTERED', { values: [row] })
          .then(function() { return {ok: true}; });
      });
  },

  salvarRegistro: function(tipo, dados) {
    if (!(_lpConfig && _lpConfig.spreadsheetId)) {
      var all = LP.getData(), recs = all[tipo] || [];
      var pfx = {selo:'SEL',cracha:'CRA',investigacao:'INV',cadeado:'CAD',cartao:'CAR',disciplinar:'DIS',ronda:'RON',bau:'BAU',pacote:'PAC',lacre:'LAC',acesso:'ACE'}[tipo] || tipo.slice(0,3).toUpperCase();
      var id  = pfx + '-' + String(recs.length + 1).padStart(4, '0');
      var now = new Date(), d = String(now.getDate()).padStart(2,'0') + '/' + String(now.getMonth()+1).padStart(2,'0') + '/' + now.getFullYear(), h = String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
      var rec = {ID: id, DATA: d, HORA: h, STATUS: 'Pendente'};
      Object.keys(dados).forEach(function(k) { rec[k] = dados[k]; });
      recs.push(rec); all[tipo] = recs; LP.saveData(all);
      return {id: id};
    }
    var sheet = _getSheetName(tipo);
    return _sheetsReq('GET', '/values/' + encodeURIComponent(sheet))
      .then(function(data) {
        var headers  = (data.values && data.values[0]) ? data.values[0] : [];
        var rowCount = data.values ? Math.max(data.values.length - 1, 0) : 0;
        var pfx = {selo:'SEL',cracha:'CRA',investigacao:'INV',cadeado:'CAD',cartao:'CAR',disciplinar:'DIS',ronda:'RON',bau:'BAU',pacote:'PAC',lacre:'LAC',acesso:'ACE'}[tipo] || tipo.slice(0,3).toUpperCase();
        var id  = pfx + '-' + String(rowCount + 1).padStart(4, '0');
        var now = new Date(), d = String(now.getDate()).padStart(2,'0') + '/' + String(now.getMonth()+1).padStart(2,'0') + '/' + now.getFullYear(), h = String(now.getHours()).padStart(2,'0') + ':' + String(now.getMinutes()).padStart(2,'0');
        var rec = {ID: id, DATA: d, HORA: h, STATUS: 'Pendente'};
        Object.keys(dados).forEach(function(k) { rec[k] = dados[k]; });
        // Novos cabeçalhos se necessário
        var newCols = Object.keys(rec).filter(function(k) { return headers.indexOf(k) === -1; });
        if (headers.length === 0) headers = Object.keys(rec);
        else if (newCols.length) headers = headers.concat(newCols);
        var ops = [];
        if (newCols.length || !data.values || data.values.length === 0) {
          ops.push(_sheetsReq('PUT', '/values/' + encodeURIComponent(sheet + '!1:1') + '?valueInputOption=USER_ENTERED', { values: [headers] }));
        }
        return Promise.all(ops).then(function() {
          var row = headers.map(function(col) { return rec[col] !== undefined ? String(rec[col]) : ''; });
          return _sheetsReq('POST', '/values/' + encodeURIComponent(sheet) + ':append?valueInputOption=USER_ENTERED', { values: [row] })
            .then(function() { return {id: id}; });
        });
      });
  },

  lerUnidadesComCoordenadas: function() {
    if (!(_lpConfig && _lpConfig.spreadsheetId)) {
      return (_lpConfig && _lpConfig.unidades || []).filter(function(u) { return u.lat && u.lng; });
    }
    return _sheetsReq('GET', '/values/UNIDADES')
      .then(function(data) {
        if (!data.values || data.values.length < 2) return [];
        var h = data.values[0], nIdx = Math.max(h.indexOf('NOME'), 0), llIdx = h.indexOf('LATLONG');
        if (llIdx === -1) return [];
        var result = [];
        data.values.slice(1).forEach(function(row) {
          var ll = String(row[llIdx] || '').trim();
          if (!ll) return;
          var p = ll.split(',');
          if (p.length < 2) return;
          result.push({ nome: String(row[nIdx]||''), unidade: String(row[nIdx]||''), lat: p[0].trim(), lng: p[1].trim() });
        });
        return result;
      });
  }
};"""

# Find and replace the full GAS_IMPL block
start_idx = c.find(OLD_IMPL_START)
end_idx   = c.find(OLD_IMPL_END)
if start_idx == -1 or end_idx == -1:
    print("ERRO: não encontrou GAS_IMPL para substituir")
    exit(1)
end_idx += len(OLD_IMPL_END)
c = c[:start_idx] + NEW_IMPL + c[end_idx:]
print("✓ GAS_IMPL substituído (Sheets API)")

# ──────────────────────────────────────────────────────────────────
# 4. Atualizar bootstrap: init token client + restaurar config
# ──────────────────────────────────────────────────────────────────
OLD_FINALLY = """    .finally(function(){
      // Se config.json não tiver URL mas o admin salvou manualmente, restaura
      if(_lpConfig && !_lpConfig.gasWebAppUrl){
        var saved = localStorage.getItem('lp_webAppUrl');
        if(saved) _lpConfig.gasWebAppUrl = saved;
      }
      google.script.run
        .withSuccessHandler(_onAuthSuccess)
        .withFailureHandler(_onAuthFail)
        .iniciarApp();
    });"""

NEW_FINALLY = """    .finally(function(){
      // Restaura configurações salvas manualmente (override ao config.json)
      var savedCid = localStorage.getItem('lp_googleClientId');
      var savedSid = localStorage.getItem('lp_spreadsheetId');
      if (_lpConfig && savedCid) _lpConfig.googleClientId  = savedCid;
      if (_lpConfig && savedSid) _lpConfig.spreadsheetId   = savedSid;
      // Restaura sheetNames se salvos
      try { var sn = localStorage.getItem('lp_sheetNames'); if(sn && _lpConfig) _lpConfig.sheetNames = JSON.parse(sn); } catch(e){}
      // Inicia token client GIS se já carregou
      if (window._gisReady) _initTokenClient();
      window._onGisReady = _initTokenClient;
      window.google.script.run
        .withSuccessHandler(_onAuthSuccess)
        .withFailureHandler(_onAuthFail)
        .iniciarApp();
    });"""

c = c.replace(OLD_FINALLY, NEW_FINALLY, 1)
print("✓ Bootstrap atualizado")

# ──────────────────────────────────────────────────────────────────
# 5. Substituir doLogin por versão OAuth Google
# ──────────────────────────────────────────────────────────────────
OLD_DOLOGIN = """function doLogin(){
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
}"""

NEW_DOLOGIN = """function doLogin(){
  var hasGoogle = _lpConfig && _lpConfig.googleClientId;
  if (hasGoogle) {
    // ── Login via Google OAuth ──
    if (!_tokenClient) { _initTokenClient(); }
    if (!_tokenClient) { alert('GIS ainda não carregou. Aguarde e tente novamente.'); return; }
    document.getElementById('lpLoginErr').classList.remove('show');
    _tokenClient.callback = function(resp) {
      if (resp.error) {
        document.getElementById('lpLoginErr').textContent = 'Erro Google: ' + (resp.error_description || resp.error);
        document.getElementById('lpLoginErr').classList.add('show');
        return;
      }
      _gToken = { token: resp.access_token, expiresAt: Date.now() + (resp.expires_in * 1000) - 60000 };
      fetch('https://www.googleapis.com/oauth2/v1/userinfo?alt=json', {
        headers: { Authorization: 'Bearer ' + _gToken.token }
      })
      .then(function(r){ return r.json(); })
      .then(function(info){
        LP.saveSession({ email: info.email });
        hideLoginModal();
        document.getElementById('authLoading').style.display = 'flex';
        window.google.script.run.withSuccessHandler(_onAuthSuccess).withFailureHandler(_onAuthFail).iniciarApp();
      })
      .catch(function(){ document.getElementById('lpLoginErr').textContent='Erro ao obter dados do usuário.'; document.getElementById('lpLoginErr').classList.add('show'); });
    };
    _tokenClient.requestAccessToken({ prompt: 'select_account' });
  } else {
    // ── Fallback: login email+senha (modo localStorage) ──
    var email = (document.getElementById('lpLoginEmail').value || '').trim().toLowerCase();
    var senha = document.getElementById('lpLoginSenha').value || '';
    var cfg   = _lpConfig || {users:[]};
    var user  = null;
    (cfg.users || []).forEach(function(u){ if((u.email||'').toLowerCase()===email && u.senha===senha) user=u; });
    if(!user){ document.getElementById('lpLoginErr').classList.add('show'); return; }
    LP.saveSession({email: user.email});
    hideLoginModal();
    document.getElementById('authLoading').style.display = 'flex';
    window.google.script.run.withSuccessHandler(_onAuthSuccess).withFailureHandler(_onAuthFail).iniciarApp();
  }
}
function doLogout(){
  if (_gToken && window.google && window.google.accounts && window.google.accounts.oauth2) {
    window.google.accounts.oauth2.revoke(_gToken.token, function(){});
    _gToken = null;
  }
  LP.clearSession();
  location.reload();
}"""

c = c.replace(OLD_DOLOGIN, NEW_DOLOGIN, 1)
print("✓ doLogin/doLogout atualizados")

# ──────────────────────────────────────────────────────────────────
# 6. Atualizar modal de login para mostrar botão Google quando configurado
# ──────────────────────────────────────────────────────────────────
OLD_LOGIN_MODAL = """<!-- ══ LOGIN MODAL ══ -->
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
</div>"""

NEW_LOGIN_MODAL = """<!-- ══ LOGIN MODAL ══ -->
<div id="lpLoginModal">
  <div class="lp-login-box">
    <div class="lp-login-logo">
      <h2>🔒 Loss Prevention</h2>
      <p id="lpLoginSubtitle">Acesse com sua conta Google</p>
    </div>
    <div id="lpLoginGoogleWrap">
      <button class="lp-login-btn" onclick="doLogin()" style="display:flex;align-items:center;justify-content:center;gap:10px;">
        <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20H24v8h11.3C33.6 32.6 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 8 2.9l5.7-5.7C34.1 6.5 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20c11 0 19.7-8 19.7-20 0-1.3-.1-2.7-.3-4z"/><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.5 16 19 13 24 13c3.1 0 5.8 1.1 8 2.9l5.7-5.7C34.1 6.5 29.3 4 24 4 16.3 4 9.6 8.3 6.3 14.7z"/><path fill="#4CAF50" d="M24 44c5.2 0 9.9-1.9 13.5-5l-6.2-5.2C29.5 35.5 26.9 36 24 36c-5.2 0-9.6-3.3-11.2-8L6.1 33.2C9.5 39.6 16.2 44 24 44z"/><path fill="#1976D2" d="M43.6 20H24v8h11.3c-.9 2.5-2.6 4.6-4.8 6l6.2 5.2C40.5 35.7 44 30.3 44 24c0-1.3-.1-2.7-.4-4z"/></svg>
        Entrar com Google
      </button>
    </div>
    <div id="lpLoginLocalWrap" style="display:none">
      <div class="lp-login-field">
        <label>E-mail</label>
        <input type="email" id="lpLoginEmail" placeholder="seu@email.com" autocomplete="username">
      </div>
      <div class="lp-login-field">
        <label>Senha</label>
        <input type="password" id="lpLoginSenha" placeholder="••••••••" autocomplete="current-password">
      </div>
      <button class="lp-login-btn" onclick="doLogin()">Entrar</button>
    </div>
    <div class="lp-login-err" id="lpLoginErr">E-mail ou senha incorretos.</div>
    <span class="lp-login-skip" onclick="hideLoginModal()">Continuar como público</span>
  </div>
</div>"""

c = c.replace(OLD_LOGIN_MODAL, NEW_LOGIN_MODAL, 1)
print("✓ Modal de login atualizado (Google OAuth)")

# ──────────────────────────────────────────────────────────────────
# 7. showLoginModal: mostrar UI correta conforme config
# ──────────────────────────────────────────────────────────────────
OLD_SHOW_LOGIN = """function showLoginModal(){
  var modal = document.getElementById('lpLoginModal');
  if(modal) modal.classList.add('show');
  setTimeout(function(){ var e = document.getElementById('lpLoginEmail'); if(e) e.focus(); }, 80);
}"""

NEW_SHOW_LOGIN = """function showLoginModal(){
  var modal = document.getElementById('lpLoginModal');
  if(modal) modal.classList.add('show');
  // Mostra UI Google ou email/senha dependendo da config
  var hasGoogle  = _lpConfig && _lpConfig.googleClientId;
  var gWrap  = document.getElementById('lpLoginGoogleWrap');
  var lWrap  = document.getElementById('lpLoginLocalWrap');
  var subtitle = document.getElementById('lpLoginSubtitle');
  if (gWrap) gWrap.style.display = hasGoogle ? 'block' : 'none';
  if (lWrap) lWrap.style.display = hasGoogle ? 'none'  : 'block';
  if (subtitle) subtitle.textContent = hasGoogle ? 'Acesse com sua conta Google' : 'Acesse com suas credenciais';
  if (!hasGoogle) setTimeout(function(){ var e=document.getElementById('lpLoginEmail'); if(e) e.focus(); }, 80);
}"""

c = c.replace(OLD_SHOW_LOGIN, NEW_SHOW_LOGIN, 1)
print("✓ showLoginModal atualizado")

# ──────────────────────────────────────────────────────────────────
# 8. Atualizar modal de Configurações: Sheets em vez de GAS URL
# ──────────────────────────────────────────────────────────────────
OLD_SETTINGS_MODAL = """<!-- ══ SETTINGS MODAL ══ -->
<div id="lpSettingsModal">
  <div class="lp-settings-box">
    <h2>⚙ Configurações</h2>
    <div class="lp-settings-field">
      <label><span class="lp-settings-indicator" id="connIndicator"></span>URL do GAS Web App (Google Sheets)</label>
      <input type="url" id="settingsWebAppUrl" placeholder="https://script.google.com/macros/s/.../exec">
      <small>
        Implante o <strong>backend.gs</strong> no <a href="https://script.google.com" target="_blank" style="color:var(--yellow)">Google Apps Script</a>
        como Web App (Execute as: Me · Who has access: Anyone) e cole a URL aqui.<br>
        Deixe em branco para usar armazenamento local (localStorage).
      </small>
    </div>
    <div id="settingsStatus" class="lp-settings-status"></div>
    <div class="lp-settings-row" style="margin-top:16px;">
      <button class="lp-settings-btn sec" onclick="testarConexao()">Testar conexão</button>
      <button class="lp-settings-btn" onclick="salvarSettings()">Salvar</button>
    </div>
    <div style="text-align:right;margin-top:12px;">
      <span onclick="hideSettingsModal()" style="font-size:11px;color:var(--text-muted);cursor:pointer;text-decoration:underline;">Fechar</span>
    </div>
  </div>
</div>"""

NEW_SETTINGS_MODAL = """<!-- ══ SETTINGS MODAL ══ -->
<div id="lpSettingsModal">
  <div class="lp-settings-box">
    <h2>⚙ Configurações — Google Sheets</h2>
    <div class="lp-settings-field">
      <label>Google OAuth Client ID</label>
      <input type="text" id="settingsClientId" placeholder="000000000000-xxxxxxxx.apps.googleusercontent.com">
      <small>Crie em <a href="https://console.cloud.google.com/apis/credentials" target="_blank" style="color:var(--yellow)">Google Cloud Console</a> → Credenciais → OAuth 2.0 Client ID (tipo: Web). Adicione sua URL do GitHub Pages como origem autorizada.</small>
    </div>
    <div class="lp-settings-field">
      <label>ID da Planilha</label>
      <input type="text" id="settingsSheetId" placeholder="1Foln_V3Pq0jqC7xDSNytYzMF_k3S2Amfdt6-U4ZgMxg">
      <small>Apenas o ID — parte entre <code style="color:var(--yellow)">/d/</code> e <code style="color:var(--yellow)">/edit</code> da URL.</small>
    </div>
    <div class="lp-settings-field">
      <label>Nomes das Abas (JSON)</label>
      <input type="text" id="settingsSheetNames" placeholder='{"selo":"SELOS","cracha":"CRACHAS",...}'>
      <small>Mapeamento tipo → nome da aba. Deixe em branco para usar os padrões do backend.gs.</small>
    </div>
    <div id="settingsStatus" class="lp-settings-status"></div>
    <div class="lp-settings-row" style="margin-top:16px;">
      <button class="lp-settings-btn sec" onclick="testarConexao()">Testar conexão</button>
      <button class="lp-settings-btn" onclick="salvarSettings()">Salvar</button>
    </div>
    <div style="text-align:right;margin-top:12px;">
      <span onclick="hideSettingsModal()" style="font-size:11px;color:var(--text-muted);cursor:pointer;text-decoration:underline;">Fechar</span>
    </div>
  </div>
</div>"""

c = c.replace(OLD_SETTINGS_MODAL, NEW_SETTINGS_MODAL, 1)
print("✓ Modal de configurações atualizado (Sheets API)")

# ──────────────────────────────────────────────────────────────────
# 9. Atualizar funções showSettingsModal / salvarSettings / testarConexao
# ──────────────────────────────────────────────────────────────────
OLD_SETTINGS_JS = """function showSettingsModal(){
  var url = (_lpConfig && _lpConfig.gasWebAppUrl) || localStorage.getItem('lp_webAppUrl') || '';
  document.getElementById('settingsWebAppUrl').value = url;
  _atualizarStatusConexao(url);
  document.getElementById('lpSettingsModal').classList.add('show');
}
function hideSettingsModal(){
  document.getElementById('lpSettingsModal').classList.remove('show');
}
function salvarSettings(){
  var url = document.getElementById('settingsWebAppUrl').value.trim();
  if(_lpConfig) _lpConfig.gasWebAppUrl = url;
  localStorage.setItem('lp_webAppUrl', url);
  _atualizarStatusConexao(url);
  hideSettingsModal();
  if(url) {
    showSuccess('URL salva! Recarregando dados...');
    setTimeout(function(){ location.reload(); }, 1200);
  }
}
function testarConexao(){
  var url = document.getElementById('settingsWebAppUrl').value.trim();
  if(!url){ document.getElementById('settingsStatus').className='lp-settings-status err'; document.getElementById('settingsStatus').textContent='⚠ Cole a URL do Web App primeiro.'; return; }
  var el = document.getElementById('settingsStatus');
  el.className='lp-settings-status ok'; el.textContent='⏳ Testando conexão...';
  fetch(url, {method:'POST', body: JSON.stringify({action:'lerUnidades'})})
    .then(function(r){ return r.json(); })
    .then(function(d){
      if(d && d.error){ el.className='lp-settings-status err'; el.textContent='✗ Erro da planilha: ' + d.error; }
      else { el.className='lp-settings-status ok'; el.textContent='✓ Conexão OK! ' + (Array.isArray(d) ? d.length + ' unidade(s) encontrada(s).' : 'Planilha respondeu.'); }
    })
    .catch(function(e){ el.className='lp-settings-status err'; el.textContent='✗ Falha de rede: ' + String(e) + ' — Verifique se o Web App está implantado como "Anyone".'; });
}
function _atualizarStatusConexao(url){
  var badge = document.getElementById('conexaoBadge');
  if(!badge) return;
  if(url){ badge.innerHTML='🟢 Sheets Conectado'; badge.style.color='var(--green)'; }
  else    { badge.innerHTML='🟡 Modo Local';      badge.style.color='var(--yellow)'; }
}"""

NEW_SETTINGS_JS = """function showSettingsModal(){
  document.getElementById('settingsClientId').value  = (_lpConfig && _lpConfig.googleClientId)  || localStorage.getItem('lp_googleClientId') || '';
  document.getElementById('settingsSheetId').value   = (_lpConfig && _lpConfig.spreadsheetId)   || localStorage.getItem('lp_spreadsheetId')  || '';
  var sn = (_lpConfig && _lpConfig.sheetNames) || null;
  document.getElementById('settingsSheetNames').value = sn ? JSON.stringify(sn) : '';
  document.getElementById('settingsStatus').className = 'lp-settings-status';
  _atualizarStatusConexao();
  document.getElementById('lpSettingsModal').classList.add('show');
}
function hideSettingsModal(){
  document.getElementById('lpSettingsModal').classList.remove('show');
}
function salvarSettings(){
  var cid = document.getElementById('settingsClientId').value.trim();
  var sid = document.getElementById('settingsSheetId').value.trim();
  var snRaw = document.getElementById('settingsSheetNames').value.trim();
  // Salva em localStorage (override ao config.json)
  if (cid) localStorage.setItem('lp_googleClientId', cid); else localStorage.removeItem('lp_googleClientId');
  if (sid) localStorage.setItem('lp_spreadsheetId',  sid); else localStorage.removeItem('lp_spreadsheetId');
  if (snRaw) { try { localStorage.setItem('lp_sheetNames', snRaw); } catch(e){} }
  // Aplica em _lpConfig
  if (!_lpConfig) _lpConfig = {};
  if (cid) _lpConfig.googleClientId = cid;
  if (sid) _lpConfig.spreadsheetId  = sid;
  if (snRaw) { try { _lpConfig.sheetNames = JSON.parse(snRaw); } catch(e){} }
  // Re-inicia token client com novo clientId
  _gToken = null;
  _tokenClient = null;
  _initTokenClient();
  _atualizarStatusConexao();
  hideSettingsModal();
  showSuccess('Configurações salvas! Faça login para ativar.');
}
function testarConexao(){
  var sid = document.getElementById('settingsSheetId').value.trim();
  var cid = document.getElementById('settingsClientId').value.trim();
  var el  = document.getElementById('settingsStatus');
  if (!cid || !sid) { el.className='lp-settings-status err'; el.textContent='⚠ Preencha Client ID e ID da Planilha primeiro.'; return; }
  el.className='lp-settings-status ok'; el.textContent='⏳ Autenticando com Google...';
  if (!_tokenClient) { _initTokenClient(); }
  if (!_tokenClient) { el.className='lp-settings-status err'; el.textContent='GIS não carregado. Aguarde e tente novamente.'; return; }
  _tokenClient.callback = function(resp) {
    if (resp.error) { el.className='lp-settings-status err'; el.textContent='✗ Auth falhou: ' + (resp.error_description||resp.error); return; }
    var tok = resp.access_token;
    el.textContent = '⏳ Lendo planilha...';
    fetch('https://sheets.googleapis.com/v4/spreadsheets/' + sid + '/values/UNIDADES', {
      headers: { Authorization: 'Bearer ' + tok }
    })
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.error) { el.className='lp-settings-status err'; el.textContent='✗ Erro Sheets: ' + d.error.message; }
      else { el.className='lp-settings-status ok'; el.textContent='✓ Planilha acessível! ' + ((d.values && d.values.length-1)||0) + ' unidade(s) na aba UNIDADES.'; }
    })
    .catch(function(e){ el.className='lp-settings-status err'; el.textContent='✗ Erro de rede: ' + String(e); });
  };
  _tokenClient.requestAccessToken({ prompt: 'select_account' });
}
function _atualizarStatusConexao(){
  var badge = document.getElementById('conexaoBadge');
  if(!badge) return;
  var sid = (_lpConfig && _lpConfig.spreadsheetId) || localStorage.getItem('lp_spreadsheetId');
  if(sid){ badge.innerHTML='🟢 Sheets Conectado'; badge.style.color='var(--green)'; }
  else   { badge.innerHTML='🟡 Modo Local';       badge.style.color='var(--yellow)'; }
}"""

c = c.replace(OLD_SETTINGS_JS, NEW_SETTINGS_JS, 1)
print("✓ Funções de configurações atualizadas")

# ──────────────────────────────────────────────────────────────────
# 10. Atualizar _atualizarStatusConexao no aplicarPermissoes override
# ──────────────────────────────────────────────────────────────────
OLD_STATUS_CALL = "    _atualizarStatusConexao((_lpConfig && _lpConfig.gasWebAppUrl) || localStorage.getItem('lp_webAppUrl') || '');"
NEW_STATUS_CALL = "    _atualizarStatusConexao();"
c = c.replace(OLD_STATUS_CALL, NEW_STATUS_CALL, 1)
print("✓ Chamada _atualizarStatusConexao corrigida")

# ──────────────────────────────────────────────────────────────────
# Escrever resultado
# ──────────────────────────────────────────────────────────────────
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(c)
print("\n✓ index.html salvo")
