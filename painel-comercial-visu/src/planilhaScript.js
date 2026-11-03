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
export const statusScript = () => ({ configurado: scriptConfigurado(), url: memo?.url || '', ligado_em: memo?.ligado_em || null, por: memo?.por || '', nome: memo?.nome || '' });

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

function saida(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
`;
}

export async function baixarPorScript(url = memo?.url, chave = memo?.chave) {
  if (!url || !chave) throw new Error('A planilha ainda não foi ligada pelo e-mail.');
  const r = await fetch(`${url}${url.includes('?') ? '&' : '?'}chave=${encodeURIComponent(chave)}`, { redirect: 'follow' });
  const txt = await r.text();
  let j; try { j = JSON.parse(txt); } catch { throw new Error(/<html/i.test(txt) ? 'O endereço devolveu uma página do Google em vez da planilha. Na implantação, "Quem pode acessar" precisa ser "Qualquer pessoa".' : `Resposta inesperada do script (${r.status}).`); }
  if (j.erro) throw new Error(j.erro === 'chave inválida' ? 'A chave do script não confere com a do painel. Copie o script de novo pelo painel e reimplante.' : `Script: ${j.erro}`);
  if (!j.base64) throw new Error('O script não devolveu a planilha.');
  return { nome: j.nome, alterado_em: j.alterado_em, bytes: Buffer.from(j.base64, 'base64') };
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
