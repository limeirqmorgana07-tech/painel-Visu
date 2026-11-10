// Pedidos de venda registrados no próprio painel (reunião Visu × Seja Expert de 03/11/2026).
// - Registro de vendas: as mesmas colunas da planilha do comercial; a partir de novembro os vendedores lançam aqui.
// - Base de janeiro a outubro importada da planilha conectada (ou de um arquivo .xlsx), para revisão dos vendedores.
// - Regra: o vendedor altera quantidade e valores até 24 h depois de lançar; depois disso, acréscimo vira
//   pedido complementar (mesmo código + "-1", "-2"...), que gera título complementar na Conta Azul.
// - Histórico: toda criação, alteração, exclusão e importação fica registrada (quem, quando, o que mudou).
// - Pagamentos: 1º e 2º pagamento vêm da Conta Azul pelo código do pedido (parcelas a receber da venda).
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { config } from './config.js';
import { banco, lerKV, salvarKV } from './tokenStore.js';
import { lerPlanilha, lerPlanilhaRecente, lerXlsx, planilhaConfigurada, clienteBase, sem, separarLoteNome } from './planilha.js';
import { gerarDemoPlanilha, gerarDemoParcelas } from './demo.js';
import * as ca from './contaAzul.js';

const pasta = () => path.dirname(config.arquivoToken);
const agoraISO = () => new Date().toISOString();
const r2 = (v) => Math.round((Number(v) || 0) * 100) / 100;

// ---------- campos (mesma ordem da planilha) ----------
export const CAMPOS = {
  data: 'data', codigo: 'texto', cliente: 'texto', lote: 'texto', nome_pedido: 'texto', vendedor: 'texto', tipo_venda: 'texto',
  novo_recompra: 'nr', segmento: 'texto', tipo_produto: 'texto', material: 'texto', especificacao: 'texto', cor: 'texto',
  quantidade: 'num', valor_unit: 'num', total: 'num', pag1: 'num', data_pag1: 'data', pag2: 'num', data_pag2: 'data', pag3: 'num', banco_pag: 'texto', pago_100: 'bool', prazo_entrega: 'data',
  forma_pagamento: 'texto', parcelas: 'parc', frete: 'texto', pagador: 'texto', observacao: 'texto', pct_premiacao: 'pct', mes_premiacao: 'mesp', obs_premiacao: 'texto',
};
// travados para o vendedor 24 h depois do lançamento (o resto, como cliente e novo × recompra, ele revisa sempre)
export const CAMPOS_VALOR = ['data', 'codigo', 'tipo_produto', 'material', 'especificacao', 'cor', 'quantidade', 'valor_unit', 'total'];
const HORAS_EDICAO = Number(process.env.HORAS_EDICAO_PEDIDO || 24);
const GESTAO = new Set(['adm', 'diretor', 'financeiro']);

// código da Visu: sequência do mês (4 dígitos) + mês + ano, ex.: 0030102026; complementar: 0030102026-1
export const codigoBase = (c) => String(c || '').trim().split(/[-/ ]/)[0];
export const chaveCodigo = (c) => String(c || '').replace(/\D/g, '').replace(/^0+/, '');
const RX_COD = /^(\d{4})(\d{2})(\d{4})$/;

// vendedor num padrão só (maiúsculas só na inicial): "DANIEL" e "daniel" viram "Daniel"
const MINUSC_NOME = new Set(['da', 'de', 'do', 'das', 'dos', 'e']);
export const tituloNome = (t) => String(t ?? '').trim().replace(/\s+/g, ' ').toLowerCase().split(' ').map((w, i) => (i > 0 && MINUSC_NOME.has(w) ? w : w.replace(/^(\p{L})/u, (m) => m.toUpperCase()))).join(' ');
function limpar(campo, v) {
  const t = CAMPOS[campo];
  if (campo === 'vendedor') return tituloNome(String(v ?? '').slice(0, 120));
  // % de premiação manual: em branco = segue a faixa do mês (não é 0%)
  // mês da premiação (manual): a venda entra na premiação deste mês, sem mudar a data da venda (ex.: Raíra Sicoob, venda de 01/10 premiada em setembro)
  if (t === 'mesp') { const s0 = String(v ?? '').trim(); let m = s0.match(/^(\d{4})-(\d{2})/); if (m) return `${m[1]}-${m[2]}`; m = s0.match(/^(?:\d{1,2}\/)?(\d{1,2})\/(\d{4})$/); if (m) return `${m[2]}-${m[1].padStart(2, '0')}`; return ''; }
  if (t === 'pct') { if (v === '' || v == null) return null; const n = Number(String(v).replace(/[%\s]/g, '').replace(',', '.')); return Number.isFinite(n) ? r2(n) : null; }
  // parcelas: 1 = à vista, 2 = 50% + 50% (padrão), 3 ou mais = parcelas iguais
  if (t === 'parc') { const s0 = sem(v); if (!s0) return 2; if (/vista/.test(s0)) return 1; const n = parseInt(s0, 10); return Number.isFinite(n) && n >= 1 ? Math.min(n, 12) : 2; }
  if (t === 'num') { const n = typeof v === 'number' ? v : Number(String(v ?? '').replace(/[R$\s.]/g, '').replace(',', '.')); return Number.isFinite(n) ? r2(n) : 0; }
  if (t === 'bool') return v === true || ['sim', 's', 'true', '1', 'x'].includes(sem(v));
  if (t === 'data') { const s = String(v ?? '').trim(); const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/) || s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/); if (!m) return ''; return m[1].length === 4 ? `${m[1]}-${m[2]}-${m[3]}` : `${m[3]}-${m[2].padStart(2, '0')}-${m[1].padStart(2, '0')}`; }
  if (t === 'nr') { const s = sem(v); return s.startsWith('rec') ? 'recompra' : s.startsWith('nov') ? 'novo' : ''; }
  return String(v ?? '').replace(/\s+/g, ' ').trim().slice(0, 300);
}
// O que vem depois do nome do cliente ("Giba - Clube Cabo Branco (Dental Center)" → "Dental Center") é o que diferencia
// a venda para o cliente, os vendedores e a produção: ao unificar o nome, esse texto vai para a coluna Lote / obs. do cliente.
export function restoDoNome(original, para) {
  const tk = String(original || '').trim().split(/\s+/), pw = String(para || '').trim().split(/\s+/).map((w) => sem(w).replace(/[^a-z0-9]/g, '')).filter(Boolean);
  let j = 0, i = 0;
  for (; i < tk.length && j < pw.length; i++) { const k = sem(tk[i]).replace(/[^a-z0-9]/g, ''); if (!k) continue; if (k === pw[j]) j++; else break; }
  if (j < pw.length) return '';
  const r = tk.slice(i).join(' ').replace(/^[\s\-–—(\[:,.;/]+|[\s\-–—)\]:,.;/]+$/g, '').replace(/^\((.*)\)$/, '$1').trim();
  return /^lote\s*\d+$/i.test(r) ? r.replace(/^l/i, 'L') : r;
}
const juntarObs = (lote, resto) => !resto || sem(lote || '').includes(sem(resto)) ? (lote || '') : (lote ? `${lote} · ${resto}` : resto);
// "Contour Inglesa lote 2" → cliente "Contour Inglesa" e lote "Lote 2"
export function separarLote(nome) { return separarLoteNome(nome); }

// ---------- armazenamento (Postgres com DATABASE_URL; arquivo sem ele) ----------
let mem = null; // Map id → registro
let logMem = null; // só sem banco
let tabelasOk = false;
async function pool() {
  const p = await banco();
  if (p && !tabelasOk) {
    await p.query('CREATE TABLE IF NOT EXISTS pedidos_venda (id TEXT PRIMARY KEY, dados JSONB NOT NULL, atualizado_em TIMESTAMPTZ DEFAULT now())');
    await p.query(`CREATE TABLE IF NOT EXISTS pedidos_log (id BIGSERIAL PRIMARY KEY, quando TIMESTAMPTZ DEFAULT now(), usuario TEXT, usuario_id TEXT,
      acao TEXT, registro TEXT, codigo TEXT, cliente TEXT, mudancas JSONB, detalhe TEXT)`);
    await p.query('CREATE INDEX IF NOT EXISTS pedidos_log_quando ON pedidos_log (quando DESC)');
    tabelasOk = true;
  }
  return p;
}
async function carregar() {
  if (mem) return mem;
  const p = await pool();
  const m = new Map();
  if (p) { const r = await p.query('SELECT dados FROM pedidos_venda'); for (const x of r.rows) m.set(x.dados.id, x.dados); }
  else { try { for (const x of JSON.parse(await fs.readFile(path.join(pasta(), 'pedidos.json'), 'utf8'))) m.set(x.id, x); } catch { /* ainda não há pedidos */ } }
  mem = m;
  await consolidarClientes().catch((e) => console.warn('[pedidos] consolidar clientes:', e.message));
  await limparPct0().catch((e) => console.warn('[pedidos] premiação 0%:', e.message));
  await recuperarObsCliente().catch((e) => console.warn('[pedidos] obs. do cliente:', e.message));
  return mem;
}
// Clientes unificados antes da v66 perderam o texto que diferenciava a venda (ex.: "(Dental Center)"):
// volta para a coluna Lote / obs. do cliente, a partir do nome como foi lançado. Só completa; não apaga nada.
async function recuperarObsCliente() {
  const novos = [];
  for (const r of mem.values()) {
    if (r.excluido) continue;
    if (/\blote\s*\d/i.test(r.cliente || '')) { const sl = separarLoteNome(r.cliente); const n = { ...r, cliente: sl.cliente || r.cliente, cliente_lancado: r.cliente_lancado || r.cliente, lote: juntarObs(r.lote, sl.lote) }; mem.set(r.id, n); novos.push([r, n]); continue; }
    if (!r.cliente_lancado || r.cliente_lancado === r.cliente) continue;
    const resto = restoDoNome(r.cliente_lancado, r.cliente); const lote = juntarObs(r.lote, resto);
    if (lote !== (r.lote || '')) { const n = { ...r, lote }; mem.set(r.id, n); novos.push([r, n]); }
  }
  if (!novos.length) return 0;
  await gravar(novos.map((x) => x[1]));
  await registrarLog(novos.map(([r, n]) => ({ ...quem(null), usuario: 'Unificação de clientes', acao: 'alterou', registro: r.id, codigo: r.codigo || null, cliente: r.cliente, mudancas: [{ campo: 'lote', antes: r.lote || '', depois: n.lote }], detalhe: `Obs. do cliente recuperada do nome lançado: ${r.cliente_lancado}` }))).catch(() => {});
  console.log('[pedidos] obs. do cliente recuperada em', novos.length, 'linhas');
  return novos.length;
}
// Até a v60, salvar o campo Premiação % (manual) em branco gravava 0% (ex.: Cabo Branco, Milena, out/2026),
// e o pedido deixava de pagar premiação. Uma vez só: volta esses 0% para em branco (segue a faixa do mês).
// Depois disso, um 0% gravado de propósito é mantido.
async function limparPct0() {
  if (await lerKV('migr_pct0_v63').catch(() => null)) return 0;
  const alvo = [...mem.values()].filter((r) => r.pct_premiacao === 0);
  const novos = alvo.map((r) => ({ ...r, pct_premiacao: null, alterado_em: agoraISO(), alterado_por: 'Correção premiação 0%' }));
  for (const n of novos) mem.set(n.id, n);
  if (novos.length) {
    await gravar(novos);
    await registrarLog(novos.map((n) => ({ ...quem(null), usuario: 'Correção premiação 0%', acao: 'alterou', registro: n.id, codigo: n.codigo || null, cliente: n.cliente || '', mudancas: [{ campo: 'pct_premiacao', antes: '0%', depois: 'em branco (segue a faixa)' }], detalhe: 'Premiação % gravada como 0% por engano' }))).catch(() => {});
  }
  await salvarKV('migr_pct0_v63', { em: agoraISO(), n: novos.length, codigos: novos.map((n) => n.codigo) });
  console.log('[pedidos] premiação 0% voltou para em branco em', novos.length, 'pedidos');
  return novos.length;
}
// Cadastro único por cliente (validado pela Visu em 08/11/2026): o mesmo cliente escrito de jeitos diferentes
// (maiúsculas, acento, pontuação ou "lote N" no nome) vira um nome só; o lote vai para a coluna Lote / obs. do cliente.
// Roda ao carregar os pedidos e é idempotente: só mexe em quem ainda está fora do padrão.
const chaveCli = (s) => sem(clienteBase(s)).replace(/[^a-z0-9]+/g, ' ').trim();
async function consolidarClientes() {
  const vivos = [...mem.values()].filter((r) => !r.excluido && r.cliente);
  const grupos = new Map();
  for (const r of vivos) { const k = chaveCli(r.cliente); if (!k) continue; const g = grupos.get(k) || new Map(); const base = clienteBase(r.cliente); g.set(base, (g.get(base) || 0) + 1); grupos.set(k, g); }
  const canon = new Map([...grupos].map(([k, g]) => [k, [...g.entries()].sort((a, b) => b[1] - a[1] || a[0].length - b[0].length)[0][0]]));
  const mudados = [];
  for (const r of vivos) {
    const para = canon.get(chaveCli(r.cliente)); if (!para || r.cliente === para) continue;
    const sl = separarLote(r.cliente);
    const n = { ...r, cliente: para, cliente_lancado: r.cliente_lancado || r.cliente, lote: r.lote || sl.lote || '', alterado_em: agoraISO(), alterado_por: 'Consolidação de clientes' };
    mudados.push([r, n]); mem.set(r.id, n);
  }
  if (!mudados.length) return 0;
  await gravar(mudados.map((x) => x[1]));
  const nomes = [...new Set(mudados.map((x) => x[1].cliente))];
  await registrarLog([{ ...quem(null), usuario: 'Consolidação de clientes', acao: 'unificou', codigo: null, cliente: nomes.slice(0, 5).join(' · ') + (nomes.length > 5 ? ` e mais ${nomes.length - 5}` : ''), mudancas: [{ campo: 'cliente', antes: `${mudados.length} linhas com o nome escrito de outro jeito`, depois: `${nomes.length} ${nomes.length === 1 ? 'cliente' : 'clientes'} com cadastro único` }], detalhe: `${mudados.length} linhas` }]).catch(() => {});
  return mudados.length;
}
async function gravar(regs) {
  if (!regs.length) return;
  const p = await pool();
  if (p) {
    for (let i = 0; i < regs.length; i += 400) {
      const lote = regs.slice(i, i + 400);
      const vals = lote.map((_, k) => `($${2 * k + 1}, $${2 * k + 2}, now())`).join(',');
      await p.query(`INSERT INTO pedidos_venda (id, dados, atualizado_em) VALUES ${vals} ON CONFLICT (id) DO UPDATE SET dados = EXCLUDED.dados, atualizado_em = now()`, lote.flatMap((r) => [r.id, JSON.stringify(r)]));
    }
    return;
  }
  await fs.mkdir(pasta(), { recursive: true });
  await fs.writeFile(path.join(pasta(), 'pedidos.json'), JSON.stringify([...mem.values()]));
}
async function apagarDefinitivo(ids) {
  if (!ids.length) return;
  const p = await pool();
  if (p) { await p.query('DELETE FROM pedidos_venda WHERE id = ANY($1)', [ids]); return; }
  await fs.writeFile(path.join(pasta(), 'pedidos.json'), JSON.stringify([...mem.values()]));
}
async function registrarLog(entradas) {
  if (!entradas.length) return;
  const p = await pool();
  if (p) {
    for (const e of entradas) await p.query('INSERT INTO pedidos_log (quando, usuario, usuario_id, acao, registro, codigo, cliente, mudancas, detalhe) VALUES (now(), $1, $2, $3, $4, $5, $6, $7, $8)',
      [e.usuario, e.usuario_id, e.acao, e.registro || null, e.codigo || null, e.cliente || null, JSON.stringify(e.mudancas || []), e.detalhe || null]);
    return;
  }
  if (!logMem) { try { logMem = JSON.parse(await fs.readFile(path.join(pasta(), 'pedidos_log.json'), 'utf8')); } catch { logMem = []; } }
  for (const e of entradas) logMem.push({ id: logMem.length + 1, quando: agoraISO(), ...e });
  if (logMem.length > 20000) logMem = logMem.slice(-20000);
  await fs.mkdir(pasta(), { recursive: true });
  await fs.writeFile(path.join(pasta(), 'pedidos_log.json'), JSON.stringify(logMem));
}
export async function historico({ codigo, usuario, acao, dias = 90, limite = 3000 } = {}) {
  const p = await pool();
  const desde = new Date(Date.now() - Number(dias || 3650) * 864e5).toISOString();
  if (p) {
    const cond = ['quando >= $1'], par = [desde];
    if (codigo) { par.push(`%${codigo}%`); cond.push(`codigo ILIKE $${par.length}`); }
    if (usuario) { par.push(usuario); cond.push(`usuario = $${par.length}`); }
    if (acao) { par.push(acao); cond.push(`acao = $${par.length}`); }
    par.push(Math.min(Number(limite) || 3000, 10000));
    const r = await p.query(`SELECT id, quando, usuario, acao, registro, codigo, cliente, mudancas, detalhe FROM pedidos_log WHERE ${cond.join(' AND ')} ORDER BY quando DESC, id DESC LIMIT $${par.length}`, par);
    return r.rows.map((x) => ({ ...x, quando: new Date(x.quando).toISOString() }));
  }
  if (!logMem) { try { logMem = JSON.parse(await fs.readFile(path.join(pasta(), 'pedidos_log.json'), 'utf8')); } catch { logMem = []; } }
  return logMem.filter((e) => e.quando >= desde && (!codigo || String(e.codigo || '').includes(codigo)) && (!usuario || e.usuario === usuario) && (!acao || e.acao === acao)).slice(-limite).reverse();
}

// ---------- configuração: de onde os indicadores leem as vendas ----------
let cfgMem = null;
export async function configPedidos() { if (!cfgMem) cfgMem = (await lerKV('pedidos_config').catch(() => null)) || { fonte: 'planilha' }; return cfgMem; }
export async function salvarConfigPedidos(c, usuario) {
  cfgMem = { ...(await configPedidos()), ...c, atualizado_em: agoraISO(), por: usuario?.nome || '' };
  await salvarKV('pedidos_config', cfgMem);
  return cfgMem;
}
// usado pelo vendas.js: com a fonte "painel", os indicadores passam a ler os pedidos registrados aqui
export const fontePainel = () => cfgMem?.fonte === 'painel' && !!mem && [...mem.values()].some((r) => !r.excluido);
// planilha até o mês anterior ao corte, pedidos do painel a partir dele (reunião: novembro todo no sistema)
export const fonteMista = () => (cfgMem?.fonte === 'misto' ? cfgMem.corte || '2026-11' : null);
// enquanto a planilha do Google estiver em uso (até a gestão encerrar), as vendas lançadas nela depois do corte também entram no painel
export const planilhaEmUso = () => !cfgMem?.planilha_encerrada;
export async function prepararFonte() { await configPedidos(); await carregar().catch(() => {}); }
export function linhasDoPainel() {
  return [...(mem?.values() || [])].filter((r) => !r.excluido && (r.total || r.quantidade)).map((r) => ({
    linha: r.linha_planilha || null, do_painel: true, pct_premiacao: r.pct_premiacao ?? null, mes_premiacao: r.mes_premiacao || '', obs_premiacao: r.obs_premiacao || '', data: r.data, mes: r.mes || (r.data || '').slice(0, 7), cliente: r.cliente || 'Sem cliente',
    cliente_original: r.cliente_lancado || [r.cliente, r.lote].filter(Boolean).join(' '),
    // o complementar conta no mesmo pedido (não infla a quantidade de pedidos nem derruba o ticket)
    // linhas importadas seguem a regra da base tratada (pedido = cliente + data), para os números baterem com a planilha;
    // pedidos lançados no painel usam o código (o complementar "-1" conta no mesmo pedido)
    pedido: r.codigo && r.origem !== 'planilha' ? codigoBase(r.codigo) : `${r.cliente}|${r.data || r.mes}`, codigo_pedido: r.codigo || '', pedido_informado: !!r.codigo,
    vendedor: r.vendedor ? tituloNome(r.vendedor) : 'Sem vendedor', tipo_venda: (r.tipo_venda || '—').toUpperCase(), novo_recompra: r.novo_recompra || '',
    tipo_produto: r.tipo_produto, material: r.material, especificacao: r.especificacao, cor: r.cor, quantidade: r.quantidade || 0, total: r.total || 0,
    pag1: r.pag1 || 0, pag2: r.pag2 || 0, pago_100: !!r.pago_100, forma_pagamento: r.forma_pagamento || '', prazo_entrega: r.prazo_entrega || '', frete: r.frete || '', segmento: r.segmento || '',
  }));
}

// ---------- permissões ----------
export function podeEditarTudo(u) { return GESTAO.has(u?.perfil); }
export const podeLancar = (u) => u?.perfil !== 'consultor';
const dentroDoPrazo = (r) => Date.now() - Date.parse(r.criado_em || 0) < HORAS_EDICAO * 3600e3 && r.origem !== 'planilha';
function bloqueio(u, r, campo) {
  if (podeEditarTudo(u)) return null;
  if (!podeLancar(u)) return 'Seu perfil só consulta os pedidos.';
  if (!ehDoVendedor(u, r)) return 'Esta linha é de outro vendedor: só ele ou a gestão altera.';
  if (CAMPOS_VALOR.includes(campo) && !dentroDoPrazo(r)) return r.origem === 'planilha'
    ? 'Linha importada da planilha: quantidade e valores só a gestão altera. Para acrescentar peças, lance um acréscimo (pedido complementar).'
    : `Passaram ${HORAS_EDICAO} h do lançamento: para acrescentar peças, lance um acréscimo (pedido complementar). Só a gestão altera este campo agora.`;
  return null;
}
// perfil Vendedor: só mexe nas linhas dele (pelo nome na coluna VENDEDOR) ou nas que ele mesmo lançou
export const ehDoVendedor = (u, r) => u?.perfil !== 'vendedor' || r.criado_por_id === u.id || (!!u.vendedor && sem(r.vendedor) === sem(u.vendedor));
const quem = (u) => ({ usuario: u?.nome || 'Sistema', usuario_id: u?.id || '' });

// ---------- leitura ----------
export async function listar() {
  const m = await carregar();
  return [...m.values()].filter((r) => !r.excluido).map((r) => (r.vendedor && r.vendedor !== tituloNome(r.vendedor) ? { ...r, vendedor: tituloNome(r.vendedor) } : r)).sort((a, b) => (a.data || a.mes || '').localeCompare(b.data || b.mes || '') || String(a.codigo).localeCompare(String(b.codigo)) || (a.ordem || 0) - (b.ordem || 0));
}
// códigos usados fora do painel (planilha ligada e números de venda da Conta Azul), para a sequência continuar de onde a planilha parou
let codigosExternos = [];
export const codigosExternosLista = () => [...new Set(codigosExternos)];
// De-para do número da venda na Conta Azul (sem os zeros do começo) para o código do painel:
// 21112026 → 0021112026 · 211120261 → 0021112026-1 (pedido complementar: o sufixo vai colado no fim, porque a Conta Azul só aceita número inteiro)
const RX_BASE_CA = /^(\d{1,4})(0[1-9]|1[0-2])(20[2-3]\d)$/;
export function codigoDeNumeroCA(n) {
  const s = String(n ?? '').replace(/\D/g, '').replace(/^0+/, '');
  if (!s) return '';
  if (RX_BASE_CA.test(s)) return s.padStart(10, '0');
  for (const k of [1, 2]) { const b = s.slice(0, -k), suf = s.slice(-k); if (b && RX_BASE_CA.test(b) && !suf.startsWith('0')) return `${b.padStart(10, '0')}-${suf}`; }
  return s;
}
// código do painel → número da venda na Conta Azul (o inverso do de-para acima)
export const numeroParaCA = (codigo) => Number(chaveCodigo(codigo));
export const definirCodigosExternos = (lista) => { codigosExternos = (lista || []).map((c) => codigoDeNumeroCA(c)).filter(Boolean); };
export function proximoCodigo(data, regs = [...(mem?.values() || [])]) {
  const d = limpar('data', data) || new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10);
  const mm = d.slice(5, 7), aa = d.slice(0, 4);
  let max = 0;
  for (const c of [...regs.map((r) => r.codigo), ...codigosExternos]) { const m = codigoBase(c).match(RX_COD); if (m && m[2] === mm && m[3] === aa) max = Math.max(max, +m[1]); }
  return `${String(max + 1).padStart(4, '0')}${mm}${aa}`;
}
export function proximoComplemento(codigo, regs = [...(mem?.values() || [])]) {
  const base = codigoBase(codigo);
  let k = 0;
  for (const r of regs) { const c = String(r.codigo || ''); if (codigoBase(c) === base && c !== base) { const n = Number(c.slice(base.length).replace(/\D/g, '')); if (n > k) k = n; } }
  return `${base}-${k + 1}`;
}

// ---------- escrita ----------
function novoRegistro(dados, u, extra = {}) {
  const r = { id: crypto.randomUUID(), origem: 'painel' };
  for (const c of Object.keys(CAMPOS)) r[c] = limpar(c, dados[c]);
  const sl = separarLote(r.cliente); if (sl.lote && !r.lote) { r.cliente = sl.cliente; r.lote = sl.lote; }
  if (!r.total && r.quantidade && r.valor_unit) r.total = r2(r.quantidade * r.valor_unit);
  r.mes = (r.data || '').slice(0, 7) || dados.mes || '';
  Object.assign(r, { criado_em: agoraISO(), criado_por: u?.nome || 'Sistema', criado_por_id: u?.id || '', ...extra });
  return r;
}
// cria um pedido (uma ou mais linhas de item com o mesmo código). complemento_de → código "-N"
export async function criarPedido(corpo, u) {
  if (!podeLancar(u)) throw new Error('Seu perfil só consulta os pedidos.');
  await carregar();
  const cab = { ...(corpo?.pedido || {}) }; if (u?.perfil === 'vendedor' && u.vendedor) cab.vendedor = u.vendedor;
  const itens = Array.isArray(corpo?.itens) && corpo.itens.length ? corpo.itens : [{}];
  if (!limpar('cliente', cab.cliente)) throw new Error('Informe o cliente.');
  if (!limpar('data', cab.data)) throw new Error('Informe a data da venda.');
  let codigo = limpar('codigo', cab.codigo);
  const complementoDe = corpo?.complemento_de ? codigoBase(corpo.complemento_de) : '';
  if (complementoDe) codigo = proximoComplemento(complementoDe);
  if (!codigo) codigo = proximoCodigo(cab.data);
  // novo item no mesmo pedido: só nas primeiras 24 h (e só no pedido do próprio vendedor); depois, é pedido complementar
  if (!complementoDe && corpo?.mesmo_pedido && !podeEditarTudo(u)) {
    const doPedido = [...mem.values()].filter((r) => !r.excluido && r.codigo === codigo);
    if (doPedido.some((r) => !ehDoVendedor(u, r))) throw new Error('Este pedido é de outro vendedor: só ele ou a gestão altera.');
    const fechado = (r) => (r.origem === 'planilha' && r.data ? Date.now() - Date.parse(r.data + 'T23:59:59-03:00') > HORAS_EDICAO * 3600e3 : !dentroDoPrazo(r));
    if (doPedido.some(fechado)) throw new Error(`O pedido ${codigo} está fechado (passaram ${HORAS_EDICAO} h). Para acrescentar peças, use o ⊕ (pedido complementar).`);
  }
  if (!complementoDe && !corpo?.mesmo_pedido && [...mem.values()].some((r) => !r.excluido && r.codigo === codigo)) throw new Error(`O código ${codigo} já existe. Para acrescentar peças a ele use "Acréscimo"; para um pedido novo deixe o código em branco (o painel gera o próximo).`);
  const regs = itens.filter((i) => i && (i.tipo_produto || i.quantidade || i.total || i.valor_unit)).map((i, k) => novoRegistro({ ...cab, ...i, codigo }, u, { ordem: k, ...(complementoDe ? { complemento_de: complementoDe } : {}) }));
  if (!regs.length) throw new Error('Inclua pelo menos um item (tipo de produto, quantidade e valor).');
  regs.forEach((r) => mem.set(r.id, r));
  await gravar(regs);
  await registrarLog(regs.map((r) => ({ ...quem(u), acao: complementoDe ? 'complemento' : 'criou', registro: r.id, codigo: r.codigo, cliente: r.cliente,
    mudancas: [{ campo: 'item', antes: '', depois: `${r.quantidade} × ${r.tipo_produto || 'item'} ${[r.material, r.cor].filter(Boolean).join(' ')} = R$ ${r.total.toFixed(2)}` }],
    detalhe: complementoDe ? `Pedido complementar de ${complementoDe}` : null })));
  return regs;
}
export async function alterar(id, mudancas, u) {
  await carregar();
  const r = mem.get(id);
  if (!r || r.excluido) throw new Error('Linha não encontrada (pode ter sido excluída).');
  const log = [], novo = { ...r };
  for (const [c, v] of Object.entries(mudancas || {})) {
    if (!(c in CAMPOS)) continue;
    const val = limpar(c, v);
    if (val === (r[c] ?? (CAMPOS[c] === 'num' ? 0 : ''))) continue;
    const b = bloqueio(u, r, c); if (b) throw new Error(b);
    novo[c] = val; log.push({ campo: c, antes: r[c] ?? '', depois: val });
  }
  if (log.some((x) => x.campo === 'cliente')) { const sl = separarLote(novo.cliente); if (sl.lote) { novo.cliente = sl.cliente; if (!novo.lote) { novo.lote = sl.lote; log.push({ campo: 'lote', antes: r.lote || '', depois: sl.lote }); } } }
  if (log.some((x) => x.campo === 'quantidade' || x.campo === 'valor_unit') && !log.some((x) => x.campo === 'total') && novo.quantidade && novo.valor_unit) {
    const t = r2(novo.quantidade * novo.valor_unit); if (t !== r.total) { novo.total = t; log.push({ campo: 'total', antes: r.total, depois: t }); }
  }
  if (!log.length) return r;
  novo.mes = (novo.data || '').slice(0, 7) || novo.mes;
  Object.assign(novo, { alterado_em: agoraISO(), alterado_por: u?.nome || '' });
  mem.set(id, novo);
  await gravar([novo]);
  await registrarLog([{ ...quem(u), acao: 'alterou', registro: id, codigo: novo.codigo, cliente: novo.cliente, mudancas: log }]);
  return novo;
}
// ---------- alteração de preço depois do pedido fechado: o vendedor pede, a gestão aprova ----------
export async function solicitarAlteracao(id, b, u) {
  await carregar();
  const r = mem.get(id);
  if (!r || r.excluido) throw new Error('Linha não encontrada.');
  if (!podeLancar(u)) throw new Error('Seu perfil só consulta os pedidos.');
  if (!ehDoVendedor(u, r)) throw new Error('Esta linha é de outro vendedor: só ele ou a gestão pede a alteração.');
  if (r.solicitacao?.status === 'pendente') throw new Error('Já existe um pedido de alteração aguardando a gestão nesta linha.');
  const vu = limpar('valor_unit', b?.valor_unit), q = b?.quantidade != null && b.quantidade !== '' ? limpar('quantidade', b.quantidade) : (Number(r.quantidade) || 0);
  if (!(vu > 0)) throw new Error('Informe o novo valor por unidade.');
  const motivo = String(b?.motivo || '').trim().slice(0, 500);
  if (!motivo) throw new Error('Explique o motivo da alteração para a gestão.');
  if (vu === r2(r.valor_unit) && q === (Number(r.quantidade) || 0)) throw new Error('O valor informado é igual ao atual.');
  const s0 = { status: 'pendente', valor_unit_antes: r2(r.valor_unit), valor_unit: vu, quantidade_antes: Number(r.quantidade) || 0, quantidade: q, total_antes: r2(r.total), total: r2(q * vu), motivo, por: u?.nome || '', por_id: u?.id || '', em: agoraISO() };
  const novo = { ...r, solicitacao: s0 };
  mem.set(id, novo); await gravar([novo]);
  await registrarLog([{ ...quem(u), acao: 'solicitou', registro: id, codigo: r.codigo, cliente: r.cliente, mudancas: [{ campo: 'valor_unit', antes: s0.valor_unit_antes, depois: vu }, ...(q !== s0.quantidade_antes ? [{ campo: 'quantidade', antes: s0.quantidade_antes, depois: q }] : []), { campo: 'total', antes: s0.total_antes, depois: s0.total }], detalhe: `Pedido de alteração de preço para a gestão aprovar · ${motivo}` }]);
  return novo;
}
export async function responderSolicitacao(id, b, u) {
  if (!podeEditarTudo(u)) throw new Error('Só a gestão aprova alteração de preço.');
  await carregar();
  const r = mem.get(id);
  if (!r || r.excluido) throw new Error('Linha não encontrada.');
  const s0 = r.solicitacao; if (s0?.status !== 'pendente') throw new Error('Não há pedido de alteração aguardando nesta linha.');
  const obs = String(b?.obs || '').trim().slice(0, 500), aprovar = !!b?.aprovar;
  let atual = r;
  if (aprovar) atual = await alterar(id, { quantidade: s0.quantidade, valor_unit: s0.valor_unit, total: s0.total }, u);
  const fim = { ...s0, status: aprovar ? 'aprovada' : 'recusada', resp_por: u?.nome || '', resp_em: agoraISO(), resp_obs: obs, ...(aprovar && r.ca_venda_id ? { ajustar_ca: true } : {}) };
  const novo = { ...(mem.get(id) || atual), solicitacao: fim, solicitacoes: [...(r.solicitacoes || []), fim].slice(-10) };
  mem.set(id, novo); await gravar([novo]);
  await registrarLog([{ ...quem(u), acao: aprovar ? 'aprovou' : 'recusou', registro: id, codigo: r.codigo, cliente: r.cliente, mudancas: [{ campo: 'valor_unit', antes: s0.valor_unit_antes, depois: aprovar ? s0.valor_unit : `${s0.valor_unit} (recusado)` }], detalhe: `${aprovar ? 'Aprovou' : 'Recusou'} a alteração de preço pedida por ${s0.por}${obs ? ' · ' + obs : ''}${aprovar && r.ca_venda_id ? ' · corrigir o valor na Conta Azul' : ''}` }]);
  return novo;
}
export async function excluir(id, u) {
  await carregar();
  const r = mem.get(id);
  if (!r || r.excluido) throw new Error('Linha não encontrada.');
  if (!podeEditarTudo(u) && !(podeLancar(u) && dentroDoPrazo(r) && r.criado_por_id === u?.id && ehDoVendedor(u, r))) throw new Error(`Só a gestão exclui pedidos depois de ${HORAS_EDICAO} h (ou lançados por outra pessoa).`);
  const novo = { ...r, excluido: true, excluido_em: agoraISO(), excluido_por: u?.nome || '' };
  mem.set(id, novo); await gravar([novo]);
  await registrarLog([{ ...quem(u), acao: 'excluiu', registro: id, codigo: r.codigo, cliente: r.cliente, mudancas: [{ campo: 'item', antes: `${r.quantidade} × ${r.tipo_produto || 'item'} = R$ ${Number(r.total || 0).toFixed(2)}`, depois: '' }] }]);
  return novo;
}
// unifica grafias de cliente (ex.: "Checkpoint 5 anos", "Checkpoint CT" → "Checkpoint")
// Pedido que está só na planilha (enquanto ela estiver em uso): ao alterar ou fazer o complementar no painel,
// o pedido é trazido para o painel (todas as linhas com o mesmo código) e passa a valer a versão do painel.
export async function assumirDaPlanilha(codigo, u) {
  if (!podeLancar(u)) throw new Error('Seu perfil só consulta os pedidos.');
  const k = chaveCodigo(codigo); if (!k) throw new Error('Linha sem código: corrija na planilha.');
  await carregar();
  const ja = [...mem.values()].filter((r) => !r.excluido && chaveCodigo(r.codigo) === k);
  if (ja.length) { await completarComplementares(codigo, u).catch(() => {}); return ja; }
  let fonteP = await linhasDaFonte(null, true);
  if (!fonteP.linhas.some((l) => chaveCodigo(l.codigo_pedido || l.codigo || '') === k)) fonteP = await linhasDaFonte(null);
  if (u?.perfil === 'vendedor') {
    const ls = fonteP.linhas.filter((l) => chaveCodigo(l.codigo_pedido || l.codigo || '') === k);
    if (ls.length && !ls.some((l) => ehDoVendedor(u, { vendedor: l.vendedor }))) throw new Error('Este pedido é de outro vendedor.');
  }
  const base = chaveCodigo(codigoBase(codigo));
  const doPedido = new Set(fonteP.linhas.map((l) => l.codigo_pedido || l.codigo || '').filter((c) => chaveCodigo(codigoBase(c)) === base).map((c) => chaveCodigo(c)));
  doPedido.add(k);
  const r = await importar({ de: '2026-01', ate: '9999-12', modo: 'novas', simular: false, codigos: doPedido, interno: true, fonte: fonteP }, u);
  if (!r.linhas) throw new Error('O pedido não foi encontrado na planilha.');
  return [...mem.values()].filter((x) => !x.excluido && doPedido.has(chaveCodigo(x.codigo)));
}
// Novo × recompra em branco: cliente que já comprou antes (planilha, painel ou Conta Azul) = Recompra; a 1ª compra = Novo.
// Devolve as células da planilha do Google a preencher e preenche também os pedidos do painel.
export async function preencherNovoRecompra(vendasCA = [], u = null) {
  await carregar();
  const k = (n) => sem(clienteBase(n || '')).replace(/[^a-z0-9]+/g, ' ').trim();
  const fonte = await linhasDaFonte(null).catch(() => ({ linhas: [] }));
  const compras = new Map(); // cliente → datas de compra
  const add = (n, d) => { const c = k(n); if (!c || !d) return; (compras.get(c) || compras.set(c, []).get(c)).push(d); };
  fonte.linhas.forEach((l) => add(l.cliente_original || l.cliente, l.data));
  [...mem.values()].filter((r) => !r.excluido).forEach((r) => add(r.cliente, r.data));
  (vendasCA || []).forEach((v) => add(v.c || v.cliente, v.d || v.data));
  const tipo = (n, d) => ((compras.get(k(n)) || []).some((x) => x < d) ? 'recompra' : 'novo');
  const celulas = fonte.linhas.filter((l) => l.linha && l.data && !l.novo_recompra && (l.cliente_original || l.cliente))
    .map((l) => ({ linha: l.linha, campo: 'novo_recompra', valor: tipo(l.cliente_original || l.cliente, l.data) === 'novo' ? 'Novo' : 'Recompra', cliente: l.cliente_original || l.cliente }));
  const mudados = [];
  for (const r of mem.values()) {
    if (r.excluido || r.novo_recompra || !r.cliente || !r.data) continue;
    const n = { ...r, novo_recompra: tipo(r.cliente, r.data), alterado_em: agoraISO(), alterado_por: 'Preenchimento novo × recompra' };
    mem.set(r.id, n); mudados.push(n);
  }
  if (mudados.length) await gravar(mudados);
  return { celulas, painel: mudados.length };
}
// pedido trazido antes desta correção: traz também os complementares que ficaram só na planilha
async function completarComplementares(codigo, u) {
  const base = chaveCodigo(codigoBase(codigo));
  const fonteP = await linhasDaFonte(null);
  const noPainel = new Set([...mem.values()].filter((r) => !r.excluido).map((r) => chaveCodigo(r.codigo)));
  const faltam = new Set(fonteP.linhas.map((l) => l.codigo_pedido || l.codigo || '').filter((c) => chaveCodigo(codigoBase(c)) === base && !noPainel.has(chaveCodigo(c))).map((c) => chaveCodigo(c)));
  if (faltam.size) await importar({ de: '2026-01', ate: '9999-12', modo: 'novas', simular: false, codigos: faltam, interno: true }, u);
}
// envio à Conta Azul: guarda o resultado em cada linha do pedido (sem mexer em "alterado_em", que é edição de quem lança)
export async function marcarEnvioCA(ids, campos, u) {
  await carregar();
  const mudados = [];
  for (const id of ids) { const r = mem.get(id); if (!r) continue; const n = { ...r, ...campos }; mem.set(id, n); mudados.push(n); }
  await gravar(mudados);
  if (campos.ca_venda_id && campos.ca_venda_id !== 'ja-existia') await registrarLog([{ ...quem(u), acao: 'enviou', codigo: mudados[0]?.codigo || null, cliente: mudados[0]?.cliente || '', mudancas: [{ campo: 'conta_azul', antes: '', depois: 'venda criada na Conta Azul (em andamento)' }], detalhe: `${mudados.length} ${mudados.length === 1 ? 'item' : 'itens'}` }]).catch(() => {});
  return mudados.length;
}
export async function unificarCliente(de, para, u) {
  if (!podeLancar(u)) throw new Error('Seu perfil só consulta os pedidos.');
  para = limpar('cliente', para); const nomes = new Set((Array.isArray(de) ? de : [de]).map((x) => sem(x)).filter(Boolean));
  if (!para || !nomes.size) throw new Error('Informe os nomes a unificar e o nome certo.');
  await carregar();
  const mudados = [];
  for (const r of mem.values()) if (!r.excluido && nomes.has(sem(r.cliente)) && r.cliente !== para && ehDoVendedor(u, r)) { const n = { ...r, cliente: para, cliente_lancado: r.cliente_lancado || r.cliente, lote: juntarObs(r.lote, restoDoNome(r.cliente, para)), alterado_em: agoraISO(), alterado_por: u?.nome || '' }; mem.set(r.id, n); mudados.push([r, n]); }
  await gravar(mudados.map((x) => x[1]));
  await registrarLog([{ ...quem(u), acao: 'unificou', codigo: null, cliente: para, mudancas: [{ campo: 'cliente', antes: [...new Set(mudados.map((x) => x[0].cliente))].join(' · '), depois: para }], detalhe: `${mudados.length} linhas` }]);
  return { linhas: mudados.length };
}

// ---------- importação da base (planilha conectada ou arquivo .xlsx) ----------
async function linhasDaFonte(bytes, recente = false) {
  if (bytes) return { linhas: lerXlsx(bytes).linhas, origem: 'arquivo' };
  if (config.demo) return { linhas: gerarDemoPlanilha().linhas, origem: 'demonstração' };
  if (!planilhaConfigurada()) throw new Error('A planilha não está conectada. Ligue a planilha em Controle → Planilha × sistema (mês) → Ligar pelo meu e-mail, ou envie o arquivo .xlsx.');
  return { linhas: (await (recente ? lerPlanilhaRecente() : lerPlanilha())).linhas, origem: 'planilha conectada' };
}
const chaveLinhaImport = (o) => [chaveCodigo(o.codigo_pedido || o.codigo || ''), o.data || '', sem(clienteBase(o.cliente_original || o.cliente || '')), sem(o.tipo_produto), sem(o.cor), Number(o.quantidade) || 0, Math.round((Number(o.total) || 0) * 100)].join('|');
export async function importar({ de = '2026-01', ate = '9999-12', modo = 'novas', simular = true, bytes = null, nomeArquivo = '', codigos = null, interno = false, fonte: fontePronta = null }, u) {
  if (!interno && !podeEditarTudo(u)) throw new Error('Só a gestão importa a base.');
  await carregar();
  const fonte = fontePronta || await linhasDaFonte(bytes);
  let noPeriodo = fonte.linhas.filter((l) => l.mes && l.mes >= de && l.mes <= ate && (l.total || l.quantidade));
  if (codigos) noPeriodo = noPeriodo.filter((l) => codigos.has(chaveCodigo(l.codigo_pedido || l.codigo || '')));
  // "só as linhas novas": compara cada linha da planilha com o que já está no painel (código, data, cliente, produto, cor, qtd e total)
  const chaveLinha = (o) => [chaveCodigo(o.codigo_pedido || o.codigo || ''), o.data || '', sem(clienteBase(o.cliente_original || o.cliente_lancado || o.cliente || '')), sem(o.tipo_produto), sem(o.cor), Number(o.quantidade) || 0, Math.round((Number(o.total) || 0) * 100)].join('|');
  let jaTem = null;
  if (modo === 'novas') {
    jaTem = new Map();
    for (const r of mem.values()) if (!r.excluido && r.mes >= de && r.mes <= ate && r.chave_origem) jaTem.set(r.chave_origem, (jaTem.get(r.chave_origem) || 0) + 1);
    for (const r of mem.values()) if (!r.excluido && r.mes >= de && r.mes <= ate && !r.chave_origem) { const k = chaveLinha({ ...r, cliente_original: r.cliente_lancado || [r.cliente, r.lote].filter(Boolean).join(' ') }); jaTem.set(k, (jaTem.get(k) || 0) + 1); const k2 = chaveLinha({ ...r, cliente_original: r.cliente }); if (k2 !== k) jaTem.set(k2, (jaTem.get(k2) || 0) + 1); }
    const novas = [];
    for (const l of noPeriodo) { const k = chaveLinha(l); if (jaTem.get(k) > 0) jaTem.set(k, jaTem.get(k) - 1); else novas.push(l); }
    noPeriodo.novas = novas;
  }
  const meses = [...new Set(noPeriodo.map((l) => l.mes))].sort();
  const existentes = [...mem.values()].filter((r) => !r.excluido && r.origem === 'planilha');
  const porMes = Object.fromEntries(meses.map((m) => {
    const ja = existentes.filter((r) => r.mes === m);
    return [m, { planilha: noPeriodo.filter((l) => l.mes === m).length, novas: noPeriodo.novas ? noPeriodo.novas.filter((l) => l.mes === m).length : null, no_painel: ja.length, corrigidas: ja.filter((r) => r.alterado_em).length, lancadas_no_painel: [...mem.values()].filter((r) => !r.excluido && r.origem === 'painel' && r.mes === m).length }];
  }));
  const alvo = modo === 'substituir' ? meses : modo === 'novas' ? meses.filter((m) => porMes[m].novas) : meses.filter((m) => !porMes[m].no_painel);
  const aImportar = modo === 'novas' ? noPeriodo.novas : noPeriodo.filter((l) => alvo.includes(l.mes));
  const resumo = { fonte: fonte.origem, arquivo: nomeArquivo || null, de, ate, modo, meses: porMes, importar_meses: alvo, linhas: aImportar.length,
    perde_correcoes: modo === 'substituir' ? alvo.reduce((s, m) => s + porMes[m].corrigidas, 0) : 0 };
  if (simular) return resumo;
  const quando = agoraISO();
  const remover = modo === 'substituir' ? existentes.filter((r) => alvo.includes(r.mes)) : [];
  remover.forEach((r) => mem.delete(r.id));
  await apagarDefinitivo(remover.map((r) => r.id));
  const novos = aImportar.map((l, k) => {
    const sl = separarLote(l.cliente_original);
    const r = { id: crypto.randomUUID(), origem: 'planilha', linha_planilha: l.linha || null, importado_em: quando, ordem: k,
      criado_em: quando, criado_por: `Importação (${fonte.origem})`, criado_por_id: u?.id || '', cliente_lancado: l.cliente_original || '' };
    const v = { data: l.data, codigo: l.codigo_pedido || l.codigo || (l.pedido_informado && !String(l.pedido).includes('|') ? l.pedido : ''), cliente: l.cliente && l.cliente !== 'Sem cliente' ? l.cliente : sl.cliente, lote: sl.lote,
      nome_pedido: l.nome_pedido, vendedor: l.vendedor === 'Sem vendedor' ? '' : l.vendedor, tipo_venda: l.tipo_venda === '—' ? '' : l.tipo_venda, novo_recompra: l.novo_recompra, segmento: l.segmento,
      tipo_produto: l.tipo_produto, material: l.material, especificacao: l.especificacao, cor: l.cor, quantidade: l.quantidade, valor_unit: l.valor_unit || (l.quantidade ? l.total / l.quantidade : 0), total: l.total,
      pag1: l.pag1 > 1 ? l.pag1 : 0, pag2: l.pag2 > 1 ? l.pag2 : 0, pago_100: l.pago_100, prazo_entrega: l.prazo_entrega, forma_pagamento: l.forma_pagamento, frete: l.frete, pagador: l.pagador, observacao: l.observacao };
    for (const c of Object.keys(CAMPOS)) r[c] = limpar(c, v[c]);
    r.mes = l.mes; if (l.duplicado) r.possivel_duplicado = true;
    r.chave_origem = chaveLinhaImport(l);
    return r;
  });
  novos.forEach((r) => mem.set(r.id, r));
  await gravar(novos);
  await registrarLog([{ ...quem(u), acao: 'importou', detalhe: `${novos.length} linhas de ${alvo.map((m) => m.split('-').reverse().join('/')).join(', ') || 'nenhum mês'} (${fonte.origem}${nomeArquivo ? ': ' + nomeArquivo : ''}; ${modo === 'substituir' ? `substituiu ${remover.length} linhas` : modo === 'novas' ? 'só as linhas novas' : 'só meses que faltavam'})`, mudancas: [] }]);
  return { ...resumo, importadas: novos.length, removidas: remover.length };
}

// ---------- pagamentos da Conta Azul (1º e 2º pagamento pelo código do pedido) ----------
const pag = { quando: 0, dados: null, carregando: null, baixas: null, fila: Promise.resolve(), pendentes: 0 };
async function cacheBaixas() { if (!pag.baixas) pag.baixas = (await lerKV('baixas_parcelas').catch(() => null)) || {}; return pag.baixas; }
function agendarBaixas(parcelas) {
  const c = pag.baixas;
  const faltam = parcelas.filter((p) => p.pago > 0 && !c[p.id] && !String(p.id).startsWith('pc-')).slice(0, 300);
  for (const p of faltam) {
    c[p.id] = { buscando: true }; pag.pendentes++;
    pag.fila = pag.fila.then(async () => {
      try { c[p.id] = { b: await ca.buscarBaixasParcela(p.id), em: agoraISO() }; }
      catch { c[p.id] = { b: [], erro: 1, em: agoraISO() }; }
      finally { if (--pag.pendentes % 20 === 0) salvarKV('baixas_parcelas', Object.fromEntries(Object.entries(c).filter(([, x]) => !x.buscando))).catch(() => {}); }
    });
  }
}
// vendasCA: vendas da Conta Azul já carregadas pelo painel (com o número da venda = código do pedido)
function comBaixas(d) {
  if (!d) return d;
  const por = {};
  for (const [k, ps] of Object.entries(d.por_codigo)) por[k] = ps.map((p) => (p.baixas?.length || !pag.baixas?.[p.id]?.b?.length ? p : { ...p, baixas: pag.baixas[p.id].b }));
  return { ...d, por_codigo: por, buscando_baixas: pag.pendentes };
}
export async function pagamentosPorPedido(vendasCA, forcar = false) {
  if (pag.dados && !forcar && Date.now() - pag.quando < 10 * 60e3) return comBaixas(pag.dados);
  if (pag.carregando) return pag.carregando;
  pag.carregando = (async () => {
    const vendas = (vendasCA || []).filter((v) => v.numero != null);
    const porNumero = new Map(vendas.map((v) => [chaveCodigo(v.numero), v]));
    let parcelas = [];
    if (config.demo) parcelas = gerarDemoParcelas(vendas);
    else if ((await ca.statusConexao()).conectado) {
      const hoje = new Date();
      parcelas = await ca.buscarParcelas('receber', { vencimento_de: new Date(hoje.getTime() - 460 * 864e5).toISOString().slice(0, 10), vencimento_ate: new Date(hoje.getTime() + 400 * 864e5).toISOString().slice(0, 10) });
      await cacheBaixas();
    }
    const out = {}, usadas = new Set(), item = (p, como) => ({ id: p.id, venc: p.vencimento, valor: r2(p.total), pago: r2(p.pago), aberto: r2(p.aberto), status: p.status, desc: p.descricao, como,
      baixas: p.baixas?.length ? p.baixas : pag.baixas?.[p.id]?.b?.length ? pag.baixas[p.id].b : p.data_pagamento ? [{ data: p.data_pagamento, conta: p.conta || '', forma: '', valor: r2(p.pago) }] : [] });
    // 1) a parcela traz o número da venda na descrição (ex.: "Venda 30102026 - parcela 1/2")
    for (const p of parcelas) {
      const k = (String(p.descricao || '').match(/\d{5,}/g) || []).map(chaveCodigo).find((n) => porNumero.has(n)); if (!k) continue;
      (out[k] ||= []).push(item(p, 'número da venda')); usadas.add(p.id);
    }
    // 2) sem o número: mesmo cliente, vencimento até 150 dias depois da venda e parcelas que somam o valor da venda
    const livres = new Map();
    for (const p of parcelas) { if (usadas.has(p.id)) continue; const c = sem(clienteBase(p.pessoa)); if (!c) continue; (livres.get(c) || livres.set(c, []).get(c)).push(p); }
    for (const [k, v] of porNumero) {
      if (out[k] || !['APROVADO', 'FATURADO'].includes(v.situacao)) continue;
      const cand = (livres.get(sem(clienteBase(v.cliente))) || []).filter((p) => !usadas.has(p.id) && p.vencimento >= v.data.slice(0, 10) && Date.parse(p.vencimento) - Date.parse(v.data) <= 150 * 864e5).sort((a, b) => a.vencimento.localeCompare(b.vencimento));
      for (let ini = 0; ini < cand.length && !out[k]; ini++) { let soma = 0; for (let fim = ini; fim < Math.min(cand.length, ini + 4); fim++) { soma += cand[fim].total; if (Math.abs(soma - v.total) <= 1) { const g = cand.slice(ini, fim + 1); out[k] = g.map((p) => item(p, 'cliente e valor')); g.forEach((p) => usadas.add(p.id)); break; } if (soma > v.total + 1) break; } }
    }
    for (const k of Object.keys(out)) out[k].sort((a, b) => a.venc.localeCompare(b.venc));
    // data da baixa e banco: só das parcelas que pertencem a pedidos
    if (!config.demo) agendarBaixas(parcelas.filter((p) => usadas.has(p.id)));
    pag.dados = { por_codigo: out, atualizado_em: agoraISO(), parcelas_lidas: parcelas.length, conectado: config.demo || parcelas.length > 0 };
    pag.quando = Date.now();
    return comBaixas(pag.dados);
  })().finally(() => { pag.carregando = null; });
  return pag.carregando;
}

// ---------- preenche 1º/2º pagamento em branco com o que já foi baixado na Conta Azul ----------
// Só completa campos vazios (nunca troca um valor digitado). Vale para a primeira linha de cada pedido, como na planilha.
export async function preencherPagamentos(pagamentos, u, { auto = false } = {}) {
  await carregar();
  const por = pagamentos?.por_codigo || {}, grupos = new Map();
  for (const r of mem.values()) if (!r.excluido && r.codigo) (grupos.get(chaveCodigo(r.codigo)) || grupos.set(chaveCodigo(r.codigo), []).get(chaveCodigo(r.codigo))).push(r);
  const mudou = [], log = [];
  for (const [k, regs] of grupos) {
    const ps = por[k]; if (!ps?.length) continue;
    regs.sort((a, b) => (a.ordem || 0) - (b.ordem || 0) || String(a.id).localeCompare(String(b.id)));
    const r0 = { ...regs[0] }, ch = [];
    const set = (c, v) => { if (v === '' || v == null || v === 0) return; if (r0[c] && !(CAMPOS[c] === 'num' && !+r0[c])) return; ch.push({ campo: c, antes: r0[c] ?? '', depois: v }); r0[c] = v; };
    [0, 1].forEach((i) => { const p = ps[i]; if (!p || !(p.pago > 0)) return; const b = p.baixas?.[0]; const antes = ch.length; set(i ? 'pag2' : 'pag1', r2(p.pago)); if (ch.length > antes) r0.pag_ca = [...new Set([...(r0.pag_ca || []), i + 1])]; if (b?.data) set(i ? 'data_pag2' : 'data_pag1', b.data); if (b?.conta) set('banco_pag', b.conta); if (b?.forma) set('forma_pagamento', b.forma); });
    { const resto = ps.slice(2).filter((p) => p.pago > 0); if (resto.length) { const antes = ch.length; set('pag3', r2(resto.reduce((a, p) => a + p.pago, 0))); if (ch.length > antes) r0.pag_ca = [...new Set([...(r0.pag_ca || []), 3])]; } }
    const total = regs.reduce((s2, r) => s2 + (+r.total || 0), 0), recebido = ps.reduce((s2, p) => s2 + (+p.pago || 0), 0), quitado = ps.every((p) => !(p.aberto > 0.01)) && Math.abs(recebido - total) <= 1;
    const marcar = quitado ? regs.filter((r) => !r.pago_100) : [];
    if (ch.length) { Object.assign(r0, { alterado_em: agoraISO(), alterado_por: auto ? 'Conta Azul (automático)' : u?.nome || '' }); mem.set(r0.id, r0); mudou.push(r0); log.push({ registro: r0.id, codigo: r0.codigo, cliente: r0.cliente, mudancas: ch }); }
    for (const r of marcar) { const n = { ...(mem.get(r.id)), pago_100: true, alterado_em: agoraISO(), alterado_por: auto ? 'Conta Azul (automático)' : u?.nome || '' }; mem.set(r.id, n); if (!mudou.includes(n)) mudou.push(n); log.push({ registro: r.id, codigo: r.codigo, cliente: r.cliente, mudancas: [{ campo: 'pago_100', antes: false, depois: true }] }); }
  }
  if (!mudou.length) return { linhas: 0, pedidos: 0 };
  await gravar(mudou);
  await registrarLog(log.map((e) => ({ usuario: auto ? 'Conta Azul (automático)' : u?.nome || 'Sistema', usuario_id: auto ? '' : u?.id || '', acao: 'alterou', ...e, detalhe: 'Pagamento preenchido pela Conta Azul' })));
  return { linhas: mudou.length, pedidos: new Set(log.map((e) => e.codigo)).size };
}

// ---------- recebimentos para gravar na planilha do Google (só onde a planilha está em branco) ----------
const dataBR = (d) => (d ? String(d).slice(0, 10).split('-').reverse().join('/') : '');
export function itensParaPlanilha(pagamentos, linhasPlanilha, ate = '9999-12') {
  const por = pagamentos?.por_codigo || {}, grupos = new Map();
  for (const l of linhasPlanilha || []) { if ((l.mes || '') > ate) continue; const c = l.codigo_pedido || l.codigo || (l.pedido_informado && !String(l.pedido).includes('|') ? l.pedido : ''); if (!c) continue; const k = chaveCodigo(c); (grupos.get(k) || grupos.set(k, { codigo: c, ls: [] }).get(k)).ls.push(l); }
  const itens = [];
  for (const [k, g] of grupos) {
    const ps = por[k]; if (!ps?.length) continue;
    // a nota fica igual ao balão do painel: só deste pedido, deste cliente e desta parcela
    const brl = (v) => 'R$ ' + Number(v || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const cli = (g.ls.find((l) => l.cliente_original || l.cliente) || {}), nomeCli = cli.cliente_original || cli.cliente || '';
    const cabNota = `Pedido ${g.codigo}${nomeCli ? ' · ' + nomeCli : ''}` + (g.ls.length > 1 ? `\n${g.ls.length} itens neste pedido (linhas da planilha): o valor é do pedido inteiro` : '');
    const nota = (p, i) => { const b = p.baixas?.[0]; return [`${i + 1}º pagamento · recebido`, cabNota, '', `Parcela ${i + 1} de ${ps.length}: ${brl(p.valor)}`, `Vencimento: ${dataBR(p.venc)}`, `Recebido: ${brl(p.pago)}${b?.data ? ' em ' + dataBR(b.data) : ''}`, b?.conta ? `Banco: ${b.conta}` : '', b?.forma ? `Forma: ${b.forma}` : '', '', '(Conta Azul · Painel de Gestão)'].filter((x, k, a) => x !== '' || (a[k - 1] && a[k - 1] !== '')).join('\n'); };
    const nota100 = () => { const rec = ps.reduce((s2, p) => s2 + (+p.pago || 0), 0); return ['Pagamentos do pedido · quitado', cabNota, '', `Total do pedido: ${brl(g.ls.reduce((s2, l) => s2 + (+l.total || 0), 0))}`, `Recebido: ${brl(rec)}`, '', ...ps.map((p, i) => { const b = p.baixas?.[0]; return `${i + 1}ª parcela · vence ${dataBR(p.venc)} · ${brl(p.valor)} · pago${b?.data ? ' ' + dataBR(b.data) : ''}${b?.conta ? ' · ' + b.conta : ''}${b?.forma ? ' · ' + b.forma : ''}`; }), '', '(Conta Azul · Painel de Gestão)'].join('\n'); };
    const temP1 = g.ls.some((l) => +l.pag1 > 1), temP2 = g.ls.some((l) => +l.pag2 > 1);
    const it = { codigo: g.codigo };
    if (!temP1 && ps[0]?.pago > 0) { it.pag1 = r2(ps[0].pago); it.nota1 = nota(ps[0], 0); }
    if (!temP2 && ps[1]?.pago > 0) { it.pag2 = r2(ps[1].pago); it.nota2 = nota(ps[1], 1); }
    const fb = ps.find((p) => p.baixas?.[0]?.forma)?.baixas[0].forma; if (fb && !g.ls.some((l) => l.forma_pagamento)) it.forma = fb;
    const total = g.ls.reduce((s2, l) => s2 + (+l.total || 0), 0), rec = ps.reduce((s2, p) => s2 + (+p.pago || 0), 0);
    if (!g.ls.every((l) => l.pago_100) && ps.every((p) => !(p.aberto > 0.01)) && Math.abs(rec - total) <= 1) { it.pago100 = true; it.nota100 = nota100(); }
    if (it.pag1 || it.pag2 || it.pago100 || it.forma) itens.push(it);
  }
  return itens;
}
export async function logPlanilha(u, itens, resp) {
  const feitos = new Set(resp?.codigos || []);
  await registrarLog(itens.filter((i) => feitos.has(i.codigo)).map((i) => ({ usuario: u ? u.nome : 'Conta Azul (automático)', usuario_id: u?.id || '', acao: 'alterou', codigo: i.codigo, cliente: '',
    mudancas: [i.pag1 && { campo: 'pag1', antes: '', depois: i.pag1 }, i.pag2 && { campo: 'pag2', antes: '', depois: i.pag2 }, i.pago100 && { campo: 'pago_100', antes: false, depois: true }].filter(Boolean), detalhe: 'Gravado na planilha do Google' })));
}
