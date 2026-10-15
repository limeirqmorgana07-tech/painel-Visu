// Conexão com o Google Drive para ler a planilha de vendas direto da conta de quem tem acesso a ela.
// O ADM clica em "Conectar Google", entra com a conta que abre a planilha (ex.: morgana.limeira@sejaexpertgestao.com)
// e autoriza só leitura. O painel guarda o refresh token no banco (DATABASE_URL) e baixa a planilha a cada atualização.
// Funciona com planilha do Google (exporta como .xlsx) e com arquivo .xlsx guardado no Drive.
import crypto from 'node:crypto';
import { config } from './config.js';
import { lerKV, salvarKV } from './tokenStore.js';

const env = process.env;
const CHAVE = 'google_token';
const ESCOPO = 'openid email https://www.googleapis.com/auth/drive.readonly';

export const credenciaisGoogle = () => !!(env.GOOGLE_CLIENT_ID && env.GOOGLE_CLIENT_SECRET);
export const redirectGoogle = () => `${config.urlPublica}/google/callback`;
export const idPlanilha = () => env.PLANILHA_ID || (String(config.planilhaLink).match(/\/d\/([\w-]+)/) || [])[1] || '';

let memo = null; // { refresh_token, email, conectado_em }
let acesso = { token: null, exp: 0 };
const estados = new Map();

export async function carregarGoogle() {
  if (memo) return memo;
  memo = (await lerKV(CHAVE).catch(() => null)) || null;
  return memo;
}
export const googleConectado = () => !!memo?.refresh_token;
export async function statusGoogle() {
  await carregarGoogle();
  return { conectado: googleConectado(), email: memo?.email || '', conectado_em: memo?.conectado_em || null, credenciais: credenciaisGoogle(), planilha_id: idPlanilha() };
}

export function urlAutorizacaoGoogle(dica) {
  const state = crypto.randomBytes(16).toString('hex');
  estados.set(state, Date.now());
  for (const [k, t] of estados) if (Date.now() - t > 15 * 60e3) estados.delete(k);
  const q = new URLSearchParams({
    client_id: env.GOOGLE_CLIENT_ID, redirect_uri: redirectGoogle(), response_type: 'code', scope: ESCOPO,
    access_type: 'offline', prompt: 'consent', include_granted_scopes: 'true', state,
  });
  if (dica) q.set('login_hint', dica);
  return `https://accounts.google.com/o/oauth2/v2/auth?${q}`;
}

async function token(params) {
  const r = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_id: env.GOOGLE_CLIENT_ID, client_secret: env.GOOGLE_CLIENT_SECRET, ...params }),
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`Google recusou a conexão: ${j.error_description || j.error || r.status}`);
  return j;
}

export async function trocarCodigoGoogle(code, state) {
  if (!estados.has(state)) throw new Error('A tentativa de conexão expirou. Clique em "Conectar Google" de novo.');
  estados.delete(state);
  const j = await token({ code, grant_type: 'authorization_code', redirect_uri: redirectGoogle() });
  if (!j.refresh_token) throw new Error('O Google não devolveu a autorização permanente. Remova o acesso do painel em myaccount.google.com/permissions e conecte de novo.');
  let email = '';
  try { email = JSON.parse(Buffer.from(String(j.id_token).split('.')[1], 'base64url').toString()).email || ''; } catch {}
  memo = { refresh_token: j.refresh_token, email, conectado_em: new Date().toISOString() };
  acesso = { token: j.access_token, exp: Date.now() + (j.expires_in - 60) * 1000 };
  await salvarKV(CHAVE, memo);
  return memo;
}

export async function desconectarGoogle() {
  memo = null; acesso = { token: null, exp: 0 };
  await salvarKV(CHAVE, null).catch(() => {});
}

async function tokenAcesso() {
  await carregarGoogle();
  if (!memo?.refresh_token) throw new Error('Google não conectado.');
  if (acesso.token && Date.now() < acesso.exp) return acesso.token;
  try {
    const j = await token({ refresh_token: memo.refresh_token, grant_type: 'refresh_token' });
    acesso = { token: j.access_token, exp: Date.now() + (j.expires_in - 60) * 1000 };
    return acesso.token;
  } catch (e) {
    if (/invalid_grant/i.test(e.message)) { await desconectarGoogle(); throw new Error('A autorização do Google expirou ou foi removida. Conecte o Google de novo.'); }
    throw e;
  }
}

// Baixa a planilha como .xlsx (Buffer) e devolve também o nome do arquivo
export async function baixarPlanilha(id = idPlanilha()) {
  const t = await tokenAcesso();
  const h = { Authorization: `Bearer ${t}` };
  const base = `https://www.googleapis.com/drive/v3/files/${encodeURIComponent(id)}`;
  const m = await fetch(`${base}?fields=name,mimeType,modifiedTime&supportsAllDrives=true`, { headers: h });
  const meta = await m.json().catch(() => ({}));
  if (!m.ok) throw new Error(m.status === 404 ? `A conta ${memo?.email || 'conectada'} não tem acesso à planilha. Conecte com a conta que abre a planilha.` : `Google Drive: ${meta.error?.message || m.status}`);
  const url = meta.mimeType === 'application/vnd.google-apps.spreadsheet'
    ? `${base}/export?mimeType=${encodeURIComponent('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}`
    : `${base}?alt=media&supportsAllDrives=true`;
  const r = await fetch(url, { headers: h });
  if (!r.ok) throw new Error(`Não consegui baixar a planilha do Drive (${r.status}).`);
  return { nome: meta.name, alterado_em: meta.modifiedTime, bytes: Buffer.from(await r.arrayBuffer()) };
}
