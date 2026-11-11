// Contas a receber · gestão da cobrança (v81): ação, observação, decisão na reunião e responsável de cada título em aberto,
// e os recebimentos sem cliente identificado (DNI). Os títulos e valores vêm da Conta Azul (financeiro.js); aqui ficam só
// as anotações. Semente: planilha "Contas a receber Visu 10-11-2026 v2" (Seja Expert), aplicada pela venda + vencimento + valor.
import fs from 'node:fs';
import { lerKV, salvarKV } from './tokenStore.js';

const CHAVE = 'receber_gestao';
export const ACOES = ['Cobrar cliente', 'Confirmar com o comercial', 'Localizar recebimento (indício de pago)', 'Conciliar recebimento já identificado', 'Ajustar lançamento no CA', 'Baixar resíduo (desconto/taxa)', 'A vencer: acompanhar'];
let memo = null;
const txt = (v, max = 2000) => String(v ?? '').replace(/\r/g, '').trim().slice(0, max);
export const chaveTitulo = (venda, venc, valor) => `${String(venda || '').replace(/\D/g, '').replace(/^0+/, '')}|${String(venc || '').slice(0, 10)}|${Math.round((Number(valor) || 0) * 100)}`;

function semente() {
  const s = JSON.parse(fs.readFileSync(new URL('./receber_semente.json', import.meta.url), 'utf8'));
  const anot = {};
  for (const t of s.titulos) anot[chaveTitulo(t.venda, t.venc, t.valor)] = { acao: t.acao || '', obs: t.obs || '', decisao: t.decisao || '', resp: t.resp || '', ca: t.ca || '', planilha: t.planilha || '', possiveis: t.possiveis || '', vendedor: t.vendedor || '', origem: 'planilha 10/11' };
  return { versao: 1, anot, dni: s.dni.map((d, i) => ({ id: 'd' + i, ...d, conciliado: false })), semente_em: '2026-11-10', atualizado_em: null };
}

export async function lerGestao() {
  if (!memo) memo = (await lerKV(CHAVE).catch(() => null)) || semente();
  return memo;
}

export async function salvarTitulo(b, u) {
  const d = await lerGestao();
  const chave = txt(b.chave, 120); if (!chave) throw new Error('Título inválido.');
  const atual = d.anot[chave] || {};
  const acao = b.acao === undefined ? atual.acao : (ACOES.includes(b.acao) ? b.acao : '');
  d.anot[chave] = { ...atual, acao, obs: b.obs === undefined ? atual.obs : txt(b.obs), decisao: b.decisao === undefined ? atual.decisao : txt(b.decisao, 500), resp: b.resp === undefined ? atual.resp : txt(b.resp, 80), em: new Date().toISOString(), por: u?.nome || '' };
  d.atualizado_em = new Date().toISOString(); memo = d; await salvarKV(CHAVE, d);
  return d.anot[chave];
}

export async function salvarDni(b, u) {
  const d = await lerGestao();
  const x = d.dni.find((y) => y.id === b.id); if (!x) throw new Error('Lançamento não encontrado.');
  if (b.conciliado !== undefined) x.conciliado = !!b.conciliado;
  if (b.titulo !== undefined) x.titulo = txt(b.titulo, 300);
  x.em = new Date().toISOString(); x.por = u?.nome || '';
  d.atualizado_em = new Date().toISOString(); memo = d; await salvarKV(CHAVE, d);
  return x;
}
