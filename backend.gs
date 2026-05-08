// ════════════════════════════════════════════════════════════════
// LOSS PREVENTION — Google Apps Script
// ════════════════════════════════════════════════════════════════
//
// COMO IMPLANTAR:
//   1. Acesse script.google.com → cole este código no arquivo .gs
//   2. Crie um arquivo HTML chamado "Index" e cole o index.html
//   3. Implante → Web App
//        Execute as: Me
//        Who has access: Anyone with Google Account  (ou Anyone)
//   4. Autorize as permissões quando solicitado
//
// ABA de usuários → "USUARIOS"
//   Coluna A → EMAIL
//   Coluna B → PERMISSAO  (Administrador | Usuario | Portaria)
//   Coluna C → UNIDADE(S) (nomes separados por vírgula, ou "TODAS" / "*")
// ════════════════════════════════════════════════════════════════

var SS_ID = '1Foln_V3Pq0jqC7xDSNytYzMF_k3S2Amfdt6-U4ZgMxg';

var USUARIOS_SHEET = 'USUARIOS';

// Mapa tipo → nome real da aba na planilha
var ABA_MAP = {
  selo:         'SOLICITAÇÃO DE SELO',
  cracha:       'SOLICITAÇÃO DE CARTÃO',
  acesso:       'SOLICITAÇÃO DE ACESSO',
  investigacao: 'INVESTIGAÇÃO',
  cadeado:      'SOLICITAÇAO QUEBRA DE CADEADO',
  cartao:       'ESQUECIMENTO DE CARTÃO',
  disciplinar:  'MEDIDA DICIPLINAR',
  ronda:        'RONDAS',
  bau:          'REVISTA DE BAÚ',
  pacote:       'PACOTES NO CAD',
  lacre:        'YMS'
};

// ── Serve o HTML principal ───────────────────────────────────────
function doGet(e) {
  return HtmlService.createHtmlOutputFromFile('Index')
    .setTitle('Loss Prevention — Gestão')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

// ── Autenticação via planilha USUARIOS ──────────────────────────
function iniciarApp() {
  var email = '';
  try { email = Session.getActiveUser().getEmail(); } catch(e) {}
  if (!email || email === '') {
    try { email = Session.getEffectiveUser().getEmail(); } catch(e) {}
  }

  var unidades = lerUnidades();

  if (!email || email === '') {
    return { permissao: 'publico', email: '', unidadesUsuario: [], unidades: unidades };
  }

  return _buscarPermissoes(email, unidades);
}

function _buscarPermissoes(email, unidades) {
  var ss    = SpreadsheetApp.openById(SS_ID);
  var sheet = ss.getSheetByName(USUARIOS_SHEET);

  if (!sheet) {
    return { permissao: 'publico', email: email, unidadesUsuario: [], unidades: unidades };
  }

  var data = sheet.getDataRange().getValues();
  if (data.length < 2) {
    return { permissao: 'publico', email: email, unidadesUsuario: [], unidades: unidades };
  }

  var headers  = data[0].map(function(h){ return String(h).trim().toUpperCase(); });
  var emailIdx = headers.indexOf('EMAIL');
  var permIdx  = headers.indexOf('PERMISSAO');
  // Aceita tanto "UNIDADE" quanto "UNIDADES"
  var unidIdx  = headers.indexOf('UNIDADES');
  if (unidIdx === -1) unidIdx = headers.indexOf('UNIDADE');

  if (emailIdx === -1) emailIdx = 0;
  if (permIdx  === -1) permIdx  = 1;
  if (unidIdx  === -1) unidIdx  = 2;

  var emailLower = email.toLowerCase().trim();

  for (var i = 1; i < data.length; i++) {
    var rowEmail = String(data[i][emailIdx] || '').toLowerCase().trim();
    if (rowEmail !== emailLower) continue;

    var permissao = String(data[i][permIdx] || 'publico').trim();
    var rawUnid   = String(data[i][unidIdx] || '').trim();
    var unidadesUsuario;

    if (!rawUnid || rawUnid.toUpperCase() === 'TODAS' || rawUnid === '*') {
      unidadesUsuario = unidades;
    } else {
      unidadesUsuario = rawUnid.split(',').map(function(u){ return u.trim(); }).filter(Boolean);
    }

    return {
      permissao:       permissao,
      email:           email,
      unidadesUsuario: unidadesUsuario,
      unidades:        unidades
    };
  }

  // E-mail não encontrado → público
  return { permissao: 'publico', email: email, unidadesUsuario: [], unidades: unidades };
}

// ── Lê nomes de unidades (aba UNIDADES) ─────────────────────────
function lerUnidades() {
  var ss    = SpreadsheetApp.openById(SS_ID);
  var sheet = ss.getSheetByName('UNIDADES');
  if (!sheet) return [];

  var data = sheet.getDataRange().getValues();
  if (data.length < 2) return [];

  var headers = data[0].map(function(h){ return String(h).trim().toUpperCase(); });
  // Aceita "NOME" ou "UNIDADE"
  var colIdx = headers.indexOf('NOME');
  if (colIdx === -1) colIdx = headers.indexOf('UNIDADE');
  if (colIdx === -1) colIdx = 0;

  var result = [];
  for (var i = 1; i < data.length; i++) {
    var v = String(data[i][colIdx] || '').trim();
    if (v) result.push(v);
  }
  return result;
}

// ── Lê unidades com coordenadas (aba UNIDADES, coluna LATLONG) ──
function lerUnidadesComCoordenadas() {
  var ss    = SpreadsheetApp.openById(SS_ID);
  var sheet = ss.getSheetByName('UNIDADES');
  if (!sheet) return [];

  var data = sheet.getDataRange().getValues();
  if (data.length < 2) return [];

  var headers   = data[0].map(function(h){ return String(h).trim().toUpperCase(); });
  var nomeIdx   = headers.indexOf('NOME');
  if (nomeIdx === -1) nomeIdx = headers.indexOf('UNIDADE');
  if (nomeIdx === -1) nomeIdx = 0;
  var latlngIdx = headers.indexOf('LATLONG');
  if (latlngIdx === -1) return [];

  var result = [];
  for (var i = 1; i < data.length; i++) {
    var latlong = String(data[i][latlngIdx] || '').trim();
    if (!latlong) continue;
    var parts = latlong.split(',');
    if (parts.length < 2) continue;
    var nome = String(data[i][nomeIdx] || '');
    result.push({ nome: nome, unidade: nome, lat: parts[0].trim(), lng: parts[1].trim() });
  }
  return result;
}

// ── Lê registros de uma aba ──────────────────────────────────────
function lerBase(tipo, unidades) {
  var sheetName = ABA_MAP[tipo];
  if (!sheetName) return [];

  var ss    = SpreadsheetApp.openById(SS_ID);
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) return [];

  var data = sheet.getDataRange().getValues();
  if (data.length < 2) return [];

  var headers = data[0].map(String);
  var records = [];

  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    var obj = {};
    var hasId = false;
    for (var j = 0; j < headers.length; j++) {
      var val = row[j];
      if (val instanceof Date) {
        obj[headers[j]] = Utilities.formatDate(val, Session.getScriptTimeZone(), 'dd/MM/yyyy');
      } else {
        obj[headers[j]] = (val !== null && val !== undefined) ? String(val) : '';
      }
      if ((headers[j] === 'ID' || headers[j] === 'id') && obj[headers[j]]) hasId = true;
    }
    if (hasId) records.push(obj);
  }

  if (unidades && unidades.length > 0) {
    records = records.filter(function(r) {
      var u = r['UNIDADE'] || r['Unidade'] || '';
      return unidades.indexOf(u) !== -1;
    });
  }

  return records;
}

// ── Salva novo registro ──────────────────────────────────────────
function salvarRegistro(tipo, dados) {
  var sheetName = ABA_MAP[tipo];
  if (!sheetName) return { error: 'tipo não mapeado: ' + tipo };

  var ss    = SpreadsheetApp.openById(SS_ID);
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) sheet = ss.insertSheet(sheetName);

  var existingData = sheet.getDataRange().getValues();
  var headers = existingData.length > 0 ? existingData[0].map(String) : [];

  var pfxMap = {
    selo:'SEL', cracha:'CRA', investigacao:'INV', cadeado:'CAD',
    cartao:'CAR', disciplinar:'DIS', ronda:'RON', bau:'BAU',
    pacote:'PAC', lacre:'LAC', acesso:'ACE'
  };
  var pfx    = pfxMap[tipo] || tipo.substring(0, 3).toUpperCase();
  var rowCnt = existingData.length > 1 ? existingData.length - 1 : 0;
  var id     = pfx + '-' + String(rowCnt + 1).padStart(4, '0');

  var tz  = Session.getScriptTimeZone();
  var now = new Date();
  var d   = Utilities.formatDate(now, tz, 'dd/MM/yyyy');
  var h   = Utilities.formatDate(now, tz, 'HH:mm');

  var record = { ID: id, DATA: d, HORA: h, STATUS: 'Pendente' };
  var keys   = Object.keys(dados);
  for (var k = 0; k < keys.length; k++) {
    record[keys[k]] = dados[keys[k]];
  }

  var allKeys = Object.keys(record);
  var newKeys = allKeys.filter(function(k){ return headers.indexOf(k) === -1; });

  if (headers.length === 0) {
    headers = allKeys;
    sheet.appendRow(headers);
  } else if (newKeys.length > 0) {
    headers = headers.concat(newKeys);
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }

  var row = headers.map(function(col){ return record[col] !== undefined ? record[col] : ''; });
  sheet.appendRow(row);

  return { id: id };
}

// ── Atualiza registro existente ──────────────────────────────────
function atualizarRegistro(tipo, updated) {
  var sheetName = ABA_MAP[tipo];
  if (!sheetName) return { error: 'tipo não mapeado: ' + tipo };

  var ss    = SpreadsheetApp.openById(SS_ID);
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) return { error: 'aba não encontrada: ' + sheetName };

  var data    = sheet.getDataRange().getValues();
  if (data.length < 2) return { error: 'aba vazia' };

  var headers  = data[0].map(String);
  var idCol    = headers.indexOf('ID');
  if (idCol === -1) return { error: 'coluna ID não encontrada' };

  var targetId = updated['ID'];

  for (var i = 1; i < data.length; i++) {
    if (String(data[i][idCol]) === targetId) {
      var row = headers.map(function(h, j) {
        return updated[h] !== undefined ? updated[h] : data[i][j];
      });
      sheet.getRange(i + 1, 1, 1, row.length).setValues([row]);
      return { ok: true };
    }
  }

  return { error: 'ID não encontrado: ' + targetId };
}

// ── Retorna opções customizadas (setor / empresa / cargo) ────────
function getOpcoesCustom() {
  var props = PropertiesService.getScriptProperties();
  var raw   = props.getProperty('lp_opts');
  if (!raw) return { setor: [], empresa: [], cargo: [] };
  try { return JSON.parse(raw); } catch(e) { return { setor: [], empresa: [], cargo: [] }; }
}

// ── Salva nova opção customizada ─────────────────────────────────
function salvarOpcaoCustom(tipo, valor) {
  valor = String(valor).trim().toUpperCase();
  if (!valor) return { ok: false };
  var props = PropertiesService.getScriptProperties();
  var raw   = props.getProperty('lp_opts');
  var opts  = { setor: [], empresa: [], cargo: [] };
  try { if (raw) opts = JSON.parse(raw); } catch(e) {}
  if (!Array.isArray(opts[tipo])) opts[tipo] = [];
  if (opts[tipo].indexOf(valor) === -1) {
    opts[tipo].push(valor);
    opts[tipo].sort();
  }
  props.setProperty('lp_opts', JSON.stringify(opts));
  return { ok: true, valor: valor };
}
