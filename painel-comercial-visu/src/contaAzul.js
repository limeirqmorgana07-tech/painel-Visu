// Cliente da API v2 da Conta Azul: login OAuth 2.0, renovação de token,
// fila de chamadas (respeita o limite de ~50/min) e leitura de vendas e contas a receber.
import crypto from 'node:crypto';
import { config, redirectUri } from './config.js';
import { lerToken, salvarToken, apagarToken } from './tokenStore.js';

// ---------- OAuth ----------
// O "state" é assinado (não fica na memória), então continua válido mesmo se o
// servidor reiniciar entre o clique em "Conectar" e a volta da Conta Azul.
const assinarState = (base) => crypto.createHmac('sha256', config.segredoSessao).update(base).digest('hex').slice(0, 32);

function stateValido(state) {
  const [ts, rand, sig] = String(state || '').split('.');
  if (!ts || !rand || !sig) return false;
  const esperado = assinarState(`${ts}.${rand}`);
  if (sig.length !== esperado.length || !crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(esperado))) return false;
  return Date.now() - Number(ts) < 30 * 60 * 1000;
}

export function urlDeAutorizacao() {
  const base = `${Date.now()}.${crypto.randomBytes(8).toString('hex')}`;
  const state = `${base}.${assinarState(base)}`;
  const q = new URLSearchParams({
    response_type: 'code',
    client_id: config.clientId,
    redirect_uri: redirectUri(),
    state,
    scope: config.escopo,
  });
  return `${config.urlLogin}?${q}`;
}

function cabecalhoBasic() {
  return 'Basic ' + Buffer.from(`${config.clientId}:${config.clientSecret}`).toString('base64');
}

async function pedirToken(corpo) {
  const r = await fetch(config.urlToken, {
    method: 'POST',
    headers: { Authorization: cabecalhoBasic(), 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(corpo),
  });
  const texto = await r.text();
  if (!r.ok) throw new Error(`Conta Azul recusou o token (${r.status}): ${texto.slice(0, 300)}`);
  const j = JSON.parse(texto);
  return {
    access_token: j.access_token,
    refresh_token: j.refresh_token,
    expira_em: Date.now() + (Number(j.expires_in || 3600) - 120) * 1000, // renova 2 min antes
    conectado_em: new Date().toISOString(),
  };
}

export async function trocarCodigo(code, state) {
  if (!stateValido(state)) throw new Error('Link de autorização expirado ou inválido. Clique em "Conectar Conta Azul" de novo.');
  const t = await pedirToken({ grant_type: 'authorization_code', code, redirect_uri: redirectUri() });
  await salvarToken(t);
  return t;
}

let renovando = null;
async function tokenValido() {
  let t = await lerToken();
  if (!t?.refresh_token) throw new ErroNaoConectado();
  if (Date.now() < t.expira_em) return t.access_token;
  // evita duas renovações ao mesmo tempo (o refresh_token é de uso único)
  renovando ||= (async () => {
    try {
      const novo = await pedirToken({ grant_type: 'refresh_token', refresh_token: t.refresh_token });
      novo.refresh_token ||= t.refresh_token;
      novo.conectado_em = t.conectado_em;
      await salvarToken(novo);
      return novo;
    } finally {
      renovando = null;
    }
  })();
  t = await renovando;
  return t.access_token;
}

export class ErroNaoConectado extends Error {
  constructor() { super('Conta Azul não conectada'); this.naoConectado = true; }
}

export async function statusConexao() {
  const t = await lerToken();
  return { conectado: !!t?.refresh_token, conectado_em: t?.conectado_em || null };
}

export async function desconectar() { await apagarToken(); }

// ---------- Fila de chamadas ----------
let ultimaChamada = 0;
let fila = Promise.resolve();
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

function naFila(fn) {
  const p = fila.then(async () => {
    const espera = ultimaChamada + config.intervaloMs - Date.now();
    if (espera > 0) await esperar(espera);
    ultimaChamada = Date.now();
    return fn();
  });
  fila = p.catch(() => {});
  return p;
}

export async function get(caminho, params = {}, tentativa = 0) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') q.append(k, v);
  const url = `${config.urlApi}${caminho}${q.toString() ? '?' + q : ''}`;
  return naFila(async () => {
    const token = await tokenValido();
    const r = await fetch(url, { headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' } });
    if (r.status === 429 && tentativa < 4) {
      const s = Number(r.headers.get('retry-after')) || 2 ** (tentativa + 1);
      await esperar(s * 1000);
      return { __repetir: true };
    }
    if (r.status === 401 && tentativa < 1) {
      const t = await lerToken();
      if (t) await salvarToken({ ...t, expira_em: 0 }); // força renovação
      return { __repetir: true };
    }
    const texto = await r.text();
    if (!r.ok) throw new Error(`GET ${caminho} → ${r.status}: ${texto.slice(0, 300)}`);
    return texto ? JSON.parse(texto) : {};
  }).then((res) => (res?.__repetir ? get(caminho, params, tentativa + 1) : res));
}

// Lê todas as páginas de uma listagem
const listaDe = (r) => (Array.isArray(r) ? r : r?.itens || r?.items || r?.data || r?.vendas || r?.content || []);

async function todasAsPaginas(caminho, params, tamanho = 100, limitePaginas = 60) {
  const tudo = [];
  for (let pagina = 1; pagina <= limitePaginas; pagina++) {
    const r = await get(caminho, { ...params, pagina, tamanho_pagina: tamanho });
    const itens = listaDe(r);
    tudo.push(...itens);
    const total = Number(r?.total_itens ?? r?.totalItens ?? r?.total ?? NaN);
    if (itens.length < tamanho || (!Number.isNaN(total) && tudo.length >= total)) break;
  }
  return tudo;
}

// ---------- Normalização ----------
// A documentação pública não fixa todos os nomes de campos; por isso aceitamos variações
// e o endpoint /api/diagnostico mostra a estrutura real para ajuste fino.
const num = (v) => {
  if (v === null || v === undefined || v === '') return 0;
  if (typeof v === 'number') return v;
  if (typeof v === 'object') return num(v.valor ?? v.total ?? v.valor_liquido ?? v.valor_bruto);
  return Number(String(v).replace(/[^\d,.-]/g, '').replace(/\.(?=\d{3}(\D|$))/g, '').replace(',', '.')) || 0;
};
const semAcento = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toUpperCase().trim();
const nomeDe = (o) => (typeof o === 'string' ? o : o?.nome || o?.name || o?.razao_social || o?.nome_fantasia || '');

export function normalizarSituacao(s) {
  const x = semAcento(typeof s === 'object' ? s?.nome || s?.descricao || s?.codigo : s);
  if (x.includes('CANCEL')) return 'CANCELADO';
  if (x.includes('ORCAMENTO')) return 'ORCAMENTO';
  if (x.includes('FATUR')) return 'FATURADO';
  if (x.includes('APROV')) return 'APROVADO';
  if (x.includes('ANDAMENTO')) return 'EM_ANDAMENTO';
  return x || 'SEM_SITUACAO';
}

export function normalizarVenda(v) {
  return {
    id: v.id ?? v.uuid ?? null,
    numero: v.numero ?? v.number ?? null,
    data: String(v.data ?? v.data_venda ?? v.data_emissao ?? v.emission ?? v.data_criacao ?? '').slice(0, 10),
    cliente: nomeDe(v.cliente ?? v.customer) || v.cliente_nome || v.nome_cliente || 'Sem cliente',
    vendedor: nomeDe(v.vendedor ?? v.seller) || v.vendedor_nome || 'Sem vendedor',
    situacao: normalizarSituacao(v.situacao ?? v.status),
    total: num(v.total ?? v.valor_total ?? v.valor ?? v.composicao_valor ?? v.totais),
  };
}

export function normalizarItem(i) {
  const qtd = num(i.quantidade ?? i.quantity) || 1;
  const valorUnit = num(i.valor ?? i.valor_unitario ?? i.value);
  return {
    nome: nomeDe(i.produto ?? i.servico ?? i.item) || i.nome || i.descricao || 'Item sem nome',
    quantidade: qtd,
    total: num(i.valor_total ?? i.total) || qtd * valorUnit,
  };
}

export function normalizarReceber(r) {
  const status = semAcento(r.status ?? r.situacao?.nome ?? r.situacao);
  const valor = num(r.total ?? r.valor ?? r.valor_total ?? r.valor_composicao);
  const pago = num(r.pago ?? r.valor_pago);
  const aberto = r.nao_pago !== undefined ? num(r.nao_pago) : status.startsWith('RECEBIDO') && !status.includes('PARCIAL') ? 0 : Math.max(valor - pago, 0);
  return {
    id: r.id ?? null,
    descricao: r.descricao || '',
    cliente: nomeDe(r.cliente ?? r.contato ?? r.pessoa) || 'Sem cliente',
    vencimento: String(r.data_vencimento ?? r.vencimento ?? '').slice(0, 10),
    status,
    valor,
    pago,
    aberto,
  };
}

// ---------- Leituras ----------
export async function buscarVendas(inicio, fim) {
  const brutas = await todasAsPaginas('/v1/venda/busca', { data_inicio: inicio, data_fim: fim });
  return brutas.map(normalizarVenda);
}

export async function buscarItensDaVenda(id) {
  const r = await get(`/v1/venda/${id}/itens`);
  return listaDe(r).map(normalizarItem);
}

export async function buscarContasAReceber(de, ate) {
  const brutas = await todasAsPaginas('/v1/financeiro/eventos-financeiros/contas-a-receber/buscar', {
    data_vencimento_de: de,
    data_vencimento_ate: ate,
  });
  return brutas.map(normalizarReceber);
}

// Amostra crua (sem dados sensíveis de token) para conferir nomes de campos
export async function amostraBruta() {
  const hoje = new Date().toISOString().slice(0, 10);
  const inicio = new Date(Date.now() - 31 * 864e5).toISOString().slice(0, 10);
  const saida = {};
  for (const [nome, fn] of Object.entries({
    vendas: () => get('/v1/venda/busca', { data_inicio: inicio, data_fim: hoje, pagina: 1, tamanho_pagina: 2 }),
    contas_a_receber: () =>
      get('/v1/financeiro/eventos-financeiros/contas-a-receber/buscar', { data_vencimento_de: inicio, data_vencimento_ate: hoje, pagina: 1, tamanho_pagina: 2 }),
  })) {
    try { saida[nome] = await fn(); } catch (e) { saida[nome] = { erro: e.message }; }
  }
  const primeira = listaDe(saida.vendas)[0];
  if (primeira?.id) {
    try { saida.itens_da_primeira_venda = await get(`/v1/venda/${primeira.id}/itens`); } catch (e) { saida.itens_da_primeira_venda = { erro: e.message }; }
  }
  return saida;
}
