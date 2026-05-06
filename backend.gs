// ════════════════════════════════════════════════════════════════
// LOSS PREVENTION — GAS Web App (backend de dados)
// ════════════════════════════════════════════════════════════════
//
// COMO IMPLANTAR:
//   1. Acesse script.google.com → Novo projeto
//   2. Cole este código
//   3. Altere SPREADSHEET_ID com o ID da sua planilha
//   4. Ajuste TIPO_SHEET conforme os nomes reais das suas abas
//   5. Implante → Web App
//        Execute as: Me
//        Who has access: Anyone
//   6. Copie a URL gerada e cole em config.json → "gasWebAppUrl"
//
// ID da planilha: está na URL
//   https://docs.google.com/spreadsheets/d/SEU_ID_AQUI/edit
// ════════════════════════════════════════════════════════════════

var SPREADSHEET_ID = 'COLE_O_ID_DA_SUA_PLANILHA_AQUI';

// Mapa tipo → nome da aba na planilha (ajuste conforme suas abas)
var TIPO_SHEET = {
  'selo':         'SELOS',
  'cracha':       'CRACHAS',
  'investigacao': 'INVESTIGACOES',
  'cadeado':      'CADEADOS',
  'cartao':       'CARTOES',
  'disciplinar':  'DISCIPLINAR',
  'ronda':        'RONDAS',
  'bau':          'BAU',
  'pacote':       'PACOTES',
  'lacre':        'LACRES',
  'acesso':       'ACESSOS'
};

// ── Ponto de entrada HTTP ────────────────────────────────────────
function doPost(e) {
  var result;
  try {
    var payload = JSON.parse(e.postData.contents);
    var action  = payload.action;

    if      (action === 'lerBase')           result = lerBase(payload.tipo, payload.unidades || []);
    else if (action === 'salvarRegistro')    result = salvarRegistro(payload.tipo, payload.dados);
    else if (action === 'atualizarRegistro') result = atualizarRegistro(payload.tipo, payload.updated);
    else if (action === 'lerUnidades')       result = lerUnidadesComCoordenadas();
    else                                     result = {error: 'action desconhecida: ' + action};
  } catch(err) {
    result = {error: err.toString()};
  }

  return ContentService
    .createTextOutput(JSON.stringify(result))
    .setMimeType(ContentService.MimeType.JSON);
}

// ── Lê registros de uma aba ──────────────────────────────────────
function lerBase(tipo, unidades) {
  var sheetName = TIPO_SHEET[tipo];
  if (!sheetName) return [];

  var ss    = SpreadsheetApp.openById(SPREADSHEET_ID);
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
      // Formata datas legíveis
      if (val instanceof Date) {
        obj[headers[j]] = Utilities.formatDate(val, Session.getScriptTimeZone(), 'dd/MM/yyyy');
      } else {
        obj[headers[j]] = val !== null && val !== undefined ? String(val) : '';
      }
      if ((headers[j] === 'ID' || headers[j] === 'id') && obj[headers[j]]) hasId = true;
    }
    if (hasId) records.push(obj);
  }

  // Filtra por unidade se informado
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
  var sheetName = TIPO_SHEET[tipo];
  if (!sheetName) return {error: 'tipo não mapeado: ' + tipo};

  var ss    = SpreadsheetApp.openById(SPREADSHEET_ID);
  var sheet = ss.getSheetByName(sheetName);

  // Cria aba se não existir
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
  }

  var existingData = sheet.getDataRange().getValues();
  var headers = existingData.length > 0 ? existingData[0].map(String) : [];

  // Gera ID sequencial
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

  // Monta o registro completo
  var record = {ID: id, DATA: d, HORA: h, STATUS: 'Pendente'};
  var keys   = Object.keys(dados);
  for (var k = 0; k < keys.length; k++) {
    record[keys[k]] = dados[keys[k]];
  }

  // Adiciona colunas novas que ainda não existem
  var allKeys  = Object.keys(record);
  var newKeys  = allKeys.filter(function(k){ return headers.indexOf(k) === -1; });

  if (headers.length === 0) {
    // Aba nova — define cabeçalhos
    headers = allKeys;
    sheet.appendRow(headers);
  } else if (newKeys.length > 0) {
    headers = headers.concat(newKeys);
    sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  }

  var row = headers.map(function(col){ return record[col] !== undefined ? record[col] : ''; });
  sheet.appendRow(row);

  return {id: id};
}

// ── Atualiza registro existente ──────────────────────────────────
function atualizarRegistro(tipo, updated) {
  var sheetName = TIPO_SHEET[tipo];
  if (!sheetName) return {error: 'tipo não mapeado: ' + tipo};

  var ss    = SpreadsheetApp.openById(SPREADSHEET_ID);
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) return {error: 'aba não encontrada: ' + sheetName};

  var data    = sheet.getDataRange().getValues();
  if (data.length < 2) return {error: 'aba vazia'};

  var headers = data[0].map(String);
  var idCol   = headers.indexOf('ID');
  if (idCol === -1) return {error: 'coluna ID não encontrada em ' + sheetName};

  var targetId = updated['ID'];

  for (var i = 1; i < data.length; i++) {
    if (String(data[i][idCol]) === targetId) {
      var row = headers.map(function(h, j) {
        return updated[h] !== undefined ? updated[h] : data[i][j];
      });
      sheet.getRange(i + 1, 1, 1, row.length).setValues([row]);
      return {ok: true};
    }
  }

  return {error: 'ID não encontrado: ' + targetId};
}

// ── Lê unidades com coordenadas (aba UNIDADES) ───────────────────
function lerUnidadesComCoordenadas() {
  var ss    = SpreadsheetApp.openById(SPREADSHEET_ID);
  var sheet = ss.getSheetByName('UNIDADES');
  if (!sheet) return [];

  var data = sheet.getDataRange().getValues();
  if (data.length < 2) return [];

  var headers   = data[0].map(String);
  var nomeIdx   = headers.indexOf('NOME');
  var latlngIdx = headers.indexOf('LATLONG');

  if (latlngIdx === -1) return [];
  if (nomeIdx   === -1) nomeIdx = 0;

  var result = [];
  for (var i = 1; i < data.length; i++) {
    var latlong = String(data[i][latlngIdx] || '').trim();
    if (!latlong) continue;
    var parts = latlong.split(',');
    if (parts.length < 2) continue;
    result.push({
      nome:     String(data[i][nomeIdx] || ''),
      unidade:  String(data[i][nomeIdx] || ''),
      lat:      parts[0].trim(),
      lng:      parts[1].trim()
    });
  }
  return result;
}
