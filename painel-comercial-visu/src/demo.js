// Dados FICTÍCIOS no formato da planilha de vendas, para ver o painel antes de ligar a planilha real.
// Produtos e tecidos vêm do catálogo da Visu; clientes, vendedores e valores são inventados.
// Algumas grafias erradas são colocadas de propósito para a página "Qualidade dos dados" ter o que mostrar.
function prng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
}

function escolher(r, lista) {
  const total = lista.reduce((s, x) => s + x[1], 0);
  let x = r() * total;
  for (const [v, p] of lista) { if ((x -= p) <= 0) return v; }
  return lista[lista.length - 1][0];
}

const PRODUTOS = [
  ['Camiseta básica', 40, 38], ['Camiseta gola polo', 12, 62], ['Baby look', 10, 40], ['Regata machão', 9, 36],
  ['Regata cavada', 6, 34], ['Cropped', 5, 39], ['Ecobag', 4, 28], ['Sacola esportiva', 4, 32],
  ['Headband', 3, 18], ['Munhequeira', 3, 16], ['Bandeira', 4, 160],
];
const MATERIAIS = [['Poliamida', 44], ['Dry-fit poliéster', 24], ['100% algodão', 22], ['Dry-fit poliamida', 10]];
const CORES = [['Preto', 36], ['Branco', 26], ['Azul marinho', 12], ['Cinza', 8], ['Vermelho', 6], ['Verde', 6], ['Rosa', 6]];
const VENDEDORES = [['Vendedora A', 34], ['Vendedor B', 28], ['Vendedora C', 22], ['Vendedor D', 16]];
const CLIENTES_FIXOS = ['Cliente Indústria 01', 'Academia Exemplo', 'Escola Modelo', 'Assessoria Corrida X', 'Clínica Exemplo', 'Igreja Exemplo'];

export function gerarDemoPlanilha() {
  const r = prng(20261008);
  const agora = new Date(Date.now() - 3 * 3600e3);
  const linhas = [];
  const jaComprou = new Set();
  let cod = 4100;
  let novos = 0;
  for (let m = 13; m >= 0; m--) {
    const ini = new Date(Date.UTC(agora.getUTCFullYear(), agora.getUTCMonth() - m, 1));
    const dias = new Date(Date.UTC(ini.getUTCFullYear(), ini.getUTCMonth() + 1, 0)).getUTCDate();
    const sazonal = 1 + 0.2 * Math.sin(((ini.getUTCMonth() + 3) / 12) * 2 * Math.PI) + (13 - m) * 0.015;
    const pedidos = Math.round((44 + r() * 12) * sazonal);
    for (let k = 0; k < pedidos; k++) {
      const dia = 1 + Math.floor(r() * dias);
      const data = new Date(Date.UTC(ini.getUTCFullYear(), ini.getUTCMonth(), dia));
      if (data > agora) continue;
      const iso = data.toISOString().slice(0, 10);
      // cliente: 28% de chance de ser alguém novo
      let cliente;
      if (r() < 0.28 || jaComprou.size < 12) cliente = `Cliente ${String(++novos).padStart(3, '0')}`;
      else cliente = r() < 0.25 ? CLIENTES_FIXOS[Math.floor(r() * CLIENTES_FIXOS.length)] : [...jaComprou][Math.floor(Math.pow(r(), 1.3) * jaComprou.size)];
      const marcadoNovo = !jaComprou.has(cliente);
      jaComprou.add(cliente);
      let nomeLancado = cliente;
      if (cliente === 'Cliente Indústria 01' && r() < 0.6) nomeLancado = `Cliente Indústria 01 lote ${1 + Math.floor(r() * 3)}`;
      if (cliente === 'Academia Exemplo' && r() < 0.15) nomeLancado = 'academia exemplo';
      const vendedor = escolher(r, VENDEDORES);
      const tipoVenda = r() < 0.82 ? 'B2B' : 'B2C';
      const itens = 1 + Math.floor(r() * r() * 3);
      cod++;
      const prazo = new Date(data.getTime() + (10 + Math.floor(r() * 12)) * 864e5).toISOString().slice(0, 10);
      const entregue = prazo < agora.toISOString().slice(0, 10);
      const xp = r();
      const pagto = xp < 0.3 ? { p1: 1, p2: 0, ok: true, fp: 'Cartão de crédito' } : { p1: 1, p2: entregue ? 1 : 0, ok: entregue || xp > 0.9, fp: 'Pix: sinal de 60% e saldo na entrega' };
      if (r() < 0.06) { pagto.p1 = 0; pagto.ok = false; }
      for (let i = 0; i < itens; i++) {
        const nomeProd = escolher(r, PRODUTOS.map((p) => [p[0], p[1]]));
        const prod = PRODUTOS.find((p) => p[0] === nomeProd);
        let material = escolher(r, MATERIAIS);
        let cor = material === 'Dry-fit poliéster' && r() < 0.7 ? 'Branco' : material === 'Poliamida' && r() < 0.5 ? 'Preto' : escolher(r, CORES);
        const especificacao = material === 'Dry-fit poliéster' ? 'Sublimação' : r() < 0.6 ? 'Silk' : 'Bordado';
        if (material === 'Poliamida' && r() < 0.1) material = 'poliamida ';
        if (cor === 'Preto' && r() < 0.08) cor = 'PRETO';
        if (cor === 'Azul marinho' && r() < 0.2) cor = 'Azul Marinho';
        const qtd = prod[0] === 'Bandeira' ? 1 + Math.floor(r() * 3) : 10 + Math.floor(Math.pow(r(), 1.6) * 140);
        const unit = Math.round(prod[2] * (0.92 + r() * 0.2) * 100) / 100;
        linhas.push({
          linha: linhas.length + 2, data: iso, mes: iso.slice(0, 7),
          cliente: nomeLancado.replace(/\s*lote\s*\d+$/i, ''), cliente_original: nomeLancado,
          pedido: `VS-${cod}`, pedido_informado: true, vendedor, tipo_venda: tipoVenda,
          novo_recompra: r() < 0.03 ? '' : marcadoNovo ? 'novo' : 'recompra',
          tipo_produto: prod[0], material, especificacao, cor,
          quantidade: qtd, total: Math.round(qtd * unit * 100) / 100, custo: Math.round(qtd * unit * (0.5 + r() * 0.16) * 100) / 100,
          pag1: pagto.p1, pag2: pagto.p2, pago_100: pagto.ok, forma_pagamento: pagto.fp, prazo_entrega: prazo, frete: '', segmento: '',
        });
      }
    }
  }
  return { linhas, mapa: { linha_cabecalho: 1, reconhecidas: {}, nao_encontradas: [], obrigatorias_faltando: [], colunas_da_planilha: [], demonstracao: true } };
}

// Vendas FICTÍCIAS "do sistema", derivadas dos pedidos da planilha de exemplo, com as diferenças
// típicas entre planilha e Conta Azul: pedido não lançado, venda ainda em andamento,
// lançamento com data do mês seguinte e valor ajustado (frete ou peças extras).
export function gerarDemoContaAzul(linhasPlanilha) {
  const r = prng(777);
  const pedidos = new Map();
  for (const l of linhasPlanilha) {
    const p = pedidos.get(l.pedido) || { data: l.data, cliente: l.cliente, vendedor: l.vendedor, total: 0 };
    p.total += l.total; pedidos.set(l.pedido, p);
  }
  const vendas = [];
  let n = 9000;
  for (const [cod, p] of pedidos) {
    const x = r();
    if (x < 0.05) continue; // não lançado no sistema
    let data = p.data, situacao = 'APROVADO', total = p.total;
    if (x < 0.1) situacao = 'EM_ANDAMENTO';
    else if (x < 0.14) { const d = new Date(p.data); d.setUTCDate(d.getUTCDate() + 12); data = d.toISOString().slice(0, 10); }
    else if (x < 0.2) total = Math.round(p.total * (1 + (r() * 0.08 - 0.03)) * 100) / 100;
    if (r() < 0.02) situacao = 'CANCELADO';
    if (data > new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10)) continue;
    const criado = x >= 0.14 && x < 0.17 ? new Date(new Date(data).getTime() + 35 * 864e5).toISOString().slice(0, 10) : data;
    vendas.push({ id: `ca-${cod}`, numero: n++, data, criado_em: criado, cliente: p.cliente, vendedor: p.vendedor, situacao, total, versao: 1 });
  }
  return vendas;
}
