// Monta os números do painel comercial a partir das vendas e contas a receber.
import { config } from './config.js';
import * as ca from './contaAzul.js';
import { gerarDemo } from './demo.js';

const NAO_CONTAM = new Set(['CANCELADO', 'ORCAMENTO']);
const ROTULO_SITUACAO = {
  APROVADO: 'Aprovada', FATURADO: 'Faturada', EM_ANDAMENTO: 'Em andamento',
  ORCAMENTO: 'Orçamento', CANCELADO: 'Cancelada', SEM_SITUACAO: 'Sem situação',
};

const iso = (d) => d.toISOString().slice(0, 10);
const hojeBR = () => new Date(Date.now() - 3 * 3600e3); // horário de Brasília (UTC-3)

function somar(lista, campo = 'total') { return lista.reduce((s, x) => s + (x[campo] || 0), 0); }

function agrupar(lista, chave, limite) {
  const m = new Map();
  for (const v of lista) {
    const k = v[chave] || '—';
    const g = m.get(k) || { nome: k, valor: 0, qtd: 0 };
    g.valor += v.total; g.qtd += 1; m.set(k, g);
  }
  const total = somar(lista) || 1;
  return [...m.values()]
    .map((g) => ({ ...g, ticket: g.qtd ? g.valor / g.qtd : 0, participacao: g.valor / total }))
    .sort((a, b) => b.valor - a.valor)
    .slice(0, limite || 999);
}

function limitesDoMes(ano, mes) {
  const ini = new Date(Date.UTC(ano, mes - 1, 1));
  const fim = new Date(Date.UTC(ano, mes, 0));
  return { ini, fim };
}

// ---------- cache em memória ----------
const cache = { base: null, quando: 0, carregando: null };
const itensPorVenda = new Map(); // id -> itens (itens raramente mudam)
let filaItens = Promise.resolve();
let itensPendentes = 0;

async function carregarBase() {
  const agora = hojeBR();
  const inicioHist = new Date(Date.UTC(agora.getUTCFullYear(), agora.getUTCMonth() - (config.mesesHistorico - 1), 1));
  const fimRec = new Date(agora.getTime() + 120 * 864e5);
  const inicioRec = new Date(agora.getTime() - 365 * 864e5);
  const vendas = await ca.buscarVendas(iso(inicioHist), iso(agora));
  let receber = [];
  let erroReceber = null;
  try { receber = await ca.buscarContasAReceber(iso(inicioRec), iso(fimRec)); } catch (e) { erroReceber = e.message; }
  return { vendas, receber, erroReceber, fonte: 'conta_azul', atualizado_em: new Date().toISOString() };
}

async function base(forcar = false) {
  const conexao = await ca.statusConexao();
  if (config.demo || !conexao.conectado) {
    return { ...gerarDemo(), fonte: 'demo', atualizado_em: new Date().toISOString() };
  }
  const vencido = Date.now() - cache.quando > config.cacheSegundos * 1000;
  if (cache.base && !vencido && !forcar) return cache.base;
  cache.carregando ||= carregarBase()
    .then((b) => { cache.base = b; cache.quando = Date.now(); return b; })
    .finally(() => { cache.carregando = null; });
  // se já existe uma versão anterior, devolve ela enquanto atualiza em segundo plano
  if (cache.base && !forcar) return cache.base;
  return cache.carregando;
}

// Busca os itens das vendas do período aos poucos, sem travar o painel
function agendarItens(vendas) {
  const faltam = vendas.filter((v) => v.id && !itensPorVenda.has(v.id)).slice(0, config.maxVendasComItens);
  for (const v of faltam) {
    itensPorVenda.set(v.id, null); // marcado como "em busca"
    itensPendentes++;
    filaItens = filaItens.then(async () => {
      try { itensPorVenda.set(v.id, await ca.buscarItensDaVenda(v.id)); }
      catch { itensPorVenda.set(v.id, []); }
      finally { itensPendentes--; }
    });
  }
}

function rankingProdutos(vendas, demoItens) {
  const m = new Map();
  let cobertas = 0;
  for (const v of vendas) {
    const itens = demoItens ? demoItens.get(v.id) : itensPorVenda.get(v.id);
    if (!itens) continue;
    cobertas++;
    for (const i of itens) {
      const g = m.get(i.nome) || { nome: i.nome, valor: 0, quantidade: 0, vendas: 0 };
      g.valor += i.total; g.quantidade += i.quantidade; g.vendas += 1; m.set(i.nome, g);
    }
  }
  const total = [...m.values()].reduce((s, g) => s + g.valor, 0) || 1;
  return {
    cobertura: vendas.length ? cobertas / vendas.length : 1,
    lista: [...m.values()].map((g) => ({ ...g, participacao: g.valor / total })).sort((a, b) => b.valor - a.valor).slice(0, 15),
  };
}

export async function montarPainel({ ano, mes, forcar } = {}) {
  const b = await base(forcar);
  const agora = hojeBR();
  ano = Number(ano) || agora.getUTCFullYear();
  mes = Number(mes) || agora.getUTCMonth() + 1;
  const { ini, fim } = limitesDoMes(ano, mes);
  const mesCorrente = ano === agora.getUTCFullYear() && mes === agora.getUTCMonth() + 1;
  const ateDia = mesCorrente ? agora.getUTCDate() : fim.getUTCDate();

  // mês anterior até o mesmo dia (comparação justa no mês corrente)
  const ant = limitesDoMes(mes === 1 ? ano - 1 : ano, mes === 1 ? 12 : mes - 1);
  const diaAnt = Math.min(ateDia, ant.fim.getUTCDate());
  const fimAnt = mesCorrente ? new Date(Date.UTC(ant.ini.getUTCFullYear(), ant.ini.getUTCMonth(), diaAnt)) : ant.fim;

  const entre = (v, a, z) => v.data >= iso(a) && v.data <= iso(z);
  const doMes = b.vendas.filter((v) => entre(v, ini, fim));
  const efetivas = doMes.filter((v) => !NAO_CONTAM.has(v.situacao));
  const efetivasAnt = b.vendas.filter((v) => entre(v, ant.ini, fimAnt) && !NAO_CONTAM.has(v.situacao));
  const orcamentos = doMes.filter((v) => v.situacao === 'ORCAMENTO');
  const canceladas = doMes.filter((v) => v.situacao === 'CANCELADO');

  const faturamento = somar(efetivas);
  const faturamentoAnt = somar(efetivasAnt);
  const diasNoMes = fim.getUTCDate();
  const projecao = mesCorrente && ateDia > 0 ? (faturamento / ateDia) * diasNoMes : faturamento;

  // série diária com acumulado + mesma curva do mês anterior
  const diaria = [];
  let acum = 0;
  let acumAnt = 0;
  for (let d = 1; d <= diasNoMes; d++) {
    const dia = iso(new Date(Date.UTC(ano, mes - 1, d)));
    const diaAntIso = d <= ant.fim.getUTCDate() ? iso(new Date(Date.UTC(ant.ini.getUTCFullYear(), ant.ini.getUTCMonth(), d))) : null;
    const valor = somar(efetivas.filter((v) => v.data === dia));
    acumAnt += diaAntIso ? somar(b.vendas.filter((v) => v.data === diaAntIso && !NAO_CONTAM.has(v.situacao))) : 0;
    acum += valor;
    diaria.push({ dia: d, data: dia, valor, acumulado: d <= ateDia ? acum : null, acumulado_anterior: acumAnt });
  }

  // série mensal (histórico)
  const mensal = [];
  for (let i = config.mesesHistorico - 1; i >= 0; i--) {
    const dt = new Date(Date.UTC(agora.getUTCFullYear(), agora.getUTCMonth() - i, 1));
    const l = limitesDoMes(dt.getUTCFullYear(), dt.getUTCMonth() + 1);
    const vs = b.vendas.filter((v) => entre(v, l.ini, l.fim) && !NAO_CONTAM.has(v.situacao));
    mensal.push({ ano: dt.getUTCFullYear(), mes: dt.getUTCMonth() + 1, valor: somar(vs), qtd: vs.length });
  }

  // produtos
  let produtos;
  if (b.fonte === 'demo') produtos = rankingProdutos(efetivas, b.itens);
  else { agendarItens(efetivas); produtos = rankingProdutos(efetivas); }

  // contas a receber
  const hoje = iso(agora);
  const rec = b.receber;
  const emAberto = rec.filter((r) => r.aberto > 0);
  const atrasados = emAberto.filter((r) => r.status === 'ATRASADO' || (r.vencimento && r.vencimento < hoje));
  const aVencer30 = emAberto.filter((r) => r.vencimento >= hoje && r.vencimento <= iso(new Date(agora.getTime() + 30 * 864e5)));
  const doMesRec = rec.filter((r) => r.vencimento >= iso(ini) && r.vencimento <= iso(fim));

  const situacoes = Object.entries(
    doMes.reduce((m, v) => { (m[v.situacao] ||= { qtd: 0, valor: 0 }); m[v.situacao].qtd++; m[v.situacao].valor += v.total; return m; }, {})
  ).map(([k, g]) => ({ situacao: k, rotulo: ROTULO_SITUACAO[k] || k, ...g })).sort((a, b) => b.valor - a.valor);

  return {
    fonte: b.fonte,
    atualizado_em: b.atualizado_em,
    avisos: [b.erroReceber ? `Contas a receber indisponíveis: ${b.erroReceber}` : null].filter(Boolean),
    periodo: { ano, mes, inicio: iso(ini), fim: iso(fim), mes_corrente: mesCorrente, ate_dia: ateDia, dias_no_mes: diasNoMes, comparado_ate: iso(fimAnt) },
    kpis: {
      faturamento,
      faturamento_anterior: faturamentoAnt,
      vendas: efetivas.length,
      vendas_anterior: efetivasAnt.length,
      ticket_medio: efetivas.length ? faturamento / efetivas.length : 0,
      ticket_medio_anterior: efetivasAnt.length ? faturamentoAnt / efetivasAnt.length : 0,
      projecao,
      meta: config.metaMensal || null,
      clientes_ativos: new Set(efetivas.map((v) => v.cliente)).size,
      orcamentos_qtd: orcamentos.length,
      orcamentos_valor: somar(orcamentos),
      canceladas_qtd: canceladas.length,
      canceladas_valor: somar(canceladas),
      conversao: orcamentos.length + efetivas.length ? efetivas.length / (orcamentos.length + efetivas.length) : null,
    },
    diaria,
    mensal,
    situacoes,
    vendedores: agrupar(efetivas, 'vendedor'),
    clientes: agrupar(efetivas, 'cliente', 12),
    produtos: { ...produtos, carregando: b.fonte !== 'demo' && itensPendentes > 0 },
    receber: {
      em_aberto: somar(emAberto, 'aberto'),
      em_aberto_qtd: emAberto.length,
      atrasado: somar(atrasados, 'aberto'),
      atrasado_qtd: atrasados.length,
      a_vencer_30: somar(aVencer30, 'aberto'),
      a_vencer_30_qtd: aVencer30.length,
      recebido_do_mes: somar(doMesRec, 'pago'),
      previsto_do_mes: somar(doMesRec, 'valor'),
      maiores_atrasos: atrasados
        .map((r) => ({ cliente: r.cliente, descricao: r.descricao, vencimento: r.vencimento, aberto: r.aberto }))
        .sort((a, b) => b.aberto - a.aberto)
        .slice(0, 10),
    },
    vendas_recentes: doMes
      .slice()
      .sort((a, b) => (b.data + (b.numero || '')).localeCompare(a.data + (a.numero || '')))
      .slice(0, 25)
      .map(({ numero, data, cliente, vendedor, situacao, total }) => ({ numero, data, cliente, vendedor, situacao, rotulo: ROTULO_SITUACAO[situacao] || situacao, total })),
  };
}
