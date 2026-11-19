// Gestão financeira pela API v2 da Conta Azul, no espírito dos relatórios do sistema:
// DRE gerencial (competência e caixa), fluxo de caixa realizado e projetado, receitas e despesas
// por categoria e centro de custo, contas a receber (inadimplência por idade) e a pagar, saldos.
import { config } from './config.js';
import * as ca from './contaAzul.js';
import { gerarDemoPlanilha } from './demo.js';
import { lerKV, salvarKV } from './tokenStore.js';

const iso = (d) => d.toISOString().slice(0, 10);
const hojeBR = () => new Date(Date.now() - 3 * 3600e3);
const mesesAte = (n) => {
  const a = hojeBR(); const out = [];
  for (let i = n - 1; i >= 0; i--) out.push(iso(new Date(Date.UTC(a.getUTCFullYear(), a.getUTCMonth() - i, 1))).slice(0, 7));
  return out;
};
const fimDoMes = (m) => { const [a, b] = m.split('-').map(Number); return iso(new Date(Date.UTC(a, b, 0))); };
const zeros = (meses) => Object.fromEntries(meses.map((m) => [m, 0]));
const r2 = (v) => Math.round(v * 100) / 100;

// ---------- DRE ----------
function achatarDRE(itens, nivel = 0, out = []) {
  for (const it of [...itens].sort((a, b) => (a.posicao ?? 0) - (b.posicao ?? 0))) {
    out.push({ descricao: it.descricao, codigo: it.codigo || '', nivel, totalizador: !!it.indica_totalizador, categorias: (it.categorias_financeiras || []).map((c) => c.id) });
    if (it.subitens?.length) achatarDRE(it.subitens, nivel + 1, out);
  }
  return out;
}

// v120: valor de cada categoria da parcela pelo rateio da Conta Azul (ex.: venda com desconto = receita bruta + desconto negativo).
// Sem o rateio (ainda não buscado), divide igualmente como antes. O valor pago é distribuído na mesma proporção.
function partes(p, campoValor, semCat) {
  const base = Number(p[campoValor]) || 0;
  const cats = p.categorias.length ? p.categorias : [{ id: null, nome: semCat }];
  const rat = p.rateio?.length ? p.rateio : cats.length > 1 && cats.every((c) => c.valor != null) ? cats : null;
  if (rat) {
    const soma = rat.reduce((a, r) => a + (Number(r.valor) || 0), 0), ref = Math.abs(soma) > 0.009 ? soma : p.total;
    const f = ref ? base / ref : 0;
    return rat.map((r) => ({ id: r.id, nome: r.nome || cats.find((c) => c.id === r.id)?.nome || 'Sem categoria', v: (Number(r.valor) || 0) * f }));
  }
  return cats.map((c) => ({ id: c.id, nome: c.nome, v: base / cats.length }));
}
// valor com sinal (receita +, despesa −)
function lancamentos(parcelas, campoValor, campoMes) {
  const out = [];
  for (const p of parcelas) {
    const sinal = p.tipo === 'receber' ? 1 : -1;
    if (!p[campoValor]) continue;
    const cc = p.centros?.length ? p.centros : ['Sem centro de custo'];
    for (const c of partes(p, campoValor, p.tipo === 'receber' ? 'Receitas sem categoria' : 'Despesas sem categoria')) out.push({ tipo: p.tipo, mes: (p[campoMes] || '').slice(0, 7), categoria_id: c.id, categoria: c.nome, centro: cc[0], pessoa: p.pessoa, valor: c.v * sinal });
  }
  return out;
}

function montarDRE(estrutura, lancs, meses) {
  if (!estrutura?.length) return dreSimples(lancs, meses);
  const plano = achatarDRE(estrutura);
  const idx = new Map();
  plano.forEach((l, i) => l.categorias.forEach((c) => idx.set(c, i)));
  const linhas = plano.map((l) => ({ ...l, valores: zeros(meses), detalhe: {} }));
  const semLugar = { descricao: 'Lançamentos sem categoria na DRE', nivel: 0, totalizador: false, valores: zeros(meses), detalhe: {} };
  for (const x of lancs) {
    if (!meses.includes(x.mes)) continue;
    const i = idx.get(x.categoria_id);
    const alvo = i === undefined ? semLugar : linhas[i];
    alvo.valores[x.mes] += x.valor;
    (alvo.detalhe[x.categoria] ||= zeros(meses))[x.mes] += x.valor;
  }
  const proprio = linhas.map((l) => ({ ...l.valores }));
  for (let i = 0; i < linhas.length; i++) {
    if (linhas[i].totalizador) continue;
    for (let j = i + 1; j < linhas.length && linhas[j].nivel > linhas[i].nivel; j++) {
      if (!linhas[j].totalizador) for (const m of meses) linhas[i].valores[m] += proprio[j][m];
    }
  }
  const acum = zeros(meses);
  for (const l of linhas) {
    if (l.nivel !== 0) continue;
    if (l.totalizador) for (const m of meses) l.valores[m] = acum[m];
    else for (const m of meses) acum[m] += l.valores[m];
  }
  const tem = Object.values(semLugar.valores).some((v) => Math.abs(v) > 0.009);
  const resultado = Object.fromEntries(meses.map((m) => [m, acum[m] + semLugar.valores[m]]));
  return { linhas: [...linhas, ...(tem ? [semLugar] : [])].filter((l) => l.totalizador || Object.values(l.valores).some((v) => Math.abs(v) > 0.009)), resultado };
}

function dreSimples(lancs, meses) {
  const grupos = { receber: new Map(), pagar: new Map() };
  for (const x of lancs) {
    if (!meses.includes(x.mes)) continue;
    const v = grupos[x.tipo].get(x.categoria) || zeros(meses);
    v[x.mes] += x.valor; grupos[x.tipo].set(x.categoria, v);
  }
  const soma = (v) => Object.values(v).reduce((s, x) => s + Math.abs(x), 0);
  const bloco = (titulo, mapa) => {
    const tot = Object.fromEntries(meses.map((m) => [m, [...mapa.values()].reduce((s, v) => s + v[m], 0)]));
    return [{ descricao: titulo, nivel: 0, totalizador: false, valores: tot },
      ...[...mapa.entries()].sort((a, b) => soma(b[1]) - soma(a[1])).map(([nome, v]) => ({ descricao: nome, nivel: 1, totalizador: false, valores: v }))];
  };
  const linhas = [...bloco('Receitas', grupos.receber), ...bloco('Despesas', grupos.pagar)];
  const resultado = Object.fromEntries(meses.map((m) => [m, linhas.filter((l) => l.nivel === 0).reduce((s, l) => s + l.valores[m], 0)]));
  linhas.push({ descricao: 'Resultado', nivel: 0, totalizador: true, valores: resultado });
  return { linhas, resultado };
}


// ---------- indicadores gerenciais: margem de contribuição e ponto de equilíbrio ----------
// Cada categoria é classificada pela linha da DRE em que está (a DRE da Visu já marca "(Variáveis)" e "(Fixos)").
const sem = (t) => String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
function classificador(estrutura) {
  const mapa = new Map();
  const anda = (itens, caminho) => {
    for (const it of itens || []) {
      const cam = [...caminho, it.descricao];
      for (const c of it.categorias_financeiras || []) { mapa.set(c.id, cam.join(' > ')); (mapa.cod ||= new Map()).set(c.id, it.codigo || ''); }
      anda(it.subitens, cam);
    }
  };
  anda(estrutura, []);
  return mapa;
}
function natureza(x, mapa) {
  const t = sem((mapa.get(x.categoria_id) || '') + ' > ' + x.categoria);
  if (x.tipo === 'receber') return /financeir|rendiment|nao operac|juros/.test(t) ? 'outras_receitas' : 'receita';
  if (/a identificar/.test(t)) return 'nao_classificado';
  if (/deduc|simples nacional|icms|pis|cofins|iss\b|imposto sobre|cancelament|devolu|desconto/.test(t)) return 'deducao';
  if (/variave/.test(t)) return 'variavel';
  if (/fix/.test(t)) return 'fixo';
  if (/financeir|tarifa|juros|iof/.test(t)) return 'financeiro';
  if (/tribut|irpj|csll/.test(t)) return 'tributos';
  if (/materia|insumo|tecido|aviament|sublima|terceiriz|comiss|frete|embalag/.test(t)) return 'variavel';
  return 'fixo';
}
function indicadores(estrutura, lancs, meses) {
  const mapa = classificador(estrutura);
  const z = () => ({ receita: 0, outras_receitas: 0, deducao: 0, variavel: 0, fixo: 0, financeiro: 0, tributos: 0, nao_classificado: 0 });
  const por = Object.fromEntries(meses.map((m) => [m, z()]));
  for (const x of lancs) if (por[x.mes]) por[x.mes][natureza(x, mapa)] += Math.abs(x.valor);
  return Object.fromEntries(meses.map((m) => {
    const g = por[m];
    const variaveis = g.deducao + g.variavel;
    const fixos = g.fixo + g.financeiro + g.tributos + g.nao_classificado;
    const mc = g.receita - variaveis;
    const mcPct = g.receita ? mc / g.receita : 0;
    return [m, {
      receita: r2(g.receita), outras_receitas: r2(g.outras_receitas), deducoes: r2(g.deducao), custos_variaveis: r2(g.variavel),
      variaveis: r2(variaveis), fixos: r2(fixos), financeiro: r2(g.financeiro), tributos: r2(g.tributos), nao_classificado: r2(g.nao_classificado),
      margem_contribuicao: r2(mc), mc_pct: Math.round(mcPct * 10000) / 10000,
      ponto_equilibrio: mcPct > 0.02 ? r2(fixos / mcPct) : null,
      resultado: r2(g.receita + g.outras_receitas - variaveis - fixos),
    }];
  }));
}


// ---------- detalhamento: os lançamentos por trás de cada total (para abrir ao clicar no painel) ----------
// Linha compacta: [mês, r|p, categoria, centro, pessoa, descrição, vencimento, valor, status, caminho na DRE, natureza, data do pagamento (v118), conta, código da DRE (v120)]
function detalhar(parcelas, campoValor, campoMes, mapa) {
  const out = [];
  for (const p of parcelas) {
    for (const c of partes(p, campoValor, 'Sem categoria')) {
      const v = r2(c.v);
      if (!v) continue;
      const caminho = mapa.get(c.id) || 'Lançamentos sem categoria na DRE';
      out.push([(p[campoMes] || '').slice(0, 7), p.tipo === 'receber' ? 'r' : 'p', c.nome, p.centros?.[0] || 'Sem centro de custo', p.pessoa || '', p.descricao || '', p.vencimento || '', v, p.status || '',
        caminho.split(' > ').join('|'), natureza({ tipo: p.tipo, categoria_id: c.id, categoria: c.nome, valor: v }, mapa), p.data_pagamento || '', p.conta || '', mapa.cod?.get(c.id) || '']);
    }
  }
  return out;
}

// ---------- agrupamentos (relatórios por categoria / centro de custo / pessoa) ----------
function porDimensao(lancs, meses, tipo, campo, limite = 12) {
  const mapa = new Map();
  for (const x of lancs) {
    if (x.tipo !== tipo || !meses.includes(x.mes)) continue;
    const v = mapa.get(x[campo]) || zeros(meses);
    v[x.mes] += Math.abs(x.valor); mapa.set(x[campo], v);
  }
  return [...mapa.entries()]
    .map(([nome, valores]) => ({ nome, valores, total: Object.values(valores).reduce((s, v) => s + v, 0) }))
    .sort((a, b) => b.total - a.total)
    .slice(0, limite)
    .map((x) => ({ ...x, valores: Object.fromEntries(Object.entries(x.valores).map(([k, v]) => [k, r2(v)])), total: r2(x.total) }));
}

// ---------- contas em aberto ----------
const FAIXAS_ATRASO = [[1, 15, '1 a 15 dias'], [16, 30, '16 a 30 dias'], [31, 60, '31 a 60 dias'], [61, 90, '61 a 90 dias'], [91, 99999, 'Mais de 90 dias']];

function contasEmAberto(abertos, tipo, hoje) {
  const xs = abertos.filter((x) => x.tipo === tipo);
  const dias = (d) => Math.round((Date.parse(hoje) - Date.parse(d)) / 864e5);
  const atras = xs.filter((x) => x.vencimento < hoje);
  const a_vencer = xs.filter((x) => x.vencimento >= hoje);
  const idade = FAIXAS_ATRASO.map(([de, ate, rot]) => {
    const g = atras.filter((x) => dias(x.vencimento) >= de && dias(x.vencimento) <= ate);
    return { faixa: rot, valor: r2(g.reduce((s, x) => s + x.aberto, 0)), qtd: g.length };
  });
  const porPessoa = new Map();
  atras.forEach((x) => { const g = porPessoa.get(x.pessoa || '—') || { pessoa: x.pessoa || '—', valor: 0, qtd: 0, mais_antigo: x.vencimento }; g.valor += x.aberto; g.qtd++; if (x.vencimento < g.mais_antigo) g.mais_antigo = x.vencimento; porPessoa.set(g.pessoa, g); });
  const em = (n) => iso(new Date(Date.parse(hoje) + n * 864e5));
  const janela = (a, b) => { const g = a_vencer.filter((x) => x.vencimento >= a && x.vencimento <= b); return { valor: r2(g.reduce((s, x) => s + x.aberto, 0)), qtd: g.length }; };
  return {
    total: r2(xs.reduce((s, x) => s + x.aberto, 0)), qtd: xs.length,
    atrasado: r2(atras.reduce((s, x) => s + x.aberto, 0)), atrasado_qtd: atras.length,
    a_vencer: r2(a_vencer.reduce((s, x) => s + x.aberto, 0)), a_vencer_qtd: a_vencer.length,
    prox7: janela(hoje, em(7)), prox30: janela(hoje, em(30)), prox90: janela(hoje, em(90)),
    idade,
    atraso_por_pessoa: [...porPessoa.values()].sort((a, b) => b.valor - a.valor).slice(0, 10).map((g) => ({ ...g, valor: r2(g.valor) })),
    proximos: a_vencer.sort((a, b) => a.vencimento.localeCompare(b.vencimento)).slice(0, 12).map((x) => ({ pessoa: x.pessoa, descricao: x.descricao, vencimento: x.vencimento, aberto: r2(x.aberto), categoria: x.categorias[0]?.nome || '' })),
  };
}

// fluxo de caixa projetado por semana: saldo atual + a receber − a pagar (13 semanas)
function projecao(abertos, saldoInicial, hoje) {
  const semanas = [];
  let saldo = saldoInicial;
  const atrasRec = abertos.filter((x) => x.tipo === 'receber' && x.vencimento < hoje).reduce((s, x) => s + x.aberto, 0);
  const atrasPag = abertos.filter((x) => x.tipo === 'pagar' && x.vencimento < hoje).reduce((s, x) => s + x.aberto, 0);
  for (let i = 0; i < 13; i++) {
    const ini = iso(new Date(Date.parse(hoje) + i * 7 * 864e5));
    const fim = iso(new Date(Date.parse(hoje) + (i * 7 + 6) * 864e5));
    const ent = abertos.filter((x) => x.tipo === 'receber' && x.vencimento >= ini && x.vencimento <= fim).reduce((s, x) => s + x.aberto, 0);
    const sai = abertos.filter((x) => x.tipo === 'pagar' && x.vencimento >= ini && x.vencimento <= fim).reduce((s, x) => s + x.aberto, 0);
    saldo += ent - sai;
    semanas.push({ inicio: ini, fim, entradas: r2(ent), saidas: r2(sai), saldo: r2(saldo) });
  }
  return { saldo_inicial: r2(saldoInicial), atrasados_receber: r2(atrasRec), atrasados_pagar: r2(atrasPag), semanas };
}

// ---------- montagem (mesma lógica para dados reais e demonstração) ----------
function montar(b, fonte) {
  const { meses, estrutura, comp, pagas, abertos, saldos, vencidas90 } = b;
  const hoje = iso(hojeBR());
  const lComp = lancamentos(comp, 'total', 'competencia');
  const lCaixa = lancamentos(pagas, 'pago', 'mes_pag');
  const dreComp = montarDRE(estrutura, lComp, meses);
  const dreCaixa = montarDRE(estrutura, lCaixa, meses);
  const somaMes = (ls, tipo) => Object.fromEntries(meses.map((m) => [m, r2(Math.abs(ls.filter((x) => x.tipo === tipo && x.mes === m).reduce((s, x) => s + x.valor, 0)))]));
  const saldoAtual = saldos.reduce((s, c) => s + (c.saldo || 0), 0);
  const receber = contasEmAberto(abertos, 'receber', hoje);
  const pagar = contasEmAberto(abertos, 'pagar', hoje);
  const venc90 = vencidas90 || 0;
  const linhaDRE = (l) => ({ descricao: l.descricao, codigo: l.codigo || '', nivel: l.nivel, totalizador: l.totalizador, valores: Object.fromEntries(Object.entries(l.valores).map(([k, v]) => [k, r2(v)])),
    // v120: categorias dentro de cada subgrupo (como na DRE gerencial da Conta Azul)
    ...(l.detalhe && Object.keys(l.detalhe).length ? { categorias: Object.entries(l.detalhe).map(([nome, vs]) => ({ nome, valores: Object.fromEntries(Object.entries(vs).map(([k, v]) => [k, r2(v)])) })).filter((c) => Object.values(c.valores).some((v) => Math.abs(v) > 0.009)).sort((a, b) => a.nome.localeCompare(b.nome, 'pt-BR')) } : {}) });
  return {
    fonte,
    atualizado_em: new Date().toISOString(),
    meses,
    ponto_equilibrio: config.pontoEquilibrio || null,
    dre: dreComp.linhas.map(linhaDRE),
    dre_caixa: dreCaixa.linhas.map(linhaDRE),
    resultado: dreComp.resultado,
    receita: somaMes(lComp, 'receber'),
    despesa: somaMes(lComp, 'pagar'),
    caixa: Object.fromEntries(meses.map((m) => [m, { entradas: somaMes(lCaixa, 'receber')[m], saidas: somaMes(lCaixa, 'pagar')[m] }])),
    despesas_categoria: porDimensao(lComp, meses, 'pagar', 'categoria'),
    receitas_categoria: porDimensao(lComp, meses, 'receber', 'categoria', 8),
    despesas_centro: porDimensao(lComp, meses, 'pagar', 'centro', 10),
    fornecedores: porDimensao(lComp, meses, 'pagar', 'pessoa', 10),
    receber, pagar,
    inadimplencia: venc90 ? r2(receber.atrasado / venc90) : null,
    saldo_atual: r2(saldoAtual),
    saldos,
    projecao: projecao(abertos, saldoAtual, hoje),
    sem_categoria: lComp.filter((x) => !x.categoria_id).length,
    indicadores: indicadores(estrutura, lComp, meses),
    det_competencia: detalhar(comp.filter((x) => meses.includes((x.competencia || '').slice(0, 7))), 'total', 'competencia', classificador(estrutura)),
    det_caixa: detalhar(pagas, 'pago', 'mes_pag', classificador(estrutura)),
    det_abertos: abertos.map((x) => [x.tipo === 'receber' ? 'r' : 'p', x.vencimento, x.pessoa || '', x.descricao || '', x.categorias[0]?.nome || '', r2(x.aberto), r2(x.total), x.id || '', r2(x.pago || 0)]),
    indicadores_caixa: indicadores(estrutura, lCaixa, meses),
    primeiro_mes_despesas: meses.find((m) => Math.abs(lComp.filter((x) => x.tipo === 'pagar' && x.mes === m).reduce((s, x) => s + x.valor, 0)) > 0.25 * Math.max(1, Math.abs(lComp.filter((x) => x.tipo === 'receber' && x.mes === m).reduce((s, x) => s + x.valor, 0)))) || null,
  };
}

// v118: fluxo de caixa diário e semanal precisa do dia do pagamento. Quando a listagem não traz a data, perguntamos à Conta Azul
// dia a dia (últimos 35 dias) e semana a semana (as 12 semanas antes disso). Dias e semanas que já passaram ficam guardados.
const cachePag = new Map(); // 'r|2026-11-03|2026-11-03' -> [ids]
async function idsPagos(tipo, de, ate, fixo) {
  const k = `${tipo}|${de}|${ate}`;
  if (fixo && cachePag.has(k)) return cachePag.get(k);
  const ls = await ca.buscarParcelas(tipo === 'r' ? 'receber' : 'pagar', { pagamento_de: de, pagamento_ate: ate });
  const ids = ls.filter((x) => x.pago > 0).map((x) => x.id);
  cachePag.set(k, ids); return ids;
}
async function refinarDatasPagamento(pagas, hoje) {
  const semData = pagas.filter((x) => !x.data_pagamento && x.id);
  if (!semData.length) return;
  const h = iso(hoje), dia = (n) => iso(new Date(hoje.getTime() - n * 864e5));
  const tarefas = [];
  for (let n = 0; n < 35; n++) { const d = dia(n); for (const t of ['r', 'p']) tarefas.push({ t, de: d, ate: d, fixo: n > 2, data: d }); }
  for (let w = 0; w < 12; w++) { const ate = dia(35 + w * 7), de = dia(41 + w * 7); for (const t of ['r', 'p']) tarefas.push({ t, de, ate, fixo: true, data: de, aprox: true }); }
  const porId = new Map();
  for (let i = 0; i < tarefas.length; i += 4) {
    await Promise.all(tarefas.slice(i, i + 4).map(async (x) => { try { (await idsPagos(x.t, x.de, x.ate, x.fixo)).forEach((id) => { if (!porId.has(id) || !x.aprox) porId.set(id, x.data); }); } catch { /* segue com o vencimento */ } }));
  }
  for (const x of semData) { const d = porId.get(x.id); if (d && d.slice(0, 7) === x.mes_pag && d <= h) x.data_pagamento = d; }
}

// v120: rateio das parcelas com mais de uma categoria, buscado no detalhe da parcela e guardado (não muda depois de lançado)
let rateioMemo = null;
async function aplicarRateio(b) {
  if (!rateioMemo) rateioMemo = (await lerKV('fin_rateio').catch(() => null)) || {};
  const todas = [...b.comp, ...b.pagas, ...b.abertos], multi = new Map();
  todas.forEach((p) => { if (p.id && p.categorias.length > 1 && !p.categorias.every((c) => c.valor != null)) multi.set(p.id, p); });
  const falta = [...multi.values()].filter((p) => { const m = rateioMemo[p.id]; return !m || Math.abs((m.t || 0) - p.total) > 0.009; });
  let novos = 0;
  for (let i = 0; i < falta.length; i += 5) {
    await Promise.all(falta.slice(i, i + 5).map(async (p) => { try { const r = ca.rateioDoDetalhe(await ca.detalheParcelaBruto(p.id)); rateioMemo[p.id] = { t: p.total, r: r ? r.map((x) => [x.id, x.valor, x.nome]) : null }; novos++; } catch { /* fica com a divisão igual */ } }));
    if (novos && i % 50 === 0) await salvarKV('fin_rateio', rateioMemo).catch(() => {});
  }
  if (novos) await salvarKV('fin_rateio', rateioMemo).catch(() => {});
  let aplic = 0;
  todas.forEach((p) => { const m = rateioMemo[p.id]; if (m?.r?.length && p.categorias.length > 1) { p.rateio = m.r.map(([id, valor, nome]) => ({ id, valor, nome: nome || p.categorias.find((c) => c.id === id)?.nome || '' })); aplic++; } });
  console.log(`[financeiro] rateio: ${multi.size} parcelas com mais de uma categoria, ${novos} buscadas agora, ${aplic} aplicadas`);
  return aplic;
}
export async function amostraRateio() {
  const d = new Date(Date.now() - 3 * 3600e3), m = iso(new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - 1, 1))).slice(0, 7);
  const br = await ca.buscarParcelasBrutas('receber', { competencia_de: `${m}-01`, competencia_ate: fimDoMes(m) });
  const it = br.find((x) => (x.categorias || []).length > 1) || br[0];
  const det = it ? await ca.detalheParcelaBruto(it.id).catch((e) => ({ erro: e.message })) : null;
  return { mes: m, item_listagem: it, detalhe: det, rateio_lido: det ? ca.rateioDoDetalhe(det) : null, memo: rateioMemo ? Object.keys(rateioMemo).length : 0 };
}

async function carregarConta() {
  const meses = mesesAte(config.mesesHistorico);
  const ini = `${meses[0]}-01`, fim = fimDoMes(meses[meses.length - 1]);
  const hoje = hojeBR();
  const [estrutura, recComp, pagComp] = await Promise.all([
    ca.buscarEstruturaDRE().catch(() => []),
    ca.buscarParcelas('receber', { competencia_de: ini, competencia_ate: fim }),
    ca.buscarParcelas('pagar', { competencia_de: ini, competencia_ate: fim }),
  ]);
  // regime de caixa: parcelas pagas em cada mês (a listagem não traz a data do pagamento, então buscamos mês a mês)
  const pagas = [];
  for (const m of meses) {
    const [r, p] = await Promise.all([
      ca.buscarParcelas('receber', { pagamento_de: `${m}-01`, pagamento_ate: fimDoMes(m) }),
      ca.buscarParcelas('pagar', { pagamento_de: `${m}-01`, pagamento_ate: fimDoMes(m) }),
    ]);
    pagas.push(...r.map((x) => ({ ...x, mes_pag: m })), ...p.map((x) => ({ ...x, mes_pag: m })));
  }
  const [recAb, pagAb] = await Promise.all([
    ca.buscarParcelas('receber', { vencimento_de: iso(new Date(hoje.getTime() - 400 * 864e5)), vencimento_ate: iso(new Date(hoje.getTime() + 100 * 864e5)) }),
    ca.buscarParcelas('pagar', { vencimento_de: iso(new Date(hoje.getTime() - 400 * 864e5)), vencimento_ate: iso(new Date(hoje.getTime() + 100 * 864e5)) }),
  ]);
  // base da inadimplência: tudo o que venceu nos últimos 90 dias (pago ou não)
  const d90 = iso(new Date(hoje.getTime() - 90 * 864e5));
  const vencidas90 = recAb.filter((x) => x.vencimento >= d90 && x.vencimento < iso(hoje)).reduce((s, x) => s + x.total, 0);
  const saldos = await ca.buscarSaldos().catch(() => []);
  return { meses, estrutura, comp: [...recComp, ...pagComp], pagas, abertos: [...recAb, ...pagAb].filter((x) => x.aberto > 0.009), saldos, vencidas90 };
}

// ---------- demonstração: parcelas fictícias no mesmo formato da API ----------
function prng(seed) { let s = seed >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32); }
function brutoDemo() {
  const r = prng(4242);
  const meses = mesesAte(config.mesesHistorico);
  const hoje = hojeBR();
  const fat = {};
  gerarDemoPlanilha().linhas.forEach((l) => { fat[l.mes] = (fat[l.mes] || 0) + l.total; });
  const cat = (id, nome) => ({ id, nome });
  const C = {
    venda: cat('c-venda', 'Venda de produtos'), imp: cat('c-imp', 'Simples Nacional'),
    tecido: cat('c-tec', 'Tecidos e aviamentos'), mo: cat('c-mo', 'Salários da produção'), sub: cat('c-sub', 'Sublimação e impressão terceirizada'),
    com: cat('c-com', 'Comissões de vendedores'), mkt: cat('c-mkt', 'Marketing e redes sociais'), frete: cat('c-fre', 'Fretes e entregas'),
    alug: cat('c-alu', 'Aluguel e condomínio'), adm: cat('c-adm', 'Salários administrativos'), ener: cat('c-ene', 'Energia e água'),
    cont: cat('c-con', 'Contabilidade e BPO'), sis: cat('c-sis', 'Sistemas e softwares'), tar: cat('c-tar', 'Tarifas bancárias e juros'),
  };
  // mesma estrutura de DRE cadastrada na Conta Azul da Visu
  const estrutura = [
    { descricao: 'Receita Bruta de Vendas', posicao: 1, subitens: [{ descricao: 'Receita de Vendas de Produtos e Serviços', posicao: 1, categorias_financeiras: [C.venda] }] },
    { descricao: 'Deduções da Receita Bruta', posicao: 2, subitens: [{ descricao: 'Impostos', posicao: 1, categorias_financeiras: [C.imp] }] },
    { descricao: 'Receita Líquida de Vendas', posicao: 3, indica_totalizador: true },
    { descricao: 'Custos de Produção', posicao: 4, subitens: [
      { descricao: 'Custos de Produção com Matéria Primas e Insumos (Variáveis)', posicao: 1, categorias_financeiras: [C.tecido, C.sub] },
      { descricao: 'Custos de Produção com Pessoal (Fixos)', posicao: 2, categorias_financeiras: [C.mo] }] },
    { descricao: 'Lucro Bruto', posicao: 5, indica_totalizador: true },
    { descricao: 'Despesas Operacionais', posicao: 6, subitens: [
      { descricao: 'Despesas Comerciais e Logísticas (Variáveis)', posicao: 1, categorias_financeiras: [C.com, C.frete] },
      { descricao: 'Despesas Comerciais e Marketing (Fixas)', posicao: 2, categorias_financeiras: [C.mkt] },
      { descricao: 'Despesas Gerais e Administrativas (Fixas)', posicao: 3, categorias_financeiras: [C.alug, C.ener, C.cont, C.sis] },
      { descricao: 'Despesas com Pessoal (Fixas)', posicao: 4, categorias_financeiras: [C.adm] }] },
    { descricao: 'Lucro / Prejuízo Operacional', posicao: 7, indica_totalizador: true },
    { descricao: 'Receitas e Despesas Financeiras', posicao: 8, subitens: [{ descricao: 'Despesas Financeiras', posicao: 1, categorias_financeiras: [C.tar] }] },
    { descricao: 'Lucro / Prejuízo Líquido', posicao: 9, indica_totalizador: true },
  ];
  const despesas = [[C.imp, 0.06, 'Receita Federal', 'Administrativo'], [C.tecido, 0.3, 'Fornecedor de tecidos', 'Produção'], [C.mo, 0.17, 'Folha de pagamento', 'Produção'], [C.sub, 0.04, 'Estamparia parceira', 'Produção'],
    [C.com, 0.035, 'Folha de pagamento', 'Comercial'], [C.mkt, 0.02, 'Agência de conteúdo', 'Comercial'], [C.frete, 0.015, 'Transportadora', 'Comercial'],
    [C.alug, 0.05, 'Imobiliária', 'Administrativo'], [C.adm, 0.13, 'Folha de pagamento', 'Administrativo'], [C.ener, 0.02, 'Concessionária', 'Produção'],
    [C.cont, 0.017, 'Escritório contábil', 'Administrativo'], [C.sis, 0.008, 'Sistemas', 'Administrativo'], [C.tar, 0.03, 'Banco', 'Financeiro']];
  const comp = [], pagas = [], abertos = [];
  const hojeIso = iso(hoje);
  let id = 0;
  const parc = (tipo, venc, total, categoria, pessoa, centro) => {
    const idade = (Date.parse(hojeIso) - Date.parse(venc)) / 864e5;
    const pago = venc < hojeIso && r() > (tipo === 'receber' ? (idade > 60 ? 0.008 : 0.07) : 0.02) ? total : 0;
    return { tipo, id: `d${id++}`, descricao: categoria.nome, vencimento: venc, competencia: venc, status: pago ? 'RECEBIDO' : venc < hojeIso ? 'ATRASADO' : 'EM_ABERTO', total, pago, aberto: total - pago, categorias: [categoria], centros: [centro], pessoa };
  };
  const mesesExt = [...meses, ...mesesAte(1).map(() => null)].filter(Boolean);
  for (const m of mesesExt) {
    const base = fat[m] || 150000;
    for (let i = 0; i < 18; i++) {
      const dia = String(1 + Math.floor(r() * 27)).padStart(2, '0');
      comp.push(parc('receber', `${m}-${dia}`, r2(base / 18 * (0.7 + r() * 0.6)), C.venda, `Cliente ${String(1 + Math.floor(r() * 60)).padStart(3, '0')}`, 'Comercial'));
    }
    for (const [c, f, pessoa, centro] of despesas) comp.push(parc('pagar', `${m}-${String(5 + Math.floor(r() * 20)).padStart(2, '0')}`, r2(base * f * (0.9 + r() * 0.2)), c, pessoa, centro));
  }
  // próximas semanas (a vencer) para a projeção
  for (let d = 1; d <= 95; d += 3) {
    const venc = iso(new Date(hoje.getTime() + d * 864e5));
    abertos.push(parc('receber', venc, r2(4200 + r() * 5200), C.venda, `Cliente ${String(1 + Math.floor(r() * 60)).padStart(3, '0')}`, 'Comercial'));
    if (d % 2) abertos.push(parc('pagar', venc, r2(5200 + r() * 6400), despesas[Math.floor(r() * despesas.length)][0], 'Fornecedor', 'Produção'));
  }
  for (const p of comp) {
    if (p.pago) pagas.push({ ...p, mes_pag: p.vencimento.slice(0, 7) });
    else if (p.aberto > 0) abertos.push(p);
  }
  const d90 = iso(new Date(hoje.getTime() - 90 * 864e5));
  const vencidas90 = comp.filter((x) => x.tipo === 'receber' && x.vencimento >= d90 && x.vencimento < hojeIso).reduce((s, x) => s + x.total, 0);
  return { meses, estrutura, comp, pagas, abertos, saldos: [{ nome: 'Conta corrente (exemplo)', saldo: 48210.55 }, { nome: 'Conta pagamentos (exemplo)', saldo: 12780.1 }], vencidas90 };
}

const cache = { dados: null, quando: 0, carregando: null };
export async function dadosFinanceiros(forcar = false) {
  const conectado = !config.demo && (await ca.statusConexao()).conectado;
  if (!conectado) return montar(brutoDemo(), 'demo');
  const vencido = Date.now() - cache.quando > Math.max(config.cacheSegundos, 600) * 1000;
  if (cache.dados && !vencido && !forcar) return cache.dados;
  cache.carregando ||= carregarConta()
    .then((b) => {
      cache.quando = Date.now(); cache.dados = montar(b, 'conta_azul');
      // v118.1: o dia de cada pagamento é buscado depois, em segundo plano (antes atrasava a primeira carga do financeiro)
      if (!cache.rateando) { cache.rateando = true; aplicarRateio(b).then((n) => { if (n) cache.dados = montar(b, 'conta_azul'); }).catch((e) => console.warn('[financeiro] rateio:', e.message)).finally(() => { cache.rateando = false; }); }
      if (!cache.refinando) { cache.refinando = true; refinarDatasPagamento(b.pagas, hojeBR()).then(() => { if (cache.quando && cache.dados?.fonte === 'conta_azul') cache.dados = montar(b, 'conta_azul'); }).catch((e) => console.warn('[financeiro] datas de pagamento:', e.message)).finally(() => { cache.refinando = false; }); }
      return cache.dados; })
    .finally(() => { cache.carregando = null; });
  if (cache.dados && !forcar) return cache.dados;
  return cache.carregando;
}
