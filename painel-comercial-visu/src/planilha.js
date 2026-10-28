// Lê a planilha "Rotina de vendas_Gestão faturamento CLOUD" (fonte principal do painel de vendas)
// e transforma cada linha num registro padronizado.
//
// Duas formas de acesso, escolhidas pelas variáveis de ambiente:
//   1) PLANILHA_CSV_URL — link CSV da aba de vendas (Arquivo → Compartilhar → Publicar na Web → CSV)
//   0) Conectar Google (botão no painel, recomendado): lê o arquivo direto do Drive da conta que tem acesso
//   2) GOOGLE_SERVICE_ACCOUNT_JSON + PLANILHA_ID (+ PLANILHA_ABA) — conta de serviço com acesso de leitor,
//      sem deixar a planilha publicada (recomendado)
import crypto from 'node:crypto';
import XLSX from 'xlsx';
import { googleConectado, baixarPlanilha } from './google.js';

const env = process.env;

// ---------- Colunas: nome esperado na planilha (sem acento/maiúsculas) → campo do painel ----------
// Cada campo aceita alguns apelidos. Ajuste fino sem mexer no código: COLUNAS_JSON='{"cliente":"Nome do cliente"}'
const COLUNAS = {
  data: ['data da venda', 'data venda', 'data'],
  mes: ['mes', 'mes da venda', 'competencia'],
  // a BASE TRATADA traz o cliente padronizado (DE-PARA CLIENTES); se existir, tem prioridade sobre o nome digitado
  cliente: ['cliente padronizado', 'cliente (padronizado)', 'cliente tratado', 'cliente padrao', 'cliente', 'nome do cliente', 'razao social'],
  pedido: ['nome do pedido (trello)', 'nome do pedido', 'pedido', 'nome do pedido trello'],
  codigo: ['cod. interno', 'cod interno', 'codigo interno', 'codigo', 'cod.'],
  vendedor: ['vendedor', 'vendedora', 'consultor'],
  tipoVenda: ['tipo de venda', 'tipo venda', 'b2b/b2c'],
  // "Novo x Recompra" (BASE TRATADA) vale mais que a marcação dos vendedores
  novoRecompra: ['novo x recompra', 'novo x recompra (tratado)', 'novo/recompra tratado', 'cliente novo ou recompra?', 'cliente novo ou recompra', 'novo ou recompra', 'novo/recompra'],
  tipoProduto: ['tipo de produto', 'tipo produto', 'produto'],
  material: ['tecido', 'material', 'material/tecido', 'tecido tratado'],
  especificacao: ['especificacao', 'especificacoes'],
  cor: ['cor', 'cores'],
  quantidade: ['quantidade', 'qtd', 'qtde', 'quant.'],
  valorUnit: ['valor/und', 'valor/un', 'valor unitario', 'valor und', 'valor/unid'],
  total: ['total', 'valor total', 'total do item'],
  pag1: ['1o pagamento', '1º pagamento', 'primeiro pagamento', '1 pagamento'],
  pag2: ['2o pagamento', '2º pagamento', 'segundo pagamento', '2 pagamento'],
  pago100: ['pedido 100% pago', 'pedido 100% pago?', '100% pago'],
  formaPagamento: ['forma de pagamento', 'forma pagamento'],
  prazoEntrega: ['prazo de entrega', 'data de entrega', 'previsao de entrega'],
  frete: ['frete', 'frete da visu ou do cliente', 'frete (visu/cliente)'],
  segmento: ['segmento', 'segmento do cliente'],
  observacao: ['observacao', 'observacoes', 'obs', 'obs.'],
  // colunas da BASE TRATADA (Tiago, out/2026)
  clienteLancado: ['cliente (como lancado)', 'nome como lancado'],
  duplicado: ['possivel lancamento duplicado?', 'possivel lancamento duplicado'],
  mapeamento: ['mapeamento'],
  anterior2026: ['cliente anterior a 2026?', 'cliente anterior a 2026? (sim)'],
};

export const sem = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[º°]/g, 'o').replace(/\s+/g, ' ').trim();

function mapearCabecalho(cabecalho) {
  let extras = {};
  try { extras = env.COLUNAS_JSON ? JSON.parse(env.COLUNAS_JSON) : {}; } catch { /* ignora JSON inválido */ }
  const idx = {};
  const normal = cabecalho.map(sem);
  for (const [campo, apelidos] of Object.entries(COLUNAS)) {
    const lista = extras[campo] ? [sem(extras[campo])] : apelidos.map(sem);
    // o primeiro apelido da lista tem prioridade (ex.: "cliente padronizado" antes de "cliente")
    let i = -1;
    for (const a of lista) { i = normal.indexOf(a); if (i >= 0) break; }
    if (i < 0) for (const a of lista) { if (a.length <= 3) continue; i = normal.findIndex((h) => h.startsWith(a)); if (i >= 0) break; }
    if (i >= 0) idx[campo] = i;
  }
  return idx;
}

// ---------- CSV ----------
export function lerCSV(texto) {
  const linhas = [];
  let campo = '', linha = [], aspas = false;
  const sep = (texto.split('\n')[0].match(/;/g) || []).length > (texto.split('\n')[0].match(/,/g) || []).length ? ';' : ',';
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (aspas) {
      if (c === '"' && texto[i + 1] === '"') { campo += '"'; i++; }
      else if (c === '"') aspas = false;
      else campo += c;
    } else if (c === '"') aspas = true;
    else if (c === sep) { linha.push(campo); campo = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && texto[i + 1] === '\n') i++;
      linha.push(campo); linhas.push(linha); linha = []; campo = '';
    } else campo += c;
  }
  if (campo || linha.length) { linha.push(campo); linhas.push(linha); }
  return linhas;
}

// ---------- Conversões ----------
export function numero(v) {
  if (v === null || v === undefined) return 0;
  if (typeof v === 'number') return v;
  let s = String(v).replace(/[R$\s]/g, '');
  if (!s) return 0;
  if (s.includes(',') && s.lastIndexOf(',') > s.lastIndexOf('.')) s = s.replace(/\./g, '').replace(',', '.');
  else s = s.replace(/,/g, '');
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

export function dataISO(v) {
  if (!v) return '';
  if (typeof v === 'number') { // número de série do Google Sheets
    const d = new Date(Date.UTC(1899, 11, 30) + v * 864e5);
    return d.toISOString().slice(0, 10);
  }
  const s = String(v).trim();
  let m = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})/);
  if (m) {
    const ano = m[3].length === 2 ? '20' + m[3] : m[3];
    return `${ano}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`;
  }
  m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[1]}-${m[2]}-${m[3]}` : '';
}

const MESES = { jan: 1, fev: 2, mar: 3, abr: 4, mai: 5, jun: 6, jul: 7, ago: 8, set: 9, out: 10, nov: 11, dez: 12 };
function mesDe(v, anoPadrao) {
  const s = sem(v);
  let m = s.match(/^(\d{1,2})[/-](\d{4})$/);
  if (m) return `${m[2]}-${m[1].padStart(2, '0')}`;
  m = s.match(/^([a-z]{3})[a-z]*[\s/-]*(\d{2,4})?/);
  if (m && MESES[m[1]]) {
    const ano = m[2] ? (m[2].length === 2 ? '20' + m[2] : m[2]) : anoPadrao;
    return ano ? `${ano}-${String(MESES[m[1]]).padStart(2, '0')}` : '';
  }
  return '';
}

function novoOuRecompra(v) {
  const s = sem(v);
  if (!s) return '';
  if (s.includes('recompra') || s.includes('recorr') || s.startsWith('antigo') || s === 'r') return 'recompra';
  if (s.includes('novo') || s.includes('nova') || s === 'n') return 'novo';
  return '';
}

function simNao(v) {
  const s = sem(v);
  return ['sim', 's', 'x', 'ok', 'pago', '100%', 'true', 'verdadeiro'].includes(s);
}

// "Yelloran lote 1", "Yelloran - Lote 2" → "Yelloran" (cadastro único por cliente, seção 5 da especificação)
export function clienteBase(nome) {
  return String(nome || '').replace(/\s*[-–(]?\s*\blote\s*\d+\)?\s*$/i, '').replace(/\s+/g, ' ').trim();
}

// ---------- Normalização das linhas ----------
export function normalizarLinhas(matriz) {
  // procura a linha de cabeçalho entre as 10 primeiras (às vezes há título acima)
  let h = 0, idx = {};
  for (let i = 0; i < Math.min(matriz.length, 10); i++) {
    const t = mapearCabecalho(matriz[i]);
    if (Object.keys(t).length > Object.keys(idx).length) { idx = t; h = i; }
  }
  const cabecalho = matriz[h] || [];
  const faltando = ['data', 'cliente', 'total'].filter((c) => idx[c] === undefined && !(c === 'data' && idx.mes !== undefined));
  const val = (lin, campo) => (idx[campo] === undefined ? '' : lin[idx[campo]] ?? '');
  const linhas = [];
  for (let i = h + 1; i < matriz.length; i++) {
    const lin = matriz[i];
    if (!lin || lin.every((c) => String(c ?? '').trim() === '')) continue;
    const quantidade = numero(val(lin, 'quantidade'));
    const unit = numero(val(lin, 'valorUnit'));
    let total = numero(val(lin, 'total'));
    if (!total && quantidade && unit) total = quantidade * unit;
    const data = dataISO(val(lin, 'data'));
    const mes = data ? data.slice(0, 7) : mesDe(val(lin, 'mes'), env.PLANILHA_ANO_PADRAO);
    const clienteOriginal = String(val(lin, 'clienteLancado') || val(lin, 'cliente')).trim();
    const clientePadrao = String(val(lin, 'cliente')).trim();
    const pedidoTxt = String(val(lin, 'codigo') || val(lin, 'pedido')).trim();
    if (!clienteOriginal && !total) continue; // linhas vazias
    if (!clienteOriginal && !data) continue; // linha de TOTAL ou subtotal no fim da planilha
    if (lin.some((c) => /^\s*(sub)?total\b/i.test(String(c ?? '')))) continue;
    linhas.push({
      linha: i + 1,
      data, mes,
      cliente: (idx.clienteLancado !== undefined ? clientePadrao : clienteBase(clienteOriginal)) || 'Sem cliente',
      cliente_original: clienteOriginal,
      pedido: pedidoTxt || `${clienteBase(clienteOriginal)}|${data || mes}`,
      pedido_informado: !!pedidoTxt,
      vendedor: String(val(lin, 'vendedor')).trim() || 'Sem vendedor',
      tipo_venda: String(val(lin, 'tipoVenda')).trim().toUpperCase() || '—',
      novo_recompra: novoOuRecompra(val(lin, 'novoRecompra')),
      tipo_produto: String(val(lin, 'tipoProduto')).trim(),
      material: String(val(lin, 'material')).trim(),
      especificacao: String(val(lin, 'especificacao')).trim(),
      cor: String(val(lin, 'cor')).trim(),
      quantidade, total,
      pag1: numero(val(lin, 'pag1')), pag2: numero(val(lin, 'pag2')),
      pago_100: simNao(val(lin, 'pago100')),
      forma_pagamento: String(val(lin, 'formaPagamento')).trim(),
      prazo_entrega: dataISO(val(lin, 'prazoEntrega')),
      frete: String(val(lin, 'frete')).trim(),
      segmento: String(val(lin, 'segmento')).trim(),
      duplicado: sem(val(lin, 'duplicado')) === 'verificar',
      nome_novo: sem(val(lin, 'mapeamento')).includes('novo'),
    });
  }
  return {
    linhas,
    mapa: {
      linha_cabecalho: h + 1,
      reconhecidas: Object.fromEntries(Object.entries(idx).map(([c, i]) => [c, cabecalho[i]])),
      nao_encontradas: Object.keys(COLUNAS).filter((c) => idx[c] === undefined),
      obrigatorias_faltando: faltando,
      nr_tratado: idx.novoRecompra !== undefined && sem(cabecalho[idx.novoRecompra]).startsWith('novo x'),
      colunas_da_planilha: cabecalho.filter((c) => String(c).trim()),
    },
  };
}

// ---------- Acesso ----------
export const planilhaConfigurada = () => !!(googleConectado() || env.PLANILHA_CSV_URL || (env.GOOGLE_SERVICE_ACCOUNT_JSON && env.PLANILHA_ID));

async function tokenContaServico() {
  const sa = JSON.parse(env.GOOGLE_SERVICE_ACCOUNT_JSON);
  const agora = Math.floor(Date.now() / 1000);
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const corpo = `${b64({ alg: 'RS256', typ: 'JWT' })}.${b64({
    iss: sa.client_email, scope: 'https://www.googleapis.com/auth/spreadsheets.readonly',
    aud: 'https://oauth2.googleapis.com/token', iat: agora, exp: agora + 3600,
  })}`;
  const assinatura = crypto.createSign('RSA-SHA256').update(corpo).sign(sa.private_key, 'base64url');
  const r = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer', assertion: `${corpo}.${assinatura}` }),
  });
  const j = await r.json();
  if (!r.ok) throw new Error(`Google recusou a conta de serviço: ${j.error_description || j.error}`);
  return j.access_token;
}

// escolhe a aba: PLANILHA_ABA, senão a que tiver mais vendas reconhecidas
const matrizDe = (wb, n) => XLSX.utils.sheet_to_json(wb.Sheets[n], { header: 1, raw: true, defval: '' });
const acharAba = (wb, teste) => wb.SheetNames.find((n) => teste(sem(n)));

// DE-PARA CLIENTES (col. A = nome como lançado, col. B = cliente padronizado) e CLIENTES (col. "Cliente anterior a 2026?")
function lerTratamento(wb) {
  const t = { depara: null, anteriores: null };
  const dp = acharAba(wb, (n) => /de.?para/.test(n) && n.includes('client'));
  if (dp) {
    t.depara = new Map();
    for (const [de, para] of XLSX.utils.sheet_to_json(wb.Sheets[dp], { header: 1, raw: false, defval: '' }).slice(1)) if (sem(de) && String(para).trim()) t.depara.set(sem(de), String(para).trim());
    t.aba_depara = dp;
  }
  const cl = acharAba(wb, (n) => n === 'clientes');
  if (cl) {
    const m = matrizDe(wb, cl), h = (m[0] || []).map(sem);
    const iC = h.findIndex((x) => x.startsWith('cliente padronizado')), iA = h.findIndex((x) => x.startsWith('cliente anterior a 2026'));
    if (iC >= 0 && iA >= 0) { t.anteriores = new Set(m.slice(1).filter((r) => sem(r[iA]).startsWith('s')).map((r) => sem(r[iC]))); t.aba_clientes = cl; }
  }
  return t;
}

// Aplica o mesmo tratamento da BASE TRATADA quando a planilha só tem a base crua:
// cliente padronizado pelo DE-PARA; novo = 1ª data de compra do cliente na base (e não marcado como anterior a 2026).
export function tratarClientes(linhas, t) {
  let nomesNovos = 0;
  if (t.depara) for (const l of linhas) { const p = t.depara.get(sem(l.cliente_original)); if (p) l.cliente = p; else { l.nome_novo = true; nomesNovos++; } if (!l.pedido_informado || t.pedidoPorData) l.pedido = `${l.cliente}|${l.data || l.mes}`; }
  const primeira = new Map();
  for (const l of linhas) { const k = sem(l.cliente), d = l.data || `${l.mes}-01`; if (!primeira.has(k) || d < primeira.get(k)) primeira.set(k, d); }
  for (const l of linhas) {
    const k = sem(l.cliente);
    l.novo_recompra = t.anteriores?.has(k) ? 'recompra' : (l.data || `${l.mes}-01`) === primeira.get(k) ? 'novo' : 'recompra';
  }
  return { nomes_novos: nomesNovos };
}

// Lê o arquivo da planilha de vendas.
//  - com a aba BASE TRATADA: usa ela (cliente padronizado, Novo x Recompra) e completa pagamento, prazo e especificação pela BASE DE DADOS (mesma linha);
//  - sem ela, mas com DE-PARA CLIENTES: o painel faz o tratamento sozinho a partir da base crua;
//  - sem nada disso: usa a base como está (marcação dos vendedores).
export function lerXlsx(bytes, aba = env.PLANILHA_ABA) {
  const wb = XLSX.read(bytes, { type: 'buffer', cellDates: false });
  const tratada = aba ? null : acharAba(wb, (n) => n.includes('base tratada'));
  const nomes = aba ? wb.SheetNames.filter((n) => sem(n) === sem(aba)) : tratada ? [tratada] : wb.SheetNames.filter((n) => !/resultado|de.?para|^clientes$/.test(sem(n)));
  if (!nomes.length) throw new Error(`A planilha não tem a aba "${aba}". Abas: ${wb.SheetNames.join(', ')}.`);
  let melhor = null;
  for (const n of nomes) {
    let r; try { r = normalizarLinhas(matrizDe(wb, n)); } catch { continue; }
    const ok = !(r.mapa?.obrigatorias_faltando?.length);
    const nota = (ok ? 1e9 : 0) + (r.linhas?.length || 0);
    if (!melhor || nota > melhor.nota) melhor = { nota, r, aba: n };
  }
  if (!melhor) throw new Error('Não encontrei a aba de vendas na planilha.');
  const r = melhor.r; r.aba = melhor.aba;
  const t = lerTratamento(wb);
  if (tratada && melhor.aba === tratada) {
    r.mapa.tratamento = 'base_tratada';
    // completa com a BASE DE DADOS (as duas abas andam linha a linha)
    const bruta = acharAba(wb, (n) => n.includes('base de dados'));
    if (bruta) {
      const rb = normalizarLinhas(matrizDe(wb, bruta)), porLinha = new Map(rb.linhas.map((l) => [l.linha, l]));
      let unidas = 0;
      for (const l of r.linhas) {
        const b = porLinha.get(l.linha);
        if (!b || sem(b.cliente_original) !== sem(l.cliente_original)) continue;
        unidas++;
        for (const c of ['pag1', 'pag2', 'pago_100', 'forma_pagamento', 'prazo_entrega', 'especificacao', 'frete', 'segmento']) if (!l[c] && b[c]) l[c] = b[c];
        if (b.pedido_informado) l.codigo_pedido = b.pedido;
      }
      r.mapa.base_dados = { aba: bruta, linhas_unidas: unidas, linhas: r.linhas.length };
      for (const [c, col] of Object.entries(rb.mapa.reconhecidas)) if (!r.mapa.reconhecidas[c] && ['pag1', 'pag2', 'pago100', 'formaPagamento', 'prazoEntrega', 'especificacao', 'frete', 'segmento', 'codigo'].includes(c)) r.mapa.reconhecidas[c] = `${col} (aba ${bruta})`;
      r.mapa.nao_encontradas = Object.keys(COLUNAS).filter((c) => !r.mapa.reconhecidas[c]);
    }
    r.mapa.nomes_novos = r.linhas.filter((l) => l.nome_novo).length;
  } else if (t.depara) {
    const x = tratarClientes(r.linhas, { ...t, pedidoPorData: true });
    r.mapa.tratamento = 'painel';
    r.mapa.nr_tratado = true;
    r.mapa.nomes_novos = x.nomes_novos;
  }
  if (t.depara) r.mapa.de_para = { aba: t.aba_depara, nomes: t.depara.size, anteriores_2026: t.anteriores ? t.anteriores.size : null };
  r.mapa.duplicados = r.linhas.filter((l) => l.duplicado).map((l) => ({ linha: l.linha, data: l.data, cliente: l.cliente, total: l.total, produto: l.tipo_produto }));
  return r;
}

export async function lerPlanilha() {
  if (googleConectado()) {
    const arq = await baixarPlanilha();
    const r = lerXlsx(arq.bytes);
    r.arquivo = { nome: arq.nome, alterado_em: arq.alterado_em, aba: r.aba };
    return r;
  }
  if (env.PLANILHA_CSV_URL) {
    const r = await fetch(env.PLANILHA_CSV_URL, { redirect: 'follow' });
    if (!r.ok) throw new Error(`Não consegui baixar a planilha (${r.status}). Confira o link CSV publicado.`);
    const texto = await r.text();
    if (/^\s*<!doctype html|<html/i.test(texto)) throw new Error('O link da planilha devolveu uma página, não um CSV. Use "Publicar na Web" no formato CSV.');
    return normalizarLinhas(lerCSV(texto));
  }
  const token = await tokenContaServico();
  const aba = env.PLANILHA_ABA ? `'${env.PLANILHA_ABA.replace(/'/g, "''")}'` : 'A:ZZ';
  const url = `https://sheets.googleapis.com/v4/spreadsheets/${env.PLANILHA_ID}/values/${encodeURIComponent(aba)}?valueRenderOption=UNFORMATTED_VALUE&dateTimeRenderOption=SERIAL_NUMBER`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  const j = await r.json();
  if (!r.ok) throw new Error(`Google Sheets: ${j.error?.message || r.status}. A planilha foi compartilhada com a conta de serviço?`);
  return normalizarLinhas(j.values || []);
}
