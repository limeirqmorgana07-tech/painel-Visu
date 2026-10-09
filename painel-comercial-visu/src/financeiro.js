// Gestão financeira a partir da Conta Azul (API v2): DRE por competência, caixa realizado,
// contas a receber e a pagar em aberto e saldos bancários.
import { config } from './config.js';
import * as ca from './contaAzul.js';

const iso = (d) => d.toISOString().slice(0, 10);
const hojeBR = () => new Date(Date.now() - 3 * 3600e3);
const mesesAte = (n) => {
  const a = hojeBR(); const out = [];
  for (let i = n - 1; i >= 0; i--) { const d = new Date(Date.UTC(a.getUTCFullYear(), a.getUTCMonth() - i, 1)); out.push(iso(d).slice(0, 7)); }
  return out;
};
const fimDoMes = (m) => { const [a, b] = m.split('-').map(Number); return iso(new Date(Date.UTC(a, b, 0))); };

// Achata a estrutura de DRE da Conta Azul (itens com subitens) mantendo a ordem e o nível
function achatarDRE(itens, nivel = 0, out = []) {
  for (const it of [...itens].sort((a, b) => (a.posicao ?? 0) - (b.posicao ?? 0))) {
    out.push({ id: it.id, descricao: it.descricao, codigo: it.codigo || '', nivel, totalizador: !!it.indica_totalizador, categorias: (it.categorias_financeiras || []).map((c) => c.id) });
    if (it.subitens?.length) achatarDRE(it.subitens, nivel + 1, out);
  }
  return out;
}

// valor com sinal: receita soma, despesa subtrai; rateio igual entre as categorias da parcela
function lancamentos(parcelas, campoValor) {
  const out = [];
  for (const p of parcelas) {
    const sinal = p.tipo === 'receber' ? 1 : -1;
    const valor = p[campoValor] * sinal;
    const cats = p.categorias.length ? p.categorias : [{ id: null, nome: p.tipo === 'receber' ? 'Receitas sem categoria' : 'Despesas sem categoria' }];
    for (const c of cats) out.push({ ...p, categoria_id: c.id, categoria: c.nome, valor: valor / cats.length });
  }
  return out;
}

function montarDRE(estrutura, lancs, meses, campoMes) {
  const plano = achatarDRE(estrutura);
  const porCategoria = new Map(); // id da categoria → índice da linha da DRE
  plano.forEach((l, i) => l.categorias.forEach((c) => porCategoria.set(c, i)));
  const linhas = plano.map((l) => ({ ...l, valores: Object.fromEntries(meses.map((m) => [m, 0])), categoriasDetalhe: {} }));
  const semLugar = { descricao: 'Lançamentos sem categoria na DRE', nivel: 0, totalizador: false, valores: Object.fromEntries(meses.map((m) => [m, 0])), categoriasDetalhe: {} };
  for (const x of lancs) {
    const m = x[campoMes]?.slice(0, 7);
    if (!meses.includes(m)) continue;
    const i = porCategoria.get(x.categoria_id);
    const alvo = i === undefined ? semLugar : linhas[i];
    alvo.valores[m] += x.valor;
    alvo.categoriasDetalhe[x.categoria] ||= Object.fromEntries(meses.map((mm) => [mm, 0]));
    alvo.categoriasDetalhe[x.categoria][m] += x.valor;
  }
  // cada item soma as próprias categorias + subitens; totalizadores = acumulado dos itens de nível 0 acima (cascata da DRE)
  const proprio = linhas.map((l) => ({ ...l.valores }));
  for (let i = 0; i < linhas.length; i++) {
    const l = linhas[i];
    if (l.totalizador) continue;
    let j = i + 1;
    while (j < linhas.length && linhas[j].nivel > l.nivel) {
      if (!linhas[j].totalizador) for (const m of meses) l.valores[m] += proprio[j][m];
      j++;
    }
  }
  const acum = Object.fromEntries(meses.map((m) => [m, 0]));
  for (const l of linhas) {
    if (l.nivel !== 0) continue;
    if (l.totalizador) { for (const m of meses) l.valores[m] = acum[m]; }
    else for (const m of meses) acum[m] += l.valores[m];
  }
  const todas = semLugar && Object.values(semLugar.valores).some((v) => Math.abs(v) > 0.009) ? [...linhas, semLugar] : linhas;
  const resultado = Object.fromEntries(meses.map((m) => [m, acum[m] + semLugar.valores[m]]));
  return { linhas: todas.filter((l) => l.totalizador || Object.values(l.valores).some((v) => Math.abs(v) > 0.009)), resultado };
}

// sem estrutura de DRE: agrupa por categoria, receitas e despesas
function dreSimples(lancs, meses, campoMes) {
  const grupos = { receber: new Map(), pagar: new Map() };
  for (const x of lancs) {
    const m = x[campoMes]?.slice(0, 7);
    if (!meses.includes(m)) continue;
    const g = grupos[x.tipo];
    const v = g.get(x.categoria) || Object.fromEntries(meses.map((mm) => [mm, 0]));
    v[m] += x.valor; g.set(x.categoria, v);
  }
  const bloco = (titulo, mapa) => {
    const tot = Object.fromEntries(meses.map((m) => [m, [...mapa.values()].reduce((s, v) => s + v[m], 0)]));
    return [{ descricao: titulo, nivel: 0, totalizador: false, valores: tot },
      ...[...mapa.entries()].sort((a, b) => Math.abs(Object.values(b[1]).reduce((s, x) => s + x, 0)) - Math.abs(Object.values(a[1]).reduce((s, x) => s + x, 0)))
        .map(([nome, v]) => ({ descricao: nome, nivel: 1, totalizador: false, valores: v }))];
  };
  const linhas = [...bloco('Receitas', grupos.receber), ...bloco('Despesas', grupos.pagar)];
  const resultado = Object.fromEntries(meses.map((m) => [m, linhas.filter((l) => l.nivel === 0).reduce((s, l) => s + l.valores[m], 0)]));
  linhas.push({ descricao: 'Resultado', nivel: 0, totalizador: true, valores: resultado });
  return { linhas, resultado };
}

async function carregarConta() {
  const meses = mesesAte(config.mesesHistorico);
  const ini = `${meses[0]}-01`, fim = fimDoMes(meses[meses.length - 1]);
  const [estrutura, recComp, pagComp] = await Promise.all([
    ca.buscarEstruturaDRE().catch(() => []),
    ca.buscarParcelas('receber', { competencia_de: ini, competencia_ate: fim }),
    ca.buscarParcelas('pagar', { competencia_de: ini, competencia_ate: fim }),
  ]);
  // caixa: o que foi efetivamente recebido/pago em cada mês
  const caixa = {};
  for (const m of meses) {
    const [r, p] = await Promise.all([
      ca.buscarParcelas('receber', { pagamento_de: `${m}-01`, pagamento_ate: fimDoMes(m) }),
      ca.buscarParcelas('pagar', { pagamento_de: `${m}-01`, pagamento_ate: fimDoMes(m) }),
    ]);
    caixa[m] = { entradas: r.reduce((s, x) => s + x.pago, 0), saidas: p.reduce((s, x) => s + x.pago, 0) };
  }
  const hoje = hojeBR();
  const [recAb, pagAb] = await Promise.all([
    ca.buscarParcelas('receber', { vencimento_de: iso(new Date(hoje.getTime() - 400 * 864e5)), vencimento_ate: iso(new Date(hoje.getTime() + 120 * 864e5)) }),
    ca.buscarParcelas('pagar', { vencimento_de: iso(new Date(hoje.getTime() - 400 * 864e5)), vencimento_ate: iso(new Date(hoje.getTime() + 120 * 864e5)) }),
  ]);
  const saldos = await ca.buscarSaldos().catch(() => []);
  return { meses, estrutura, comp: [...recComp, ...pagComp], caixa, abertos: [...recAb, ...pagAb].filter((x) => x.aberto > 0.009), saldos };
}

function montar(bruto, fonte) {
  const { meses, estrutura, comp, caixa, abertos, saldos } = bruto;
  const lancs = lancamentos(comp, 'total');
  const dre = estrutura?.length ? montarDRE(estrutura, lancs, meses, 'competencia') : dreSimples(lancs, meses, 'competencia');
  const receita = Object.fromEntries(meses.map((m) => [m, lancs.filter((x) => x.tipo === 'receber' && x.competencia.slice(0, 7) === m).reduce((s, x) => s + x.valor, 0)]));
  const despesa = Object.fromEntries(meses.map((m) => [m, -lancs.filter((x) => x.tipo === 'pagar' && x.competencia.slice(0, 7) === m).reduce((s, x) => s + x.valor, 0)]));
  const hoje = iso(hojeBR());
  const em30 = iso(new Date(hojeBR().getTime() + 30 * 864e5));
  const resumoAbertos = (tipo) => {
    const xs = abertos.filter((x) => x.tipo === tipo);
    const atras = xs.filter((x) => x.vencimento < hoje);
    const prox = xs.filter((x) => x.vencimento >= hoje && x.vencimento <= em30);
    return {
      total: xs.reduce((s, x) => s + x.aberto, 0), qtd: xs.length,
      atrasado: atras.reduce((s, x) => s + x.aberto, 0), atrasado_qtd: atras.length,
      prox30: prox.reduce((s, x) => s + x.aberto, 0), prox30_qtd: prox.length,
      maiores_atrasos: atras.sort((a, b) => b.aberto - a.aberto).slice(0, 8).map((x) => ({ pessoa: x.pessoa, descricao: x.descricao, vencimento: x.vencimento, aberto: x.aberto })),
      proximos: prox.sort((a, b) => a.vencimento.localeCompare(b.vencimento)).slice(0, 10).map((x) => ({ pessoa: x.pessoa, descricao: x.descricao, vencimento: x.vencimento, aberto: x.aberto })),
    };
  };
  return {
    fonte,
    atualizado_em: new Date().toISOString(),
    meses,
    ponto_equilibrio: config.pontoEquilibrio || null,
    dre: dre.linhas.map((l) => ({ descricao: l.descricao, codigo: l.codigo || '', nivel: l.nivel, totalizador: l.totalizador, valores: l.valores })),
    resultado: dre.resultado,
    receita, despesa,
    caixa,
    receber: resumoAbertos('receber'),
    pagar: resumoAbertos('pagar'),
    saldos,
    sem_categoria: lancs.filter((x) => !x.categoria_id).length,
  };
}

// ---------- demonstração ----------
import { gerarDemoPlanilha } from './demo.js';
function demo() {
  const meses = mesesAte(config.mesesHistorico);
  const fat = {};
  gerarDemoPlanilha().linhas.forEach((l) => { fat[l.mes] = (fat[l.mes] || 0) + l.total; });
  const v = (m, f) => Math.round((fat[m] || 0) * f * 100) / 100;
  const L = (descricao, nivel, totalizador, fn) => ({ descricao, nivel, totalizador, valores: Object.fromEntries(meses.map((m) => [m, fn(m)])) });
  const dre = [
    L('Receita operacional bruta', 0, false, (m) => v(m, 1)),
    L('Venda de produtos', 1, false, (m) => v(m, 1)),
    L('Deduções (impostos sobre vendas)', 0, false, (m) => -v(m, 0.06)),
    L('Receita líquida', 0, true, (m) => v(m, 0.94)),
    L('Custos de produção', 0, false, (m) => -v(m, 0.52)),
    L('Tecidos e aviamentos', 1, false, (m) => -v(m, 0.31)),
    L('Mão de obra da produção', 1, false, (m) => -v(m, 0.17)),
    L('Sublimação e impressão', 1, false, (m) => -v(m, 0.04)),
    L('Lucro bruto', 0, true, (m) => v(m, 0.42)),
    L('Despesas comerciais', 0, false, (m) => -v(m, 0.09)),
    L('Despesas administrativas', 0, false, (m) => -v(m, 0.27)),
    L('Despesas financeiras', 0, false, (m) => -v(m, 0.03)),
    L('Resultado líquido', 0, true, (m) => v(m, 0.03)),
  ];
  const resultado = dre[dre.length - 1].valores;
  const caixa = Object.fromEntries(meses.map((m, i) => [m, { entradas: v(meses[Math.max(i - 1, 0)], 0.55) + v(m, 0.42), saidas: v(m, 0.95) }]));
  const ab = (t) => ({ total: t, qtd: 34, atrasado: t * 0.12, atrasado_qtd: 4, prox30: t * 0.55, prox30_qtd: 18, maiores_atrasos: [], proximos: [] });
  return {
    fonte: 'demo', atualizado_em: new Date().toISOString(), meses, ponto_equilibrio: config.pontoEquilibrio || null,
    dre, resultado, receita: dre[0].valores, despesa: Object.fromEntries(meses.map((m) => [m, v(m, 0.97)])), caixa,
    receber: ab(96500), pagar: ab(71200), saldos: [{ nome: 'Conta corrente (exemplo)', saldo: 48210.55 }, { nome: 'Conta pagamentos (exemplo)', saldo: 12780.1 }], sem_categoria: 0,
  };
}

const cache = { dados: null, bruto: null, quando: 0, carregando: null };
export async function dadosFinanceiros(forcar = false) {
  const conectado = !config.demo && (await ca.statusConexao()).conectado;
  if (!conectado) return demo();
  const vencido = Date.now() - cache.quando > Math.max(config.cacheSegundos, 600) * 1000;
  if (cache.dados && !vencido && !forcar) return cache.dados;
  cache.carregando ||= carregarConta()
    .then((b) => { cache.bruto = b; cache.quando = Date.now(); cache.dados = montar(b, 'conta_azul'); return cache.dados; })
    .finally(() => { cache.carregando = null; });
  if (cache.dados && !forcar) return cache.dados;
  return cache.carregando;
}
