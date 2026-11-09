// Base de vendas do painel.
// Fonte comercial (FONTE_VENDAS): "auto" (padrão) usa a planilha quando ligada e a Conta Azul quando não.
// A Conta Azul também alimenta a conciliação "planilha x sistema" mês a mês.
import { config } from './config.js';
import * as ca from './contaAzul.js';
import { planilhaConfigurada, lerPlanilha, sem, clienteBase } from './planilha.js';
import { gerarDemoPlanilha, gerarDemoContaAzul } from './demo.js';
import { lerAtributos } from './produtos.js';
import { lerKV, salvarKV } from './tokenStore.js';
import { fontePainel, fonteMista, planilhaEmUso, linhasDoPainel, prepararFonte, chaveCodigo, restoDoNome } from './pedidos.js';

const chave = (s) => sem(s).replace(/[^a-z0-9]+/g, ' ').trim();
// nome de vendedor num padrão só: "DANIEL SILVA", "daniel silva" e "Daniel Silva" viram "Daniel Silva"
const MINUSC_NOME = new Set(['da', 'de', 'do', 'das', 'dos', 'e']);
export const tituloNome = (t) => String(t ?? '').trim().replace(/\s+/g, ' ').toLowerCase().split(' ').map((w, i) => (i > 0 && MINUSC_NOME.has(w) ? w : w.replace(/^(\p{L})/u, (m) => m.toUpperCase()))).join(' ');
const iso = (d) => d.toISOString().slice(0, 10);
const hojeBR = () => new Date(Date.now() - 3 * 3600e3);

// ---------- faixas de comissão (seção 3 da especificação) ----------
// Regra conhecida: 1% a partir de R$ 15 mil no mês e 5% a partir de R$ 50 mil, sem teto. As faixas intermediárias
// ainda serão confirmadas com a Visu; o ADM cadastra no painel (chave comissao_faixas).
// Política de Premiação por Performance – Visu 2026 (atualizada em 23/10/2026): piso R$ 15.000 a 1%,
// +0,25 p.p. a cada R$ 2.187,50, até 5% a partir de R$ 50.000 (sem teto de valor).
export const FAIXAS_PADRAO = () => Array.from({ length: 17 }, (_, k) => ({ de: Math.round((15000 + 2187.5 * k) * 100) / 100, pct: Math.round((1 + 0.25 * k) * 100) / 100 }));
export async function faixasComissao() {
  const kv = await lerKV('comissao_faixas').catch(() => null);
  return Array.isArray(kv?.faixas) && kv.faixas.length ? kv.faixas : FAIXAS_PADRAO();
}

// ---------- padronização de grafias ----------
function padronizar(linhas, campo) {
  const grupos = new Map();
  for (const l of linhas) {
    if (!l[campo]) continue;
    const k = chave(l[campo]);
    const g = grupos.get(k) || new Map();
    g.set(l[campo], (g.get(l[campo]) || 0) + 1);
    grupos.set(k, g);
  }
  const canonico = new Map();
  const variacoes = [];
  for (const [k, g] of grupos) {
    const ord = [...g.entries()].sort((a, b) => b[1] - a[1]);
    canonico.set(k, campo === 'vendedor' && !/^(sem vendedor|nao vendedores)$/.test(k) ? tituloNome(ord[0][0]) : ord[0][0].trim());
    if (ord.length > 1) variacoes.push({ valor: ord[0][0].trim(), grafias: ord.map(([t, n]) => ({ texto: t, linhas: n })) });
  }
  for (const l of linhas) if (l[campo]) l[campo] = canonico.get(chave(l[campo]));
  return variacoes.sort((a, b) => b.grafias.length - a.grafias.length);
}

function qualidade(linhas, mapa) {
  const porChave = new Map();
  for (const l of linhas) {
    const k = chave(l.cliente);
    const g = porChave.get(k) || new Map();
    g.set(l.cliente_original, (g.get(l.cliente_original) || 0) + 1);
    porChave.set(k, g);
  }
  const clientesDuplicados = [...porChave.values()]
    .filter((g) => g.size > 1)
    .map((g) => {
      const ord = [...g.entries()].sort((a, b) => b[1] - a[1]);
      return { cliente: clienteBase(ord[0][0]), grafias: ord.map(([t, n]) => ({ texto: t, linhas: n })) };
    })
    .sort((a, b) => b.grafias.length - a.grafias.length);
  for (const l of linhas) {
    const g = porChave.get(chave(l.cliente));
    if (g && g.size > 1) l.cliente = clienteBase([...g.entries()].sort((a, b) => b[1] - a[1])[0][0]);
    // o lote que estava no nome vai para a coluna Lote / obs. do cliente
    const lt = String(l.cliente_original || '').match(/\b(lote\s*\d+)\)?\s*$/i);
    if (lt && !l.lote) l.lote = lt[1].replace(/\s+/g, ' ').replace(/^l/, 'L');
    // e o que diferencia a venda depois do nome (ex.: "(Dental Center)") também
    if (!l.lote && l.cliente_original && l.cliente_original !== l.cliente) { const r = restoDoNome(l.cliente_original, l.cliente); if (r) l.lote = r; }
  }
  const vazio = (c) => linhas.filter((l) => !l[c]).length;
  return {
    total_linhas: linhas.length,
    clientes_duplicados: clientesDuplicados,
    variacoes: {
      tipo_produto: padronizar(linhas, 'tipo_produto'),
      material: padronizar(linhas, 'material'),
      cor: padronizar(linhas, 'cor'),
      vendedor: padronizar(linhas, 'vendedor'),
    },
    faltando: {
      data: linhas.filter((l) => !l.data && !l.mes).length,
      // o cód. interno só passou a existir em setembro/2026
      pedido: linhas.filter((l) => !l.pedido_informado && (l.mes || '') >= '2026-09').length,
      vendedor: linhas.filter((l) => !l.vendedor || l.vendedor === 'Sem vendedor').length,
      novo_recompra: vazio('novo_recompra'),
      tipo_produto: vazio('tipo_produto'),
      material: vazio('material'),
      cor: vazio('cor'),
      quantidade: linhas.filter((l) => !l.quantidade).length,
      total: linhas.filter((l) => !l.total).length,
    },
    colunas: mapa,
  };
}

// ---------- Conta Azul ----------
const itensCache = { dados: null, pendentes: 0, fila: Promise.resolve(), desdeGravacao: 0, versao: 0 };

async function carregarCacheItens() {
  if (!itensCache.dados) itensCache.dados = (await lerKV('itens_vendas')) || {};
  return itensCache.dados;
}

// busca os itens das vendas aos poucos (limite da API: ~50 chamadas/min), das mais recentes para as mais antigas
function agendarItens(vendas) {
  const cache = itensCache.dados;
  const faltam = vendas
    .filter((v) => v.id && (!cache[v.id] || cache[v.id].v !== v.versao) && !cache[v.id]?.buscando)
    .sort((a, b) => b.data.localeCompare(a.data))
    .slice(0, config.maxVendasComItens);
  for (const v of faltam) {
    cache[v.id] = { ...(cache[v.id] || {}), buscando: true };
    itensCache.pendentes++;
    itensCache.fila = itensCache.fila.then(async () => {
      try {
        const itens = await ca.buscarItensDaVenda(v.id);
        cache[v.id] = { v: v.versao, i: itens.map((x) => [x.nome, x.quantidade, Math.round(x.total * 100) / 100, x.descricao, Math.round((x.custo || 0) * 100) / 100]) };
        itensCache.versao++;
      } catch {
        delete cache[v.id];
      } finally {
        itensCache.pendentes--;
        if (++itensCache.desdeGravacao >= 20 || itensCache.pendentes === 0) {
          itensCache.desdeGravacao = 0;
          salvarKV('itens_vendas', Object.fromEntries(Object.entries(cache).filter(([, x]) => !x.buscando))).catch(() => {});
        }
      }
    });
  }
}

// Leitura incremental (09/11/2026): o histórico completo da Conta Azul é lido uma vez por dia (ou quando o servidor reinicia);
// nas outras atualizações só lê do mês anterior em diante e junta com o que já estava em memória.
let completoEm = 0;
async function vendasContaAzul(anterior = null) {
  const agora = hojeBR();
  const inicioTotal = iso(new Date(Date.UTC(agora.getUTCFullYear(), agora.getUTCMonth() - (config.mesesHistorico + 12), 1)));
  const fim = iso(agora);
  const hojeStr = fim;
  const parcial = anterior?.length && completoEm && iso(new Date(completoEm)) === hojeStr;
  const inicio = parcial ? iso(new Date(Date.UTC(agora.getUTCFullYear(), agora.getUTCMonth() - 1, 1))) : inicioTotal;
  if (parcial) {
    const novas = await ca.buscarVendas(inicio, fim);
    try { const r = await ca.vendedorPorVenda(inicio, fim); novas.forEach((v) => { if (r.mapa.has(v.id)) v.vendedor = r.mapa.get(v.id); }); } catch (e) { console.warn('[vendedores]', e.message); }
    const vendas = [...anterior.filter((v) => (v.data || '') < inicio), ...novas];
    return { vendas, vendedores: cache.bruto?.vendedoresCA || [], parcial: true };
  }
  completoEm = Date.now();
  const vendas = await ca.buscarVendas(inicio, fim);
  let vendedores = [];
  try {
    const r = await ca.vendedorPorVenda(inicio, fim);
    vendedores = r.vendedores;
    vendas.forEach((v) => { if (r.mapa.has(v.id)) v.vendedor = r.mapa.get(v.id); });
  } catch (e) { console.warn('[vendedores]', e.message); }
  return { vendas, vendedores };
}

const EFETIVAS = new Set(['APROVADO', 'FATURADO']);

const MESES_NOME = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];
const nomeMesCurto = (m) => { const i = +m.slice(5) - 2; return i >= 0 ? `${MESES_NOME[i]}/${m.slice(0, 4)}` : `dezembro/${+m.slice(0, 4) - 1}`; };
// Na Conta Azul da Visu, cada mês até julho/2026 entrou como um lançamento único ("Visu"): esses meses só servem
// para o faturamento. Pedido, ticket, cliente e novo × recompra só são confiáveis a partir de DETALHE_CA_DESDE.
export const detalheCaDesde = () => process.env.DETALHE_CA_DESDE || '2026-08';
function linhasDeVendasCA(vendas, cacheItens) {
  const desde = detalheCaDesde();
  const efetivas = vendas.filter((v) => EFETIVAS.has(v.situacao)).sort((a, b) => a.data.localeCompare(b.data));
  // recompra = cliente que já comprou num mês anterior DENTRO do período detalhado; o resto fica sem classificação
  // (pode ser novo ou cliente antigo que não aparece na Conta Azul). O dado certo vem da planilha (BASE TRATADA).
  const primeiroMes = new Map();
  for (const v of efetivas) { if (v.data.slice(0, 7) < desde) continue; const k = chave(clienteBase(v.cliente)); if (!primeiroMes.has(k)) primeiroMes.set(k, v.data.slice(0, 7)); }
  const linhas = [];
  let comItens = 0;
  for (const v of efetivas) {
    const mes = v.data.slice(0, 7), consolidado = mes < desde;
    const pm = primeiroMes.get(chave(clienteBase(v.cliente)));
    const base = {
      data: v.data, mes, cliente: consolidado ? 'Vendas consolidadas do mês' : clienteBase(v.cliente), cliente_original: v.cliente,
      pedido: consolidado ? `consolidado-${mes}` : String(v.numero ?? v.id), pedido_informado: !consolidado, vendedor: consolidado ? 'Não vendedores' : v.vendedor || 'Sem vendedor', tipo_venda: '—',
      novo_recompra: !consolidado && pm && pm < mes ? 'recompra' : '', consolidado,
      pag1: 0, pag2: 0, pago_100: false, forma_pagamento: '', prazo_entrega: '', frete: '', segmento: '',
    };
    const itens = cacheItens[v.id]?.i;
    if (itens?.length && !consolidado) {
      comItens++;
      const soma = itens.reduce((s, x) => s + x[2], 0) || 1;
      const fator = v.total ? v.total / soma : 1; // distribui desconto/frete proporcionalmente
      for (const [nome, q, t, desc, custo] of itens) {
        linhas.push({ ...base, ...lerAtributos(nome, desc), produto: nome, quantidade: q, total: t * fator, custo: custo || 0 });
      }
    } else {
      linhas.push({ ...base, tipo_produto: '', material: '', especificacao: '', cor: '', produto: '', quantidade: 0, total: v.total });
    }
  }
  const det = efetivas.filter((v) => v.data.slice(0, 7) >= desde);
  return { linhas, cobertura_itens: det.length ? comItens / det.length : 1, historico_desde: efetivas[0]?.data || null, detalhe_desde: desde };
}

// ---------- conciliação planilha x Conta Azul ----------
function resumoMensalCA(vendas) {
  const m = {};
  for (const v of vendas) {
    const k = v.data.slice(0, 7);
    m[k] ||= { APROVADO: { t: 0, n: 0 }, FATURADO: { t: 0, n: 0 }, EM_ANDAMENTO: { t: 0, n: 0 }, ORCAMENTO: { t: 0, n: 0 }, CANCELADO: { t: 0, n: 0 }, OUTROS: { t: 0, n: 0 } };
    const g = m[k][v.situacao] || m[k].OUTROS;
    g.t += v.total; g.n++;
  }
  return m;
}

const cache = { dados: null, bruto: null, quando: 0, versaoItens: -1, carregando: null };

// parte cara: chamadas à Conta Azul e leitura da planilha
async function buscarFontes() {
  const avisos = [];
  const conectadoCA = !config.demo && (await ca.statusConexao()).conectado;
  const fonteCfg = (process.env.FONTE_VENDAS || 'auto').toLowerCase();
  let origem, base;
  let vendasCA = null, vendedoresCA = [];

  if (conectadoCA) {
    try { ({ vendas: vendasCA, vendedores: vendedoresCA } = await vendasContaAzul(cache.bruto?.vendasCA || null)); }
    catch (e) { avisos.push(`Não consegui ler as vendas da Conta Azul: ${e.message}`); }
  }
  const usarPlanilha = planilhaConfigurada() && fonteCfg !== 'conta_azul';

  if (config.demo || (!usarPlanilha && !vendasCA)) {
    origem = 'demo';
    base = gerarDemoPlanilha();
    vendasCA = gerarDemoContaAzul(base.linhas);
  } else if (usarPlanilha) {
    origem = 'planilha';
    try { base = await lerPlanilha(); }
    catch (e) {
      if (!vendasCA) throw e;
      avisos.push(`Planilha indisponível (${e.message}). Mostrando as vendas da Conta Azul.`);
    }
  }
  await prepararFonte().catch(() => {});
  return { origem, base, vendasCA, vendedoresCA, avisos, conectadoCA };
}

// parte barata: monta a resposta (refeita quando chegam novos itens de venda)
async function montar(bruto) {
  let { origem, base, vendasCA, vendedoresCA } = bruto;
  const avisos = [...bruto.avisos];
  let extra = {};
  if (origem !== 'planilha' && origem !== 'demo') base = null;
  // fonte "Pedidos do painel" (ADM escolhe em Pedidos de venda): os indicadores leem os pedidos registrados no painel
  if (fontePainel()) { origem = 'painel'; base = { linhas: linhasDoPainel(), mapa: null }; }
  let soPlanilha = null;
  const corte = fonteMista();
  if (corte && (origem === 'planilha' || (origem === 'demo' && config.demo)) && base) {
    // linhas sem código: a mesma venda pode estar no painel (cliente + data + total)
    const kSem = (l) => [chave(clienteBase(l.cliente_original || l.cliente || '')), l.data || '', Math.round((Number(l.total) || 0) * 100)].join('|');
    const painelTodos = linhasDoPainel();
    const doPainel = painelTodos.filter((l) => (l.mes || '') >= corte), codPainel = new Set(doPainel.map((l) => chaveCodigo(l.codigo_pedido)).filter(Boolean));
    // antes do corte vale a planilha; o pedido que foi trazido para o painel (alteração, % de premiação, complementar) vale a versão do painel, só para aquele código
    const painelAntes = painelTodos.filter((l) => (l.mes || '') < corte);
    const codAntes = new Set(painelAntes.map((l) => chaveCodigo(l.codigo_pedido)).filter(Boolean)), semCodAntes = new Set(painelAntes.map(kSem));
    const plan = base.linhas, depois = plan.filter((l) => (l.mes || '') >= corte);
    const antes = plan.filter((l) => (l.mes || '') < corte).filter((l) => { const c = chaveCodigo(l.codigo_pedido || l.codigo || ''); return c ? !codAntes.has(c) : !semCodAntes.has(kSem(l)); });
    soPlanilha = depois.filter((l) => { const c = chaveCodigo(l.codigo_pedido || l.codigo || ''); return !c || !codPainel.has(c); });
    const semCodPainel = new Set(doPainel.map(kSem));
    soPlanilha = soPlanilha.filter((l) => chaveCodigo(l.codigo_pedido || l.codigo || '') || !semCodPainel.has(kSem(l)));
    const emUso = planilhaEmUso();
    base = { ...base, linhas: [...antes, ...painelAntes, ...doPainel, ...(emUso ? soPlanilha.map((l) => ({ ...l, pos_corte: true })) : [])] };
    origem = 'misto';
    if (soPlanilha.length && emUso) avisos.push(`${soPlanilha.length} ${soPlanilha.length === 1 ? 'venda lançada' : 'vendas lançadas'} na planilha a partir de ${corte.split('-').reverse().join('/')} ${soPlanilha.length === 1 ? 'entrou' : 'entraram'} no painel (a planilha ainda está em uso). Quando o painel for a única ferramenta, encerre a planilha em Planilha de vendas → Fonte dos indicadores.`);
    else if (soPlanilha.length) avisos.push(`${soPlanilha.length} ${soPlanilha.length === 1 ? 'linha de venda' : 'linhas de venda'} a partir de ${corte.split('-').reverse().join('/')} ${soPlanilha.length === 1 ? 'está' : 'estão'} só na planilha (R$ ${soPlanilha.reduce((s2, l) => s2 + (l.total || 0), 0).toLocaleString('pt-BR', { maximumFractionDigits: 0 })}). Desde novembro as vendas são lançadas no sistema: traga com Planilha de vendas → Importar base → Só as linhas novas, ou veja em Inconsistências.`);
  }
  // sem Conta Azul conectada não existe "lado do sistema": nunca usar as vendas fictícias da demonstração junto com dados reais
  if (bruto.origem === 'demo' && !config.demo) vendasCA = null;
  if (!base && vendasCA) {
    origem = 'conta_azul';
    const cacheItens = await carregarCacheItens();
    agendarItens(vendasCA.filter((v) => EFETIVAS.has(v.situacao) && v.data.slice(0, 7) >= detalheCaDesde()));
    const r = linhasDeVendasCA(vendasCA, cacheItens);
    base = { linhas: r.linhas, mapa: null };
    extra = { cobertura_itens: r.cobertura_itens, itens_pendentes: itensCache.pendentes, nr_calculado: true, historico_desde: r.historico_desde, detalhe_desde: r.detalhe_desde };
    avisos.push(`Fonte: Conta Azul. Até ${nomeMesCurto(detalheCaDesde())} cada mês entrou como um lançamento único, então esses meses aparecem só no faturamento (sem pedidos, ticket, clientes ou novo × recompra). Ligue a planilha (BASE TRATADA) para ter o histórico completo.`);
    if (itensCache.pendentes) avisos.push(`Buscando os produtos de ${itensCache.pendentes} vendas na Conta Azul. O mix de produtos se completa nos próximos minutos.`);
  }

  const linhas = base.linhas.filter((l) => l.total || l.quantidade);
  // novo × recompra em branco: o painel preenche pela carteira (cliente que já comprou antes = recompra; 1ª compra = novo).
  // A planilha do Google recebe o mesmo valor pelo botão "Preencher novo × recompra" e nos horários automáticos.
  {
    const kc = (n) => chave(clienteBase(n || ''));
    const datas = new Map();
    const add = (n, d) => { const c = kc(n); if (!c || !d) return; const v = datas.get(c); if (!v || d < v) datas.set(c, d); };
    linhas.forEach((l) => add(l.cliente_original || l.cliente, l.data));
    (vendasCA || []).forEach((v) => { if (EFETIVAS.has(v.situacao)) add(v.cliente, v.data); });
    for (const l of linhas) {
      if (l.novo_recompra || !l.data) continue;
      const p = datas.get(kc(l.cliente_original || l.cliente));
      l.novo_recompra = p && p < l.data ? 'recompra' : 'novo'; l.nr_auto = true;
    }
  }
  const q = qualidade(linhas, base.mapa);
  q.faltando.novo_recompra_auto = linhas.filter((l) => l.nr_auto).length;
  if (base.mapa?.obrigatorias_faltando?.length) avisos.push(`A planilha não tem as colunas: ${base.mapa.obrigatorias_faltando.join(', ')}.`);

  return {
    fonte: origem,
    planilha_arquivo: origem === 'planilha' || origem === 'misto' ? base.arquivo || null : null,
    corte_sistema: corte || null,
    // enquanto a planilha está em uso, essas vendas já entram no painel (e são comparadas com a Conta Azul): não são inconsistência
    so_planilha: soPlanilha && !planilhaEmUso() ? soPlanilha.map((l) => ({ d: l.data, m: l.mes, c: l.cliente, v: l.vendedor, t: Math.round((l.total || 0) * 100) / 100, cd: l.codigo_pedido || l.codigo || '', tp: l.tipo_produto, q: l.quantidade })) : undefined,
    detalhe_desde: detalheCaDesde(),
    nr_fonte: origem === 'planilha' && base.mapa?.nr_tratado ? (base.mapa?.tratamento === 'painel' ? 'painel' : 'tratada') : undefined,
    de_para: origem === 'planilha' ? base.mapa?.de_para || null : null,
    conta_azul_conectada: !!bruto.conectadoCA,
    modo_demo: !!config.demo,
    credenciais_conta_azul: !!(config.clientId && config.clientSecret),
    atualizado_em: new Date().toISOString(),
    avisos,
    ...extra,
    regras: {
      ponto_equilibrio: config.pontoEquilibrio || null,
      meta: config.metaMensal || null,
      comissao_inicio: config.comissaoInicio,
      comissao_teto: config.comissaoTeto,
      comissao_faixas: await faixasComissao(),
    },
    vendedores_cadastrados: vendedoresCA.map((v) => v.nome),
    linhas: linhas.map((l) => ({
      m: l.mes, d: l.data, c: l.cliente, p: l.pedido, v: l.vendedor, tv: l.tipo_venda, nr: l.novo_recompra, ...(l.nr_auto ? { nra: 1 } : {}),
      tp: l.tipo_produto, mt: l.material, es: l.especificacao, cr: l.cor, pr: l.produto || '', q: l.quantidade, t: Math.round(l.total * 100) / 100, cu: Math.round((l.custo || 0) * 100) / 100,
      ...(l.codigo_pedido || (l.pedido_informado && !String(l.pedido).includes('|')) ? { cd: l.codigo_pedido || l.pedido } : {}),
      p1: l.pag1, p2: l.pag2, ok: l.pago_100, fp: l.forma_pagamento, pz: l.prazo_entrega, sg: l.segmento,
      ...(l.consolidado ? { cs: 1 } : {}),
      // linha da planilha do Google (para preencher campo em branco pelo painel) ou lançada no painel
      ...(l.do_painel ? { sp: 1 } : l.linha ? { ln: l.linha } : {}),
      // para a página Inconsistências: nome como foi lançado (quando difere do padronizado) e possível duplicidade
      ...(l.cliente_original && l.cliente_original !== l.cliente ? { co: l.cliente_original } : {}),
      ...(l.duplicado ? { du: 1 } : {}),
      ...(l.pos_corte ? { pv: 1 } : {}),
      ...(l.lote ? { lo: l.lote } : {}),
      ...(l.pct_premiacao != null ? { pp: l.pct_premiacao, op: l.obs_premiacao || '' } : {}),
    })),
    // vendas do sistema, para a conciliação (data da venda, situação, cliente, valor)
    conta_azul: vendasCA
      ? {
          por_mes: resumoMensalCA(vendasCA),
          vendas: vendasCA.map((v) => ({ d: v.data, e: v.criado_em, n: v.numero, c: clienteBase(v.cliente), v: v.vendedor || '', s: v.situacao, t: Math.round(v.total * 100) / 100 })),
        }
      : null,
    qualidade: q,
  };
}

export async function dadosDeVendas(forcar = false) {
  const vencido = Date.now() - cache.quando > config.cacheSegundos * 1000;
  if (cache.bruto && !vencido && !forcar) {
    if (cache.versaoItens !== itensCache.versao) {
      cache.versaoItens = itensCache.versao;
      cache.dados = await montar(cache.bruto);
    }
    return cache.dados;
  }
  cache.carregando ||= buscarFontes()
    .then(async (b) => { cache.bruto = b; cache.quando = Date.now(); cache.versaoItens = itensCache.versao; cache.dados = await montar(b); return cache.dados; })
    .finally(() => { cache.carregando = null; });
  if (cache.dados && !forcar) return cache.dados;
  return cache.carregando;
}

// pedidos do painel mudaram: a próxima leitura remonta a base sem chamar a Conta Azul de novo
export const remontarVendas = () => { cache.versaoItens = -1; };
export const vendasContaAzulEmCache = () => cache.bruto?.vendasCA || null;
