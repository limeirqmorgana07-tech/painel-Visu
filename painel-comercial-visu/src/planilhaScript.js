// Planilha de vendas lida pelo e-mail de quem tem acesso a ela, sem credenciais do Google Cloud.
// O ADM cola um pequeno script (Google Apps Script) na conta dele (ex.: morgana.limeira@sejaexpertgestao.com),
// publica como "App da Web" e cola o endereço no painel. O script devolve a planilha (.xlsx) só para quem
// tiver a chave gerada pelo painel. Assim o painel lê a planilha em tempo real a cada atualização.
import crypto from 'node:crypto';
import { lerKV, salvarKV } from './tokenStore.js';

const CHAVE_KV = 'planilha_script';
let memo = null; // { url, chave, ligado_em, por }

export async function carregarScript() { if (!memo) memo = (await lerKV(CHAVE_KV).catch(() => null)) || {}; return memo; }
export const scriptConfigurado = () => !!(memo?.url && memo?.chave);
export async function chaveScript() {
  await carregarScript();
  if (!memo.chave) { memo = { ...memo, chave: crypto.randomBytes(18).toString('base64url') }; await salvarKV(CHAVE_KV, memo); }
  return memo.chave;
}
export const ateScript = () => memo?.gravar_ate || '2026-10';
export async function definirAte(m) { await carregarScript(); if (/^\d{4}-\d{2}$/.test(String(m))) { memo = { ...memo, gravar_ate: m }; await salvarKV(CHAVE_KV, memo); } return ateScript(); }
export const statusScript = () => ({ gravar_ate: ateScript(), configurado: scriptConfigurado(), url: memo?.url || '', ligado_em: memo?.ligado_em || null, por: memo?.por || '', nome: memo?.nome || '',
  arquivo_id: memo?.arquivo_id || '', versao_script: memo?.versao_script || null, versao_atual: 45, gravar: memo?.gravar !== false, ultima_gravacao: memo?.ultima_gravacao || null, celulas_fila: (memo?.celulas_fila || []).length });
export const arquivoScript = () => memo?.arquivo_id || '';
// a planilha mudou de endereço (ex.: o .xlsx foi convertido para Planilha Google): o script novo leva o novo ID
export async function definirArquivo(link) {
  await carregarScript();
  const id = (String(link || '').match(/\/d\/([\w-]{20,})/) || [])[1] || (/^[\w-]{20,}$/.test(String(link || '').trim()) ? String(link).trim() : '');
  if (!id) throw new Error('Cole o link da planilha (https://docs.google.com/spreadsheets/d/…).');
  memo = { ...memo, arquivo_id: id }; await salvarKV(CHAVE_KV, memo); return id;
}
export async function definirGravar(ativo) { await carregarScript(); memo = { ...memo, gravar: !!ativo }; await salvarKV(CHAVE_KV, memo); return memo.gravar; }
// fila dos campos em branco preenchidos no painel, gravados na planilha junto com os recebimentos
export const filaCelulas = () => memo?.celulas_fila || [];
export async function adicionarCelulas(lista, u) {
  await carregarScript();
  const f = filaCelulas().filter((c) => !lista.some((x) => x.linha === c.linha && x.campo === c.campo));
  for (const x of lista) f.push({ id: crypto.randomBytes(6).toString('hex'), linha: Number(x.linha), campo: String(x.campo), valor: x.valor, cliente: String(x.cliente || ''), por: u?.nome || '', em: new Date().toISOString() });
  memo = { ...memo, celulas_fila: f.slice(-500) }; await salvarKV(CHAVE_KV, memo); return f;
}
export async function concluirCelulas(ids, pulados = []) {
  const feitos = new Set(ids || []), motivo = new Map((pulados || []).filter((p) => p.id).map((p) => [p.id, p.motivo]));
  // célula que não deu para gravar por um motivo definitivo (cliente mudou, linha sumiu) sai da fila e fica no histórico
  const fim = (filaCelulas()).filter((c) => feitos.has(c.id) || motivo.has(c.id));
  memo = { ...memo, celulas_fila: filaCelulas().filter((c) => !feitos.has(c.id) && !motivo.has(c.id)), celulas_hist: [...fim.map((c) => ({ ...c, ok: feitos.has(c.id) && !motivo.has(c.id), motivo: motivo.get(c.id) || '', gravado_em: new Date().toISOString() })), ...(memo?.celulas_hist || [])].slice(0, 300) };
  await salvarKV(CHAVE_KV, memo);
}
export const historicoCelulas = () => memo?.celulas_hist || [];
export async function marcarGravacao(r) { memo = { ...memo, ultima_gravacao: { em: new Date().toISOString(), ...r } }; await salvarKV(CHAVE_KV, memo).catch(() => {}); }

export function modeloScript(chave, arquivoId) {
  return `// Painel de Gestão Visu: entrega a planilha de vendas ao painel (só com a chave abaixo)
const ARQUIVO_ID = '${arquivoId}';
const CHAVE = '${chave}';

const VERSAO_SCRIPT = 45;
function doGet(e) {
  if (!e || !e.parameter || e.parameter.chave !== CHAVE) return saida({ erro: 'chave inválida' });
  const arquivo = DriveApp.getFileById(ARQUIVO_ID);
  if (e.parameter.info) return saida({ versao: VERSAO_SCRIPT, nome: arquivo.getName(), tipo: arquivo.getMimeType() });
  let blob;
  if (arquivo.getMimeType() === MimeType.GOOGLE_SHEETS) {
    const url = 'https://docs.google.com/spreadsheets/d/' + ARQUIVO_ID + '/export?format=xlsx';
    blob = UrlFetchApp.fetch(url, { headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() } }).getBlob();
  } else {
    blob = arquivo.getBlob();
  }
  return saida({ versao: VERSAO_SCRIPT, nome: arquivo.getName(), alterado_em: arquivo.getLastUpdated().toISOString(), base64: Utilities.base64Encode(blob.getBytes()) });
}

// Rode esta função uma vez no editor (▶ Executar) para o Google pedir a autorização de leitura do Drive.
function autorizar() {
  const arquivo = DriveApp.getFileById(ARQUIVO_ID);
  UrlFetchApp.fetch('https://www.google.com', { muteHttpExceptions: true });
  try { SpreadsheetApp.openById(ARQUIVO_ID).getName(); } catch (e) { /* .xlsx: o painel grava por uma cópia temporária */ }
  LockService.getScriptLock();
  ScriptApp.getOAuthToken();
  Logger.log('Autorizado. Planilha: ' + arquivo.getName() + ' (' + arquivo.getMimeType() + ')');
}

// Grava os recebimentos baixados na Conta Azul: valor em 1º/2º PAGAMENTO (com nota: data, banco e forma),
// FORMA DE PAGAMENTO vazia e SIM em PEDIDO 100% PAGO. Só escreve em célula vazia.
// Se o arquivo for .xlsx: faz uma cópia temporária em Planilha Google, preenche, e salva por cima do mesmo arquivo
// (mesmo nome e link). Só grava se ninguém mexeu na planilha nos últimos 15 minutos e guarda a versão anterior.
const MINUTOS_SEM_USO = 15;
function doPost(e) {
  // qualquer erro volta como texto para o painel mostrar (antes o Google devolvia uma página de erro)
  try { return gravar(e); } catch (x) { return saida({ erro: 'Erro no script do Google: ' + (x && x.message ? x.message : String(x)) + (x && x.stack ? ' · ' + String(x.stack).split('\\n').slice(0, 2).join(' ') : ''), versao: VERSAO_SCRIPT }); }
}
function gravar(e) {
  let dados;
  try { dados = JSON.parse(e.postData.contents); } catch (x) { return saida({ erro: 'pedido inválido' }); }
  if (dados.chave !== CHAVE) return saida({ erro: 'chave inválida' });
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(30000)) return saida({ adiado: true, motivo: 'outra gravação em andamento' });
  try {
    const arquivo = DriveApp.getFileById(ARQUIVO_ID);
    const editadoEm = arquivo.getLastUpdated().getTime(), parado = (Date.now() - editadoEm) / 60000;
    if (!dados.forcar && parado < MINUTOS_SEM_USO) return saida({ adiado: true, motivo: 'a planilha foi editada há ' + Math.floor(parado) + ' min', editado_em: new Date(editadoEm).toISOString() });
    if (arquivo.getMimeType() === MimeType.GOOGLE_SHEETS) return saida(aplicar(SpreadsheetApp.openById(ARQUIVO_ID), dados.itens || [], dados.celulas || []));
    // .xlsx: cópia temporária convertida → preenche → volta a ser .xlsx no mesmo arquivo
    const token = ScriptApp.getOAuthToken(), h = { Authorization: 'Bearer ' + token };
    const meta = JSON.parse(UrlFetchApp.fetch('https://www.googleapis.com/drive/v3/files/' + ARQUIVO_ID + '?fields=headRevisionId,mimeType&supportsAllDrives=true', { headers: h }).getContentText());
    const copia = JSON.parse(UrlFetchApp.fetch('https://www.googleapis.com/drive/v3/files/' + ARQUIVO_ID + '/copy?supportsAllDrives=true', { method: 'post', headers: h, contentType: 'application/json',
      payload: JSON.stringify({ name: 'temporário painel Visu (pode apagar)', mimeType: 'application/vnd.google-apps.spreadsheet' }) }).getContentText());
    let r;
    try {
      r = aplicar(SpreadsheetApp.openById(copia.id), dados.itens || [], dados.celulas || []);
      if (r.celulas) {
        SpreadsheetApp.flush();
        if (DriveApp.getFileById(ARQUIVO_ID).getLastUpdated().getTime() !== editadoEm) { r = { adiado: true, motivo: 'alguém editou a planilha durante a gravação; tento de novo depois' }; }
        else {
          const xlsx = UrlFetchApp.fetch('https://docs.google.com/spreadsheets/d/' + copia.id + '/export?format=xlsx', { headers: h }).getBlob();
          // guarda para sempre a versão anterior (Arquivo > Histórico de versões > Gerenciar versões)
          if (meta.headRevisionId) UrlFetchApp.fetch('https://www.googleapis.com/drive/v3/files/' + ARQUIVO_ID + '/revisions/' + meta.headRevisionId, { method: 'patch', headers: h, contentType: 'application/json', payload: JSON.stringify({ keepForever: true }), muteHttpExceptions: true });
          UrlFetchApp.fetch('https://www.googleapis.com/upload/drive/v3/files/' + ARQUIVO_ID + '?uploadType=media&supportsAllDrives=true', { method: 'patch', headers: h, contentType: meta.mimeType || 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', payload: xlsx.getBytes() });
          r.versao_anterior = meta.headRevisionId || '';
        }
      }
    } finally { DriveApp.getFileById(copia.id).setTrashed(true); }
    return saida(r);
  } finally { lock.releaseLock(); }
}

function aplicar(ss, itens, celulasPedidas) {
  const sem = (s) => String(s == null ? '' : s).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().replace(/[º°]/g, 'o').replace(/\\s+/g, ' ').trim();
  let aba = null, cab = null, linhaCab = 0;
  for (const sh of ss.getSheets()) {
    if (/tratada|resultado|de.?para|^clientes$/.test(sem(sh.getName()))) continue;
    const ult = Math.max(1, sh.getLastColumn()), vals = sh.getRange(1, 1, Math.min(10, Math.max(1, sh.getLastRow())), ult).getValues();
    for (let i = 0; i < vals.length && !aba; i++) { const hh = vals[i].map(sem); if (hh.some((x) => x.indexOf('cod interno') === 0) && hh.some((x) => x.indexOf('1o pagamento') === 0)) { aba = sh; cab = hh; linhaCab = i + 1; } }
    if (aba) break;
  }
  if (!aba) return { erro: 'Não achei a aba de vendas (colunas COD INTERNO e 1º PAGAMENTO).' };
  const col = (p) => cab.findIndex((x) => x.indexOf(p) === 0);
  const cCod = col('cod interno'), c1 = col('1o pagamento'), c2 = col('2o pagamento'), c100 = col('pedido 100% pago'), cFp = col('forma de pagamento');
  const n = aba.getLastRow() - linhaCab; if (n < 1) return { celulas: 0, pedidos: 0, aba: aba.getName() };
  const faixa = aba.getRange(linhaCab + 1, 1, n, cab.length), vals = faixa.getValues(), formulas = faixa.getFormulas();
  const chave = (c) => String(c).replace(/\\D/g, '').replace(/^0+/, '');
  const porCod = {};
  vals.forEach((r, i) => { const k = chave(r[cCod]); if (k) (porCod[k] = porCod[k] || []).push(i); });
  const vazio = (v) => v === '' || v === null || v === 0;
  let celulas = 0; const feitos = [], pulados = [];
  itens.forEach((it) => {
    const rows = porCod[chave(it.codigo)]; if (!rows) { pulados.push({ codigo: it.codigo, motivo: 'código não encontrado na aba' }); return; }
    const r0 = rows[0]; let mexeu = false;
    // nunca escreve por cima de fórmula nem de valor já digitado (e conta o motivo, para o painel mostrar)
    const grava = (c, v, nota, rot) => { if (c < 0 || v == null || v === '') return;
      if (formulas[r0][c]) { pulados.push({ codigo: it.codigo, linha: linhaCab + 1 + r0, campo: rot, motivo: 'célula com fórmula' }); return; }
      if (!vazio(vals[r0][c])) { pulados.push({ codigo: it.codigo, linha: linhaCab + 1 + r0, campo: rot, motivo: 'já tem valor' }); return; }
      const cel = aba.getRange(linhaCab + 1 + r0, c + 1); cel.setValue(v); if (nota) cel.setNote(nota); celulas++; mexeu = true; };
    grava(c1, it.pag1, it.nota1, '1º pagamento'); grava(c2, it.pag2, it.nota2, '2º pagamento'); grava(cFp, it.forma, '', 'forma de pagamento');
    if (it.pago100 && c100 >= 0) rows.forEach((i) => { const a = sem(vals[i][c100]); if ((a === '' || a === 'nao') && !formulas[i][c100]) { const cel = aba.getRange(linhaCab + 1 + i, c100 + 1); cel.setValue('SIM'); if (i === r0 && it.nota100) cel.setNote(it.nota100); celulas++; mexeu = true; } });
    if (mexeu) feitos.push(it.codigo);
  });
  // campos em branco preenchidos no painel (Qualidade dos dados): confere o cliente da linha antes de escrever
  const COLS = { data: 'data da venda', codigo: 'cod interno', vendedor: 'vendedor', tipo_venda: 'tipo de venda', novo_recompra: 'cliente novo', tipo_produto: 'tipo de produto', material: 'material', cor: 'cor', quantidade: 'quantidade', forma_pagamento: 'forma de pagamento', prazo_entrega: 'prazo de entrega' };
  const cCli = col('cliente'), celFeitas = [];
  (celulasPedidas || []).forEach((c) => {
    const i = Number(c.linha) - linhaCab - 1, cc = COLS[c.campo] ? col(COLS[c.campo]) : -1;
    if (i < 0 || i >= n || cc < 0) { pulados.push({ id: c.id, linha: c.linha, campo: c.campo, motivo: 'linha ou coluna não encontrada' }); return; }
    const a = sem(vals[i][cCli]).slice(0, 14), b = sem(c.cliente).slice(0, 14);
    if (!a || (a.indexOf(b) !== 0 && b.indexOf(a) !== 0)) { pulados.push({ id: c.id, linha: c.linha, campo: c.campo, motivo: 'o cliente dessa linha mudou (' + vals[i][cCli] + ')' }); return; }
    if (formulas[i][cc] || !vazio(vals[i][cc])) { pulados.push({ id: c.id, linha: c.linha, campo: c.campo, motivo: 'a célula já foi preenchida' }); celFeitas.push(c.id); return; }
    const cel = aba.getRange(linhaCab + 1 + i, cc + 1);
    let v = c.valor;
    if ((c.campo === 'data' || c.campo === 'prazo_entrega') && /^\\d{4}-\\d{2}-\\d{2}$/.test(v)) v = new Date(v + 'T12:00:00');
    else if (c.campo === 'quantidade') v = Number(v);
    else { const dv = cel.getDataValidation(); if (dv && dv.getCriteriaType() === SpreadsheetApp.DataValidationCriteria.VALUE_IN_LIST) { const ok = (dv.getCriteriaValues()[0] || []).filter((o) => sem(o) === sem(v))[0]; if (ok) v = ok; } }
    cel.setValue(v); celulas++; celFeitas.push(c.id);
  });
  return { versao: VERSAO_SCRIPT, celulas: celulas, pedidos: feitos.length, codigos: feitos, celulas_feitas: celFeitas, pulados: pulados.slice(0, 200), aba: aba.getName() };
}

function saida(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
`;
}

export async function baixarPorScript(url = memo?.url, chave = memo?.chave) {
  if (!url || !chave) throw new Error('A planilha ainda não foi ligada pelo e-mail.');
  const r = await fetch(`${url}${url.includes('?') ? '&' : '?'}chave=${encodeURIComponent(chave)}`, { redirect: 'follow' });
  const txt = await r.text();
  let j; try { j = JSON.parse(txt); } catch {
    if (!/<html/i.test(txt)) throw new Error(`Resposta inesperada do script (${r.status}).`);
    const t = txt.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ');
    if (/autoriza|authoriz|permiss/i.test(t) && !/sign in|fazer login|entrar/i.test(t)) throw new Error('O script ainda não foi autorizado a ler o Drive. No editor do Apps Script, escolha a função "autorizar" (ou doGet) ao lado de ▶ Executar, clique em Executar e permita o acesso. Depois: Implantar → Gerenciar implantações → lápis → Versão: Nova versão → Implantar, e teste de novo.');
    if (/sign in|fazer login|entrar|login/i.test(t)) throw new Error('O Google pediu login: na implantação, "Quem pode acessar" precisa ser "Qualquer pessoa" (não "Qualquer pessoa com Conta do Google"). Ajuste em Implantar → Gerenciar implantações → lápis.');
    throw new Error('O Google devolveu uma página de erro em vez da planilha. Quase sempre falta autorizar o script: no editor, rode ▶ Executar uma vez (função "autorizar" ou doGet) e permita o acesso; depois Implantar → Gerenciar implantações → lápis → Nova versão → Implantar. Confira também se "Quem pode acessar" está como "Qualquer pessoa".');
  }
  if (j.erro) throw new Error(j.erro === 'chave inválida' ? 'A chave do script não confere com a do painel. Copie o script de novo pelo painel e reimplante.' : `Script: ${j.erro}`);
  if (!j.base64) throw new Error('O script não devolveu a planilha.');
  if (memo && url === memo.url) memo.versao_script = j.versao || null;
  return { nome: j.nome, alterado_em: j.alterado_em, bytes: Buffer.from(j.base64, 'base64') };
}

export async function enviarParaPlanilha(itens, forcar = false) {
  if (!scriptConfigurado()) throw new Error('A planilha ainda não foi ligada pelo e-mail.');
  const r = await fetch(memo.url, { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify({ chave: memo.chave, itens, celulas: filaCelulas(), forcar }), redirect: 'follow' });
  const txt = await r.text();
  let j; try { j = JSON.parse(txt); } catch {
    // página de erro do Google: mostra o que ela diz (antes qualquer página era tratada como "script antigo")
    const t = txt.replace(/<script[\s\S]*?<\/script>|<style[\s\S]*?<\/style>/gi, ' ').replace(/<[^>]+>/g, ' ').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
    if (/(function|função)[^.]{0,40}(not found|não encontrada)[^.]{0,20}doPost|doPost[^.]{0,40}(not found|não encontrad)/i.test(t)) throw new Error('A implantação no Google ainda é a antiga (sem gravação). No Apps Script: Implantar → Gerenciar implantações → lápis → Versão: Nova versão → Implantar. Só salvar o código não basta.');
    if (/autoriza|authoriz|permiss/i.test(t)) throw new Error('O Google pede autorização de novo: no editor do Apps Script, escolha a função "autorizar", clique ▶ Executar e permita. Depois Implantar → Gerenciar implantações → lápis → Nova versão.');
    throw new Error('O Google devolveu um erro em vez da resposta do script: "' + t.slice(0, 260) + '". Se o script foi atualizado, confira se foi feita uma Nova versão da implantação.');
  }
  if (j.versao) memo.versao_script = j.versao;
  if (j.erro) throw new Error(j.erro === 'chave inválida' ? 'A chave do script não confere com a do painel. Copie o script de novo pelo painel e reimplante.' : j.erro);
  return j;
}

export async function ligarScript(url, usuario) {
  url = String(url || '').trim();
  if (!/^https:\/\/script\.google(usercontent)?\.com\//.test(url)) throw new Error('Cole o endereço do App da Web (começa com https://script.google.com/macros/s/ e termina com /exec).');
  const chave = await chaveScript();
  const arq = await baixarPorScript(url, chave); // testa antes de salvar
  memo = { ...memo, url, chave, ligado_em: new Date().toISOString(), por: usuario?.nome || '', nome: arq.nome };
  await salvarKV(CHAVE_KV, memo);
  return arq;
}
// desligar não apaga as escolhas (gravar sozinho, até qual mês, arquivo): antes, religar a planilha desligava a gravação
export async function desligarScript() { memo = { chave: memo?.chave, gravar: memo?.gravar, celulas_fila: memo?.celulas_fila, celulas_hist: memo?.celulas_hist, gravar_ate: memo?.gravar_ate, arquivo_id: memo?.arquivo_id, ultima_gravacao: memo?.ultima_gravacao }; await salvarKV(CHAVE_KV, memo); }
