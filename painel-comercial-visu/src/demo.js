// Dados fictícios para visualizar o painel antes da conexão com a Conta Azul.
// Nomes genéricos de propósito: nada aqui representa clientes ou vendas reais da Visu.
function prng(seed) {
  let s = seed >>> 0;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
}

const VENDEDORES = ['Vendedor 1', 'Vendedor 2', 'Vendedor 3', 'Vendedor 4', 'Venda direta'];
const PESO_VEND = [0.32, 0.26, 0.2, 0.14, 0.08];
const PRODUTOS = Array.from({ length: 14 }, (_, i) => ({ nome: `Produto ${String.fromCharCode(65 + i)}`, preco: 180 + ((i * 397) % 1900) }));
const CLIENTES = Array.from({ length: 70 }, (_, i) => `Cliente ${String(i + 1).padStart(3, '0')}`);

function escolher(r, lista, pesos) {
  if (!pesos) return lista[Math.floor(r() * lista.length)];
  let x = r();
  for (let i = 0; i < lista.length; i++) { if ((x -= pesos[i]) <= 0) return lista[i]; }
  return lista[lista.length - 1];
}

export function gerarDemo() {
  const r = prng(20261008);
  const agora = new Date(Date.now() - 3 * 3600e3);
  const vendas = [];
  const itens = new Map();
  let numero = 1000;
  for (let m = 11; m >= 0; m--) {
    const dt = new Date(Date.UTC(agora.getUTCFullYear(), agora.getUTCMonth() - m, 1));
    const dias = new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth() + 1, 0)).getUTCDate();
    const sazonal = 1 + 0.18 * Math.sin((dt.getUTCMonth() + 2) / 12 * 2 * Math.PI) + (11 - m) * 0.012;
    const qtd = Math.round((38 + r() * 14) * sazonal);
    for (let k = 0; k < qtd; k++) {
      const dia = 1 + Math.floor(r() * dias);
      const data = new Date(Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth(), dia));
      if (data > agora) continue;
      const id = `demo-${numero}`;
      const linhas = [];
      const n = 1 + Math.floor(r() * 3);
      for (let j = 0; j < n; j++) {
        const p = PRODUTOS[Math.floor(Math.pow(r(), 1.7) * PRODUTOS.length)];
        const q = 1 + Math.floor(r() * 4);
        linhas.push({ nome: p.nome, quantidade: q, total: Math.round(p.preco * q * (0.9 + r() * 0.2) * 100) / 100 });
      }
      const total = linhas.reduce((s, l) => s + l.total, 0);
      const x = r();
      const situacao = x < 0.06 ? 'CANCELADO' : x < 0.16 ? 'ORCAMENTO' : x < 0.24 ? 'EM_ANDAMENTO' : x < 0.62 ? 'FATURADO' : 'APROVADO';
      vendas.push({
        id, numero: String(numero++), data: data.toISOString().slice(0, 10),
        cliente: CLIENTES[Math.floor(Math.pow(r(), 1.4) * CLIENTES.length)],
        vendedor: escolher(r, VENDEDORES, PESO_VEND), situacao, total,
      });
      itens.set(id, linhas);
    }
  }
  const hoje = agora.toISOString().slice(0, 10);
  const receber = vendas
    .filter((v) => v.situacao === 'FATURADO' || v.situacao === 'APROVADO')
    .flatMap((v) => {
      const parcelas = v.total > 3000 ? 3 : 1;
      return Array.from({ length: parcelas }, (_, i) => {
        const venc = new Date(new Date(v.data).getTime() + (30 * (i + 1)) * 864e5).toISOString().slice(0, 10);
        const valor = v.total / parcelas;
        const idadeDias = (Date.parse(hoje) - Date.parse(venc)) / 864e5;
        const pagoNoPrazo = venc < hoje && r() > (idadeDias > 60 ? 0.02 : 0.15);
        return {
          id: `${v.id}-${i}`, descricao: `Venda ${v.numero} (${i + 1}/${parcelas})`, cliente: v.cliente,
          vencimento: venc, valor,
          status: pagoNoPrazo ? 'RECEBIDO' : venc < hoje ? 'ATRASADO' : 'EM_ABERTO',
          pago: pagoNoPrazo ? valor : 0, aberto: pagoNoPrazo ? 0 : valor,
        };
      });
    });
  return { vendas, receber, itens, erroReceber: null };
}
