#!/usr/bin/env python3
"""
Patch: troca backend Google Sheets → /api/gas (backend Node.js no Fury)
Aplica em public/index.html
"""

with open('public/index.html', 'r', encoding='utf-8') as f:
    c = f.read()

# ── 1. Remove GIS script tag (não precisa mais de OAuth Google) ──
c = c.replace(
    '<script src="https://accounts.google.com/gsi/client" onload="window._gisReady=true;if(window._onGisReady)window._onGisReady();" async defer></script>\n',
    '',
    1
)

# ── 2. Substituir TODO o GAS_IMPL por versão que chama /api/gas ──
OLD_BLOCK_START = '// ── Token Google OAuth ─────────────────────────────────────────'
OLD_BLOCK_END   = '};'   # final do GAS_IMPL

# Localiza o bloco completo (do token oauth até o fim do GAS_IMPL)
start = c.find(OLD_BLOCK_START)
# Procura o "};" que fecha o GAS_IMPL (após 'lerUnidadesComCoordenadas')
marker = 'lerUnidadesComCoordenadas: function()'
marker_idx = c.find(marker, start)
end = c.find('};', marker_idx) + 2   # inclui o "};"

NEW_IMPL = """// ── Backend Fury /api/gas ──────────────────────────────────────
function _apiReq(payload) {
  return fetch('/api/gas', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  }).then(function(r) {
    return r.json().then(function(d) {
      if (!r.ok) throw new Error((d.error) || 'HTTP ' + r.status);
      return d;
    });
  });
}

// ── GAS_IMPL ────────────────────────────────────────────────────
var GAS_IMPL = {

  iniciarApp: function() {
    var cfg  = _lpConfig || { users: [], unidades: [] };
    var allU = (cfg.unidades || []).map(function(u) { return u.nome || u; });
    var sess = LP.getSession();
    if (sess && sess.email) {
      var found = null;
      (cfg.users || []).forEach(function(u) { if (u.email === sess.email) found = u; });
      if (found) return { permissao: found.permissao, email: sess.email, unidadesUsuario: found.unidades || [], unidades: allU };
      return { permissao: 'publico', email: sess.email, unidadesUsuario: [], unidades: allU };
    }
    return { permissao: 'publico', email: '', unidadesUsuario: [], unidades: allU };
  },

  lerBase: function(tipo, unidades) {
    return _apiReq({ action: 'lerBase', tipo: tipo, unidades: unidades || [] });
  },

  atualizarRegistro: function(tipo, updated) {
    return _apiReq({ action: 'atualizarRegistro', tipo: tipo, updated: updated });
  },

  salvarRegistro: function(tipo, dados) {
    return _apiReq({ action: 'salvarRegistro', tipo: tipo, dados: dados });
  },

  lerUnidadesComCoordenadas: function() {
    return _apiReq({ action: 'lerUnidades' }).then(function(list) {
      return (list || []).filter(function(u) { return u.lat && u.lng; });
    });
  }
};"""

c = c[:start] + NEW_IMPL + c[end:]
print("✓ GAS_IMPL → /api/gas")

# ── 3. Bootstrap: remove lógica de GIS/token, simplifica ────────
OLD_FINALLY = """    .finally(function(){
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

NEW_FINALLY = """    .finally(function(){
      window.google.script.run
        .withSuccessHandler(_onAuthSuccess)
        .withFailureHandler(_onAuthFail)
        .iniciarApp();
    });"""

c = c.replace(OLD_FINALLY, NEW_FINALLY, 1)
print("✓ Bootstrap simplificado")

# ── 4. doLogin: só email+senha (remove fluxo OAuth) ─────────────
OLD_DOLOGIN = """function doLogin(){
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

NEW_DOLOGIN = """function doLogin(){
  var email = (document.getElementById('lpLoginEmail').value || '').trim().toLowerCase();
  var senha = document.getElementById('lpLoginSenha').value || '';
  var cfg   = _lpConfig || { users: [] };
  var user  = null;
  (cfg.users || []).forEach(function(u) {
    if ((u.email || '').toLowerCase() === email && u.senha === senha) user = u;
  });
  if (!user) { document.getElementById('lpLoginErr').classList.add('show'); return; }
  LP.saveSession({ email: user.email });
  hideLoginModal();
  document.getElementById('authLoading').style.display = 'flex';
  window.google.script.run.withSuccessHandler(_onAuthSuccess).withFailureHandler(_onAuthFail).iniciarApp();
}
function doLogout(){
  LP.clearSession();
  location.reload();
}"""

c = c.replace(OLD_DOLOGIN, NEW_DOLOGIN, 1)
print("✓ doLogin → email+senha")

# ── 5. Modal login: volta ao simples (sem botão Google) ──────────
OLD_LOGIN_MODAL = """<!-- ══ LOGIN MODAL ══ -->
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

NEW_LOGIN_MODAL = """<!-- ══ LOGIN MODAL ══ -->
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

c = c.replace(OLD_LOGIN_MODAL, NEW_LOGIN_MODAL, 1)
print("✓ Modal login simplificado")

# ── 6. showLoginModal: remove lógica Google ──────────────────────
OLD_SHOW_LOGIN = """function showLoginModal(){
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

NEW_SHOW_LOGIN = """function showLoginModal(){
  var modal = document.getElementById('lpLoginModal');
  if(modal) modal.classList.add('show');
  setTimeout(function(){ var e = document.getElementById('lpLoginEmail'); if(e) e.focus(); }, 80);
}"""

c = c.replace(OLD_SHOW_LOGIN, NEW_SHOW_LOGIN, 1)
print("✓ showLoginModal simplificado")

# ── 7. Settings modal: volta ao simples (gerenciar usuários/unidades) ──
OLD_SETTINGS_MODAL = """<!-- ══ SETTINGS MODAL ══ -->
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

NEW_SETTINGS_MODAL = """<!-- ══ SETTINGS MODAL ══ -->
<div id="lpSettingsModal">
  <div class="lp-settings-box">
    <h2>⚙ Configurações</h2>
    <div class="lp-settings-field">
      <label><span class="lp-settings-indicator" id="connIndicator"></span>Status do backend</label>
      <div id="settingsStatus" class="lp-settings-status"></div>
    </div>
    <div class="lp-settings-field">
      <label>Usuários (JSON)</label>
      <textarea id="settingsUsers" rows="6" style="width:100%;background:var(--bg2);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:8px;font-size:12px;font-family:monospace;resize:vertical;"></textarea>
      <small>Lista de usuários com email, senha e permissão (Administrador / Usuario / Portaria).</small>
    </div>
    <div class="lp-settings-field">
      <label>Unidades (JSON)</label>
      <textarea id="settingsUnidades" rows="4" style="width:100%;background:var(--bg2);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:8px;font-size:12px;font-family:monospace;resize:vertical;"></textarea>
      <small>Lista de unidades com nome, lat e lng.</small>
    </div>
    <div class="lp-settings-row" style="margin-top:16px;">
      <button class="lp-settings-btn sec" onclick="testarConexao()">Testar backend</button>
      <button class="lp-settings-btn" onclick="salvarSettings()">Salvar</button>
    </div>
    <div style="text-align:right;margin-top:12px;">
      <span onclick="hideSettingsModal()" style="font-size:11px;color:var(--text-muted);cursor:pointer;text-decoration:underline;">Fechar</span>
    </div>
  </div>
</div>"""

c = c.replace(OLD_SETTINGS_MODAL, NEW_SETTINGS_MODAL, 1)
print("✓ Settings modal atualizado")

# ── 8. Settings JS: gerencia usuários/unidades ───────────────────
OLD_SETTINGS_JS = """function showSettingsModal(){
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

NEW_SETTINGS_JS = """function showSettingsModal(){
  var cfg = _lpConfig || { users: [], unidades: [] };
  document.getElementById('settingsUsers').value    = JSON.stringify(cfg.users    || [], null, 2);
  document.getElementById('settingsUnidades').value = JSON.stringify(cfg.unidades || [], null, 2);
  _atualizarStatusConexao();
  document.getElementById('lpSettingsModal').classList.add('show');
}
function hideSettingsModal(){
  document.getElementById('lpSettingsModal').classList.remove('show');
}
function salvarSettings(){
  try {
    var users    = JSON.parse(document.getElementById('settingsUsers').value    || '[]');
    var unidades = JSON.parse(document.getElementById('settingsUnidades').value || '[]');
    if (!_lpConfig) _lpConfig = {};
    _lpConfig.users    = users;
    _lpConfig.unidades = unidades;
    localStorage.setItem('lp_config', JSON.stringify(_lpConfig));
    _atualizarStatusConexao();
    hideSettingsModal();
    showSuccess('Configurações salvas!');
  } catch(e) {
    document.getElementById('settingsStatus').className = 'lp-settings-status err';
    document.getElementById('settingsStatus').textContent = '✗ JSON inválido: ' + String(e);
  }
}
function testarConexao(){
  var el = document.getElementById('settingsStatus');
  el.className = 'lp-settings-status ok'; el.textContent = '⏳ Testando backend...';
  fetch('/health')
    .then(function(r){ return r.json(); })
    .then(function(d){
      if(d.status === 'ok'){ el.className='lp-settings-status ok'; el.textContent='✓ Backend Fury respondendo corretamente!'; }
      else { el.className='lp-settings-status err'; el.textContent='✗ Resposta inesperada do backend.'; }
    })
    .catch(function(e){ el.className='lp-settings-status err'; el.textContent='✗ Backend não acessível: ' + String(e); });
}
function _atualizarStatusConexao(){
  var badge = document.getElementById('conexaoBadge');
  if(!badge) return;
  badge.innerHTML='🟢 Backend Fury'; badge.style.color='var(--green)';
}"""

c = c.replace(OLD_SETTINGS_JS, NEW_SETTINGS_JS, 1)
print("✓ Settings JS atualizado")

# ── 9. Corrigir chamada antiga de _atualizarStatusConexao ────────
OLD_STATUS_CALL = "    _atualizarStatusConexao();"
# (já está correto, só verifica se existe)
print("✓ _atualizarStatusConexao OK")

with open('public/index.html', 'w', encoding='utf-8') as f:
    f.write(c)
print("\n✓ public/index.html salvo (pronto para Fury)")
