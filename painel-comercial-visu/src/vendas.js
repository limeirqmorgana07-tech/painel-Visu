// Monta a base de vendas do painel: planilha (fonte principal) → Conta Azul (reserva) → demonstração.
// Também padroniza grafias e gera o relatório de qualidade dos dados (seção 5 da especificação).
import { config } from './config.js';
import * as ca from './contaAzul.js';
import { planilhaConfigurada, lerPlanilha, sem, clienteBase } from './planilha.js';
import { gerarDemoPlanilha } from './demo.js';

const chave = (s) => sem(s).replace(/[^a-z0-9]+/g, ' ').trim();

// Agrupa grafias diferentes do mesmo valor ("Poliamida", "poliamida ", "POLIAMIDA") e
// devolve, para cada uma, a grafia mais usada. Lista as variações encontradas.
function padronizar(linhas, campo) {
  const grupos = new Map();
  for (const l of linhas) {
    const original = l[campo];
    if (!original) continue;
    const k = chave(original);
    const g = grupos.get(k) || new Map();
    g.set(original, (g.get(original) || 0) + 1);
    grupos.set(k, g);
  }
  const canonico = new Map();
  const variacoes = [];
  for (const [k, g] of grupos) {
    const ordenado = [...g.entries()].sort((a, b) => b[1] - a[1]);
    canonico.set(k, ordenado[0][0].trim());
    if (ordenado.length > 1) variacoes.push({ valor: ordenado[0][0].trim(), grafias: ordenado.map(([t, n]) => ({ texto: t, linhas: n })) });
  }
  for (const l of linhas) if (l[campo]) l[campo] = canonico.get(chave(l[campo]));
  return variacoes.sort((a, b) => b.grafias.length - a.grafias.length);
}

function qualidade(linhas, mapa) {
  // clientes: mesmo nome com lote / caixa / acento / espaço diferentes
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
  // nomes de cliente iguais após padronizar → unifica a grafia exibida
  for (const l of linhas) {
    const g = porChave.get(chave(l.cliente));
    if (g && g.size > 1) l.cliente = clienteBase([...g.entries()].sort((a, b) => b[1] - a[1])[0][0]);
  }

  const vazio = (campo) => linhas.filter((l) => !l[campo]).length;
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
      pedido: linhas.filter((l) => !l.pedido_informado).length,
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

// Conta Azul como reserva: sem tecido/cor e sem a marcação novo x recompra da planilha
async function deContaAzul() {
  const agora = new Date(Date.now() - 3 * 3600e3);
  const inicio = new Date(Date.UTC(agora.getUTCFullYear(), agora.getUTCMonth() - 23, 1)).toISOString().slice(0, 10);
  const vendas = await ca.buscarVendas(inicio, agora.toISOString().slice(0, 10));
  const linhas = vendas
    .filter((v) => v.situacao !== 'CANCELADO' && v.situacao !== 'ORCAMENTO')
    .map((v) => ({
      linha: null, data: v.data, mes: v.data.slice(0, 7), cliente: clienteBase(v.cliente), cliente_original: v.cliente,
      pedido: String(v.numero ?? v.id), pedido_informado: true, vendedor: v.vendedor, tipo_venda: '—', novo_recompra: '',
      tipo_produto: '', material: '', especificacao: '', cor: '', quantidade: 0, total: v.total,
      pag1: 0, pag2: 0, pago_100: false, forma_pagamento: '', prazo_entrega: '', frete: '', segmento: '',
    }));
  return { linhas, mapa: null };
}

const cache = { dados: null, quando: 0, carregando: null };

async function carregar() {
  let origem, base, aviso = null;
  if (config.demo) { origem = 'demo'; base = gerarDemoPlanilha(); }
  else if (planilhaConfigurada()) { origem = 'planilha'; base = await lerPlanilha(); }
  else if ((await ca.statusConexao()).conectado) {
    origem = 'conta_azul'; base = await deContaAzul();
    aviso = 'Lendo as vendas da Conta Azul porque a planilha de vendas ainda não foi ligada. Tecido, cor e novo x recompra só aparecem com a planilha.';
  } else { origem = 'demo'; base = gerarDemoPlanilha(); }

  const linhas = base.linhas.filter((l) => l.total || l.quantidade);
  const q = qualidade(linhas, base.mapa);
  if (base.mapa?.obrigatorias_faltando?.length) {
    aviso = `A planilha não tem as colunas: ${base.mapa.obrigatorias_faltando.join(', ')}. Ajuste o nome no cabeçalho ou use COLUNAS_JSON.`;
  }
  // linhas compactas para o navegador (só o que o painel usa)
  const enxutas = linhas.map((l) => ({
    m: l.mes, d: l.data, c: l.cliente, p: l.pedido, v: l.vendedor, tv: l.tipo_venda, nr: l.novo_recompra,
    tp: l.tipo_produto, mt: l.material, es: l.especificacao, cr: l.cor, q: l.quantidade, t: Math.round(l.total * 100) / 100,
    p1: l.pag1, p2: l.pag2, ok: l.pago_100, sg: l.segmento,
  }));
  return {
    fonte: origem,
    atualizado_em: new Date().toISOString(),
    avisos: [aviso].filter(Boolean),
    regras: {
      ponto_equilibrio: config.pontoEquilibrio || null,
      meta: config.metaMensal || null,
      comissao_inicio: config.comissaoInicio,
      comissao_teto: config.comissaoTeto,
    },
    linhas: enxutas,
    qualidade: q,
  };
}

export async function dadosDeVendas(forcar = false) {
  const vencido = Date.now() - cache.quando > config.cacheSegundos * 1000;
  if (cache.dados && !vencido && !forcar) return cache.dados;
  cache.carregando ||= carregar()
    .then((d) => { cache.dados = d; cache.quando = Date.now(); return d; })
    .finally(() => { cache.carregando = null; });
  if (cache.dados && !forcar) return cache.dados; // devolve a versão anterior enquanto atualiza
  return cache.carregando;
}
