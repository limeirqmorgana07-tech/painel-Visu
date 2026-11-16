// Pedidos lançados no painel → vendas na Conta Azul (definido com a Visu em 08/11/2026):
// item = o tipo de produto escolhido no lançamento (produto com esse nome na Conta Azul; se não existir, é criado),
// condição de pagamento do campo Parcelas (padrão 50% + 50%, 2x; também à vista ou 3x ou mais), situação "aprovado" (desde a v91; antes "em andamento"), número da venda = código interno do pedido.
// Só vão os pedidos lançados no painel (os importados da planilha já são lançados na Conta Azul pela equipe).
// Pedido complementar (código com -1, -2…): vai como venda própria, com o sufixo colado no número (0021112026-1 → 211120261).
import * as ca from './contaAzul.js';
import * as cadastros from './cadastros.js';
import { config } from './config.js';
import * as pedidos from './pedidos.js';

const sem = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
const r2 = (v) => Math.round((Number(v) || 0) * 100) / 100;
const somaDias = (iso, d) => { const x = new Date(iso + 'T12:00:00Z'); x.setUTCDate(x.getUTCDate() + d); return x.toISOString().slice(0, 10); };

const FORMAS = [[/pix/, 'PIX_PAGAMENTO_INSTANTANEO'], [/boleto/, 'BOLETO_BANCARIO'], [/debito/, 'CARTAO_DEBITO'], [/credito|cartao/, 'CARTAO_CREDITO'], [/dinheiro|especie/, 'DINHEIRO'], [/transfer|ted|doc/, 'TRANSFERENCIA_BANCARIA'], [/deposito/, 'DEPOSITO_BANCARIO'], [/link/, 'LINK_PAGAMENTO']];
const tipoPagamento = (f) => { const s = sem(f); for (const [re, t] of FORMAS) if (re.test(s)) return t; return undefined; };

// 50% + 50%: 1ª parcela na data da venda, 2ª no prazo de entrega (ou 30 dias depois, sem prazo)
export function parcelas5050(total, data, prazo) {
  const p1 = r2(total / 2), p2 = r2(total - p1);
  const v2 = prazo && prazo >= data ? prazo : somaDias(data, 30);
  return [{ data_vencimento: data, valor: p1, descricao: 'Parcela 1 (50%)' }, { data_vencimento: v2, valor: p2, descricao: 'Parcela 2 (50%)' }];
}

// v92: nomes da condição personalizada, iguais aos do painel
export const nomeParcPers = (i, n) => (n <= 1 ? 'Pagamento único' : i === 0 ? 'Pagamento de entrada' : i === n - 1 ? 'Pagamento final (saldo)' : n > 3 ? `Pagamento complementar ${i}` : 'Pagamento complementar');
// condição do pedido: 1 = à vista (na data da venda), 2 = 50% + 50% (padrão), 3 ou mais = parcelas iguais a cada 30 dias
export function parcelasPedido(n, total, data, prazo, pers = []) {
  // personalizado: as parcelas como o vendedor montou (valor e data de cada uma); precisam somar o total do pedido
  if (n === 'P') {
    const ps = (pers || []).filter((p) => p.valor > 0);
    if (!ps.length) throw new Error('Parcelas personalizadas não preenchidas.');
    const soma = r2(ps.reduce((a2, p) => a2 + p.valor, 0));
    if (Math.abs(soma - total) > 0.05) throw new Error(`As parcelas personalizadas somam ${soma.toFixed(2)} e o pedido é ${total.toFixed(2)}.`);
    return ps.map((p, i) => ({ data_vencimento: p.data || data, valor: r2(p.valor), descricao: nomeParcPers(i, ps.length) }));
  }
  n = Math.max(1, Math.min(12, parseInt(n, 10) || 2));
  if (n === 2) return parcelas5050(total, data, prazo);
  if (n === 1) return [{ data_vencimento: data, valor: r2(total), descricao: 'À vista' }];
  const base = Math.floor((total / n) * 100) / 100, out = [];
  for (let i = 0; i < n; i++) out.push({ data_vencimento: i ? somaDias(data, 30 * i) : data, valor: i === n - 1 ? r2(total - base * (n - 1)) : base, descricao: `Parcela ${i + 1} de ${n}` });
  return out;
}
export const opcaoCondicao = (n, pers = []) => { if (n === 'P') { const k = (pers || []).filter((p) => p.valor > 0).length; return k <= 1 ? 'À vista' : `${k}x`; } n = parseInt(n, 10) || 2; return n === 1 ? 'À vista' : `${n}x`; };

// monta o corpo da venda de um pedido (todas as linhas com o mesmo código)
// v100: toda venda do painel entra na Conta Azul com a categoria financeira "Receita Geral de Vendas" (regra travada)
export const CATEGORIA_VENDA = 'Receita Geral de Vendas';
let catCache = null;
export async function idCategoriaVenda() {
  if (catCache && Date.now() - catCache.em < 6 * 3600e3) return catCache.id;
  const alvo = sem(CATEGORIA_VENDA); let id = null;
  const procura = (lista) => { for (const c of lista || []) { if (c && sem(c.nome || c.descricao) === alvo && c.id) return c.id; const f = procura(c?.subitens || c?.categorias_financeiras || c?.filhos); if (f) return f; } return null; };
  for (const [url, q] of [['/v1/categorias', { busca: CATEGORIA_VENDA, tipo: 'RECEITA', pagina: 1, tamanho_pagina: 50 }], ['/v1/categorias', { busca: CATEGORIA_VENDA }], ['/v1/financeiro/categorias-dre', {}]]) {
    try { const r = await ca.get(url, q); id = procura(r?.itens || r?.items || (Array.isArray(r) ? r : [])); if (id) break; } catch {}
  }
  if (!id) throw new Error(`Categoria "${CATEGORIA_VENDA}" não encontrada na Conta Azul: a venda não foi enviada. Confira se a categoria existe com esse nome.`);
  catCache = { id, em: Date.now() };
  return id;
}
export function corpoVenda(linhas, { idCliente, idVendedor, produtoDe, idCategoria }) {
  const c = linhas[0];
  const total = r2(linhas.reduce((s, l) => s + (Number(l.total) || r2((Number(l.quantidade) || 0) * (Number(l.valor_unit) || 0))), 0));
  const itens = linhas.map((l) => ({
    id: produtoDe(l.tipo_produto),
    descricao: [l.tipo_produto, l.material, l.cor, l.especificacao].filter(Boolean).join(' · ').slice(0, 250),
    quantidade: Number(l.quantidade) || 1,
    valor: r2(Number(l.valor_unit) || (Number(l.total) || 0) / (Number(l.quantidade) || 1)),
  }));
  const tp = tipoPagamento(c.forma_pagamento);
  // v110: pedido complementar herda a condição Personalizado do principal, mas as parcelas são do principal (somam outro valor).
  // Nesse caso o complementar vai numa parcela só, "Pagamento complementar", com vencimento no pagamento final do principal.
  let nParc = c.parcelas, pers = c.parcelas_pers;
  if (/-\d+$/.test(c.codigo) && nParc === 'P') {
    const ps = (pers || []).filter((p) => p.valor > 0), soma = r2(ps.reduce((a2, p) => a2 + p.valor, 0));
    if (!ps.length || Math.abs(soma - total) > 0.05) { nParc = 'P'; pers = [{ valor: total, data: ps.length ? ps[ps.length - 1].data || c.data : (c.prazo_entrega || c.data) }]; }
  }
  const corpo = {
    id_cliente: idCliente,
    numero: pedidos.numeroParaCA(c.codigo),
    // v91: os pedidos já chegam aprovados pela gestão (cotação e aprovação no CRM): a venda entra APROVADA na Conta Azul
    situacao: 'APROVADO',
    data_venda: c.data,
    itens,
    condicao_pagamento: { opcao_condicao_pagamento: opcaoCondicao(nParc, pers), parcelas: parcelasPedido(nParc, total, c.data, c.prazo_entrega, pers).map((p, i, arr) => (arr.length === 1 && /-\d+$/.test(c.codigo) && c.parcelas === 'P' ? { ...p, descricao: 'Pagamento complementar' } : p)), ...(tp ? { tipo_pagamento: tp } : {}) },
    observacoes: [/-\d+$/.test(c.codigo) ? `Pedido complementar ${c.codigo} (acréscimo ao pedido ${pedidos.codigoBase(c.codigo)}) lançado no Painel de Gestão Visu` : `Pedido ${c.codigo} lançado no Painel de Gestão Visu`, c.nome_pedido ? `Pedido (Trello): ${c.nome_pedido}` : '', c.lote ? `Lote / obs.: ${c.lote}` : '', c.observacao || ''].filter(Boolean).join(' · ').slice(0, 1000),
  };
  if (idVendedor) corpo.id_vendedor = idVendedor;
  if (idCategoria) corpo.id_categoria = idCategoria;
  return corpo;
}

// pedidos do painel ainda não enviados, agrupados pelo código
export function pendentesDeEnvio(regs, desde) {
  const g = new Map();
  for (const r of regs) {
    if (r.excluido || r.origem !== 'painel' || !r.codigo || r.ca_venda_id) continue;
    if (desde && (r.data || '') < desde) continue;
    (g.get(r.codigo) || g.set(r.codigo, []).get(r.codigo)).push(r);
  }
  return g;
}

let rodando = null;
export async function enviarPedidos(u, { codigos = null } = {}) {
  if (rodando) return rodando;
  rodando = (async () => {
    const cfg = await pedidos.configPedidos();
    const regs = await pedidos.listar();
    const pend = pendentesDeEnvio(regs, cfg.enviar_ca_desde || null);
    const alvo = [...pend.entries()].filter(([cod]) => !codigos || codigos.includes(cod));
    const res = { enviados: [], ja_existiam: [], erros: [], complementares: 0 };
    if (!alvo.length) return res;
    if (!config.demo && !(await ca.statusConexao().catch(() => ({}))).conectado) throw new Error('A Conta Azul não está conectada.');
    // listas da Conta Azul (uma vez por envio)
    const clientes = config.demo ? [] : await ca.buscarClientes().catch(() => []);
    const vendedores = config.demo ? [] : await ca.buscarVendedores().catch(() => []);
    const cliPorNome = new Map(clientes.filter((c) => c.id).map((c) => [sem(c.nome), c.id]));
    const cadPorNome = new Map((await cadastros.listarClientes().catch(() => [])).map((x) => [sem(x.nome), x]));
    const vendPorNome = (n) => { const k = sem(n); if (!k) return null; const v = vendedores.find((x) => sem(x.nome) === k) || vendedores.find((x) => sem(x.nome).split(' ')[0] === k.split(' ')[0]); return v?.id || null; };
    const numerosCA = new Set();
    if (!config.demo) { const de = alvo.map(([, ls]) => ls[0].data).sort()[0]; (await ca.buscarVendas(de, new Date().toISOString().slice(0, 10)).catch(() => [])).forEach((v) => v.numero != null && numerosCA.add(String(v.numero))); }
    const prodCache = new Map();
    const produtoId = async (nome) => {
      const k = sem(nome); if (!k) throw new Error('Item sem tipo de produto.');
      if (prodCache.has(k)) return prodCache.get(k);
      let id;
      if (config.demo) id = 'demo-prod-' + k.replace(/ /g, '-');
      else { const achados = await ca.buscarProdutos(nome); id = achados.find((p) => sem(p.nome) === k)?.id || (await ca.criarProduto(nome)).id; }
      if (!id) throw new Error(`Não foi possível achar nem criar o produto "${nome}" na Conta Azul.`);
      prodCache.set(k, id); return id;
    };
    for (const [cod, linhas] of alvo) {
      const ids = linhas.map((l) => l.id), numero = String(pedidos.numeroParaCA(cod));
      try {
        if (numerosCA.has(numero)) { await pedidos.marcarEnvioCA(ids, { ca_venda_id: 'ja-existia', ca_erro: '', ca_obs: 'Já existia venda com este número na Conta Azul' }, u); res.ja_existiam.push(cod); continue; }
        const c = linhas[0];
        // v109: cliente novo do painel vai obrigatoriamente para a Conta Azul (com os dados do cadastro do painel)
        const cad = cadPorNome.get(sem(c.cliente));
        const novoCliente = async () => { const n = await ca.criarCliente({ nome: c.cliente, tipo: cad?.tipo || (c.tipo_venda === 'B2C' ? 'Física' : 'Jurídica'), documento: cad?.documento, email: cad?.email, telefone: cad?.telefone }); cliPorNome.set(sem(c.cliente), n.id); await cadastros.marcarClienteCA(c.cliente, n.id).catch(() => {}); return n.id; };
        let idCliente = cliPorNome.get(sem(c.cliente)) || cad?.ca_id || null;
        if (!idCliente) idCliente = config.demo ? 'demo-cli' : ((await ca.buscarClientePorNome(c.cliente).catch(() => null))?.id || await novoCliente());
        const prodIds = new Map();
        for (const l of linhas) prodIds.set(sem(l.tipo_produto), await produtoId(l.tipo_produto));
        const idCategoria = config.demo ? 'demo-categoria' : await idCategoriaVenda();
        const corpo = corpoVenda(linhas, { idCliente, idVendedor: vendPorNome(c.vendedor), produtoDe: (n) => prodIds.get(sem(n)), idCategoria });
        let v;
        if (config.demo) v = { id: 'demo-venda-' + numero };
        else {
          try { v = await ca.criarVenda(corpo); }
          catch (e) {
            if (!/cliente/i.test(e.message) || !/n[ãa]o encontrad/i.test(e.message)) throw e;
            // o código guardado não vale mais na Conta Azul: procura de novo pelo nome; se não existir, cadastra e tenta outra vez
            cliPorNome.delete(sem(c.cliente));
            corpo.id_cliente = (await ca.buscarClientePorNome(c.cliente).catch(() => null))?.id || await novoCliente();
            v = await ca.criarVenda(corpo);
          }
        }
        await pedidos.marcarEnvioCA(ids, { ca_venda_id: v.id || 'enviado', ca_enviado_em: new Date().toISOString(), ca_erro: '', ca_total: corpo.condicao_pagamento.parcelas.reduce((s, p) => s + p.valor, 0) }, u);
        res.enviados.push(cod);
      } catch (e) {
        await pedidos.marcarEnvioCA(ids, { ca_erro: e.message.slice(0, 300), ca_tentativa_em: new Date().toISOString() }, u).catch(() => {});
        res.erros.push({ codigo: cod, erro: e.message });
      }
    }
    return res;
  })().finally(() => { rodando = null; });
  return rodando;
}
