// Notas fiscais emitidas na Conta Azul (v78): número, data, chave e situação da NF de cada venda.
// A Conta Azul só lista NF-e por período, com filtro por venda (GET /v1/notas-fiscais?id_venda=…); para gastar pouco,
// o painel consulta só as vendas aprovadas dos últimos 75 dias que ainda não têm nota, no máximo 25 por vez,
// e guarda o resultado (venda sem nota é consultada de novo depois de 12 horas).
import * as ca from './contaAzul.js';
import { lerKV, salvarKV } from './tokenStore.js';
import { config } from './config.js';

const CHAVE = 'nf_ca';
let cache = null, rodando = null, ultima = 0;
const hoje = () => new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10);
const ck = (n) => String(n ?? '').replace(/\D/g, '').replace(/^0+/, '');

function nota(it) {
  if (!it || typeof it !== 'object') return null;
  const v = (...k) => { for (const x of k) { const y = x.split('.').reduce((o, p) => o?.[p], it); if (y != null && y !== '') return y; } return null; };
  return {
    numero: v('numero', 'numero_nota', 'numeroNota', 'numero_nfe') != null ? String(v('numero', 'numero_nota', 'numeroNota', 'numero_nfe')) : '',
    serie: v('serie') != null ? String(v('serie')) : '',
    chave: String(v('chave', 'chave_acesso', 'chaveAcesso') || ''),
    data: String(v('data_emissao', 'dataEmissao', 'data', 'emissao') || '').slice(0, 10),
    status: String(v('status', 'situacao') || ''),
    valor: Number(v('valor_total', 'valor', 'total')) || null,
  };
}

async function lerCache() { if (!cache) cache = (await lerKV(CHAVE).catch(() => null)) || { por_venda: {} }; return cache; }

// mapa código do pedido (sem zeros) → nota, para a Planilha de vendas
export async function notasPorCodigo() {
  const c = await lerCache(), out = {};
  for (const x of Object.values(c.por_venda)) if (x?.nf && x.numero_venda) out[ck(x.numero_venda)] = x.nf;
  return out;
}

export function atualizarNotas(vendasCA) {
  if (config.demo || rodando || Date.now() - ultima < 30 * 60e3) return rodando;
  ultima = Date.now();
  rodando = (async () => {
    if (!(await ca.statusConexao()).conectado) return;
    const c = await lerCache(), lim = new Date(Date.now() - 75 * 864e5).toISOString().slice(0, 10);
    const alvo = (vendasCA || []).filter((v) => v.id && v.data >= lim && ['APROVADO', 'FATURADO'].includes(v.situacao))
      .filter((v) => { const x = c.por_venda[v.id]; return !x || (!x.nf && Date.now() - Date.parse(x.em || 0) > 12 * 3600e3); })
      .sort((a, b) => b.data.localeCompare(a.data)).slice(0, 25);
    for (const v of alvo) {
      try {
        const r = await ca.get('/v1/notas-fiscais', { data_inicial: v.data, data_final: hoje(), id_venda: v.id, pagina: 1, tamanho_pagina: 10 });
        const itens = r?.itens || r?.items || (Array.isArray(r) ? r : []);
        if (itens[0] && !c.campos) c.campos = Object.keys(itens[0]);
        c.por_venda[v.id] = { numero_venda: v.numero, nf: nota(itens[0]), em: new Date().toISOString() };
      } catch (e) { c.por_venda[v.id] = { numero_venda: v.numero, nf: null, em: new Date().toISOString(), erro: String(e.message).slice(0, 200) }; }
    }
    if (alvo.length) await salvarKV(CHAVE, c);
  })().catch((e) => console.warn('[notas CA]', e.message)).finally(() => { rodando = null; });
  return rodando;
}
