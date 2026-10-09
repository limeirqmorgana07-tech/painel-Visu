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
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue;
    if (Array.isArray(v)) v.forEach((x) => q.append(k, x));
    else q.append(k, v);
  }
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

// tamanho_pagina só aceita 10, 20, 50, 100, 200, 500 ou 1000 (documentação da API v2)
async function todasAsPaginas(caminho, params, tamanho = 500, limitePaginas = 80) {
  const tudo = [];
  let ultimo = null;
  for (let pagina = 1; pagina <= limitePaginas; pagina++) {
    const r = await get(caminho, { ...params, pagina, tamanho_pagina: tamanho });
    const itens = listaDe(r);
    if (pagina === 1) ultimo = r;
    tudo.push(...itens);
    const total = Number(r?.total_itens ?? r?.itens_totais ?? NaN);
    if (!itens.length) break;
    if (!Number.isNaN(total) ? tudo.length >= total : itens.length < tamanho) break;
  }
  todasAsPaginas.ultimaResposta = ultimo;
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

// Situações da API: Aprovado, Faturado, Cancelado, Em andamento / Esperando aprovação, Orçamento...
// Atenção: "Esperando aprovação" contém "APROV" e NÃO é venda aprovada.
export function normalizarSituacao(s) {
  const x = semAcento(typeof s === 'object' ? s?.nome || s?.descricao || s?.codigo : s).replace(/\s+/g, '_');
  if (x.includes('CANCEL') || x.includes('RECUSAD')) return 'CANCELADO';
  if (x.includes('ESPERANDO') || x.includes('PENDENTE') || x.includes('ANDAMENTO') || x.includes('REVISAO') || x.includes('INCOMPLET')) return 'EM_ANDAMENTO';
  if (x.includes('ORCAMENTO') && !x.includes('ACEITO')) return 'ORCAMENTO';
  if (x.includes('FATUR')) return 'FATURADO';
  if (x.includes('APROV') || x.includes('ACEITO') || x === 'VENDA') return 'APROVADO';
  return x || 'SEM_SITUACAO';
}

export function normalizarVenda(v) {
  return {
    id: v.id ?? v.uuid ?? null,
    numero: v.numero ?? v.number ?? null,
    data: String(v.data ?? v.data_venda ?? v.data_emissao ?? v.criado_em ?? '').slice(0, 10),
    criado_em: String(v.criado_em ?? '').slice(0, 10),
    versao: v.versao ?? null,
    origem: v.origem ?? '',
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
    nome: i.nome || nomeDe(i.produto ?? i.servico ?? i.item) || i.descricao || 'Item sem nome',
    descricao: i.descricao || '',
    tipo: i.tipo || '',
    quantidade: qtd,
    total: num(i.valor_total ?? i.total) || qtd * valorUnit,
    custo: num(i.custo) * qtd,
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
// data_inicio/data_fim filtram pela data de EMISSÃO; o painel usa a data da venda (campo "data").
export async function buscarVendas(inicio, fim, extra = {}) {
  const brutas = await todasAsPaginas('/v1/venda/busca', { data_inicio: inicio, data_fim: fim, ...extra });
  return brutas.map(normalizarVenda);
}

// A listagem de vendas não traz o vendedor. Buscamos os vendedores e, para cada um, as vendas dele.
export async function buscarVendedores() {
  const r = await get('/v1/venda/vendedores');
  return listaDe(r).map((v) => ({ id: v.id, nome: v.nome || 'Sem nome' }));
}

export async function vendedorPorVenda(inicio, fim) {
  const mapa = new Map();
  const vendedores = await buscarVendedores();
  for (const vend of vendedores) {
    const vs = await todasAsPaginas('/v1/venda/busca', { data_inicio: inicio, data_fim: fim, ids_vendedores: [vend.id] });
    vs.forEach((v) => mapa.set(v.id, vend.nome));
  }
  return { mapa, vendedores };
}

export async function buscarItensDaVenda(id) {
  const r = await get(`/v1/venda/${id}/itens`, { pagina: 1, tamanho_pagina: 100 });
  return listaDe(r).map(normalizarItem);
}

// ---------- Financeiro ----------
const CAMINHO_PARCELAS = {
  receber: '/v1/financeiro/eventos-financeiros/contas-a-receber/buscar',
  pagar: '/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar',
};

export function normalizarParcela(p, tipo) {
  const status = semAcento(p.status_traduzido || p.status);
  const total = num(p.total ?? p.valor);
  const pago = num(p.pago);
  return {
    tipo,
    id: p.id,
    descricao: p.descricao || '',
    vencimento: String(p.data_vencimento || '').slice(0, 10),
    competencia: String(p.data_competencia || '').slice(0, 10),
    status,
    total,
    pago,
    aberto: p.nao_pago !== undefined ? num(p.nao_pago) : Math.max(total - pago, 0),
    categorias: (p.categorias || []).map((c) => ({ id: c.id, nome: c.nome })),
    centros: (p.centros_custo || []).map((c) => c.nome),
    pessoa: nomeDe(p.cliente ?? p.fornecedor ?? p.contato) || '',
  };
}

// data de vencimento é obrigatória na API; usamos uma janela larga e filtramos por competência ou pagamento
export async function buscarParcelas(tipo, filtros = {}) {
  const brutas = await todasAsPaginas(CAMINHO_PARCELAS[tipo], {
    data_vencimento_de: filtros.vencimento_de || '2018-01-01',
    data_vencimento_ate: filtros.vencimento_ate || '2035-12-31',
    data_competencia_de: filtros.competencia_de,
    data_competencia_ate: filtros.competencia_ate,
    data_pagamento_de: filtros.pagamento_de,
    data_pagamento_ate: filtros.pagamento_ate,
  });
  return brutas.map((p) => normalizarParcela(p, tipo));
}

export async function buscarEstruturaDRE() {
  const r = await get('/v1/financeiro/categorias-dre');
  return r?.itens || [];
}

export async function buscarSaldos() {
  const contas = await todasAsPaginas('/v1/conta-financeira', {}, 100, 5);
  const saida = [];
  for (const c of contas) {
    if (c.ativo === false) continue;
    let saldo = null;
    try {
      const s = await get(`/v1/conta-financeira/${c.id}/saldo-atual`);
      saldo = num(s?.saldo_atual ?? s?.saldo ?? s?.valor ?? s);
    } catch { /* conta sem saldo disponível */ }
    saida.push({ id: c.id, nome: c.nome || c.descricao || 'Conta', tipo: c.tipo || '', saldo });
  }
  return saida;
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
    vendas: () => get('/v1/venda/busca', { data_inicio: inicio, data_fim: hoje, pagina: 1, tamanho_pagina: 10 }),
    contas_a_receber: () =>
      get('/v1/financeiro/eventos-financeiros/contas-a-receber/buscar', { data_vencimento_de: inicio, data_vencimento_ate: hoje, pagina: 1, tamanho_pagina: 10 }),
  })) {
    try { saida[nome] = await fn(); } catch (e) { saida[nome] = { erro: e.message }; }
  }
  try { saida.vendedores = await get('/v1/venda/vendedores'); } catch (e) { saida.vendedores = { erro: e.message }; }
  try { saida.estrutura_dre = await get('/v1/financeiro/categorias-dre'); } catch (e) { saida.estrutura_dre = { erro: e.message }; }
  try { saida.contas_a_pagar = await get('/v1/financeiro/eventos-financeiros/contas-a-pagar/buscar', { data_vencimento_de: inicio, data_vencimento_ate: hoje, pagina: 1, tamanho_pagina: 10 }); } catch (e) { saida.contas_a_pagar = { erro: e.message }; }
  const primeira = listaDe(saida.vendas)[0];
  if (primeira?.id) {
    try { saida.itens_da_primeira_venda = await get(`/v1/venda/${primeira.id}/itens`); } catch (e) { saida.itens_da_primeira_venda = { erro: e.message }; }
  }
  return saida;
}
