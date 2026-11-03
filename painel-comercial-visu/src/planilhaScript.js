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
export const statusScript = () => ({ configurado: scriptConfigurado(), url: memo?.url || '', ligado_em: memo?.ligado_em || null, por: memo?.por || '', nome: memo?.nome || '',
  arquivo_id: memo?.arquivo_id || '', gravar: !!memo?.gravar, ultima_gravacao: memo?.ultima_gravacao || null });
export const arquivoScript = () => memo?.arquivo_id || '';
// a planilha mudou de endereço (ex.: o .xlsx foi convertido para Planilha Google): o script novo leva o novo ID
export async function definirArquivo(link) {
  await carregarScript();
  const id = (String(link || '').match(/\/d\/([\w-]{20,})/) || [])[1] || (/^[\w-]{20,}$/.test(String(link || '').trim()) ? String(link).trim() : '');
  if (!id) throw new Error('Cole o link da planilha (https://docs.google.com/spreadsheets/d/…).');
  memo = { ...memo, arquivo_id: id }; await salvarKV(CHAVE_KV, memo); return id;
}
export async function definirGravar(ativo) { await carregarScript(); memo = { ...memo, gravar: !!ativo }; await salvarKV(CHAVE_KV, memo); return memo.gravar; }
export async function marcarGravacao(r) { memo = { ...memo, ultima_gravacao: { em: new Date().toISOString(), ...r } }; await salvarKV(CHAVE_KV, memo).catch(() => {}); }

export function modeloScript(chave, arquivoId) {
  return `// Painel de Gestão Visu: entrega a planilha de vendas ao painel (só com a chave abaixo)
const ARQUIVO_ID = '${arquivoId}';
const CHAVE = '${chave}';

function doGet(e) {
  if (!e || !e.parameter || e.parameter.chave !== CHAVE) return saida({ erro: 'chave inválida' });
  const arquivo = DriveApp.getFileById(ARQUIVO_ID);
  let blob;
  if (arquivo.getMimeType() === MimeType.GOOGLE_SHEETS) {
    const url = 'https://docs.google.com/spreadsheets/d/' + ARQUIVO_ID + '/export?format=xlsx';
    blob = UrlFetchApp.fetch(url, { headers: { Authorization: 'Bearer ' + ScriptApp.getOAuthToken() } }).getBlob();
  } else {
    blob = arquivo.getBlob();
  }
  return saida({ nome: arquivo.getName(), alterado_em: arquivo.getLastUpdated().toISOString(), base64: Utilities.base64Encode(blob.getBytes()) });
}

// Rode esta função uma vez no editor (▶ Executar) para o Google pedir a autorização de leitura do Drive.
function autorizar() {
  const arquivo = DriveApp.getFileById(ARQUIVO_ID);
  UrlFetchApp.fetch('https://www.google.com', { muteHttpExceptions: true });
  try { SpreadsheetApp.openById(ARQUIVO_ID).getName(); } catch (e) { Logger.log('Atenção: o arquivo é .xlsx. Para o painel gravar os recebimentos, converta para Planilha Google (Arquivo > Salvar como Planilhas Google).'); }
  Logger.log('Autorizado. Planilha: ' + arquivo.getName() + ' (' + arquivo.getMimeType() + ')');
}

// Grava os recebimentos baixados na Conta Azul: valor em 1º/2º PAGAMENTO (com nota: data, banco e forma)
// e SIM em PEDIDO 100% PAGO. Só escreve em célula vazia. Precisa ser Planilha Google (não .xlsx).
function doPost(e) {
  let dados;
  try { dados = JSON.parse(e.postData.contents); } catch (x) { return saida({ erro: 'pedido inválido' }); }
  if (dados.chave !== CHAVE) return saida({ erro: 'chave inválida' });
  const arquivo = DriveApp.getFileById(ARQUIVO_ID);
  if (arquivo.getMimeType() !== MimeType.GOOGLE_SHEETS) return saida({ erro: 'xlsx', nome: arquivo.getName() });
  const ss = SpreadsheetApp.openById(ARQUIVO_ID);
  const sem = (s) => String(s == null ? '' : s).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[º°]/g, 'o').replace(/\s+/g, ' ').trim();
  let aba = null, cab = null, linhaCab = 0;
  for (const sh of ss.getSheets()) {
    if (/tratada|resultado|de.?para|^clientes$/.test(sem(sh.getName()))) continue;
    const ult = Math.max(1, sh.getLastColumn()), vals = sh.getRange(1, 1, Math.min(10, Math.max(1, sh.getLastRow())), ult).getValues();
    for (let i = 0; i < vals.length && !aba; i++) { const h = vals[i].map(sem); if (h.some((x) => x.indexOf('cod interno') === 0) && h.some((x) => x.indexOf('1o pagamento') === 0)) { aba = sh; cab = h; linhaCab = i + 1; } }
    if (aba) break;
  }
  if (!aba) return saida({ erro: 'Não achei a aba de vendas (colunas COD INTERNO e 1º PAGAMENTO).' });
  const col = (p) => cab.findIndex((x) => x.indexOf(p) === 0);
  const cCod = col('cod interno'), c1 = col('1o pagamento'), c2 = col('2o pagamento'), c100 = col('pedido 100% pago');
  const n = aba.getLastRow() - linhaCab; if (n < 1) return saida({ celulas: 0, pedidos: 0, aba: aba.getName() });
  const vals = aba.getRange(linhaCab + 1, 1, n, cab.length).getValues();
  const chave = (c) => String(c).replace(/\D/g, '').replace(/^0+/, '');
  const porCod = {};
  vals.forEach((r, i) => { const k = chave(r[cCod]); if (k) (porCod[k] = porCod[k] || []).push(i); });
  const vazio = (v) => v === '' || v === null || v === 0;
  let celulas = 0; const feitos = [];
  (dados.itens || []).forEach((it) => {
    const rows = porCod[chave(it.codigo)]; if (!rows) return;
    const r0 = rows[0]; let mexeu = false;
    const grava = (c, v, nota) => { if (c < 0 || v == null || v === '' || !vazio(vals[r0][c])) return; const cel = aba.getRange(linhaCab + 1 + r0, c + 1); cel.setValue(v); if (nota) cel.setNote(nota); celulas++; mexeu = true; };
    grava(c1, it.pag1, it.nota1); grava(c2, it.pag2, it.nota2);
    if (it.pago100 && c100 >= 0) rows.forEach((i) => { const a = sem(vals[i][c100]); if (a === '' || a === 'nao') { aba.getRange(linhaCab + 1 + i, c100 + 1).setValue('SIM'); celulas++; mexeu = true; } });
    if (mexeu) feitos.push(it.codigo);
  });
  return saida({ celulas: celulas, pedidos: feitos.length, codigos: feitos, aba: aba.getName() });
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
  return { nome: j.nome, alterado_em: j.alterado_em, bytes: Buffer.from(j.base64, 'base64') };
}

export async function enviarParaPlanilha(itens) {
  if (!scriptConfigurado()) throw new Error('A planilha ainda não foi ligada pelo e-mail.');
  const r = await fetch(memo.url, { method: 'POST', headers: { 'Content-Type': 'text/plain;charset=utf-8' }, body: JSON.stringify({ chave: memo.chave, itens }), redirect: 'follow' });
  const txt = await r.text();
  let j; try { j = JSON.parse(txt); } catch { throw new Error(/doPost|função|function/i.test(txt) ? 'O script na sua conta ainda é o antigo (só lê). Copie o script novo pelo painel, cole no Apps Script, rode "autorizar" e faça Implantar → Gerenciar implantações → lápis → Nova versão.' : 'O Google devolveu uma página em vez da resposta do script. Rode "autorizar" no editor e faça uma nova versão da implantação.'); }
  if (j.erro === 'xlsx') throw new Error(`O arquivo "${j.nome}" é .xlsx e o Google não deixa gravar nele. Abra a planilha → Arquivo → Salvar como Planilhas Google, passe a usar a nova planilha e cole o link dela em "Ligar pelo meu e-mail".`);
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
export async function desligarScript() { memo = { chave: memo?.chave }; await salvarKV(CHAVE_KV, memo); }
