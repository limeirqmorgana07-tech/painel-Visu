// Divergências (Conferência): fechamento mensal no formato validado com a Visu em 08/11/2026.
// Comercial: total do mês na planilha de vendas × vendas do Conta Azul, com observações e ações por responsável.
// Financeiro: saldo no fim do mês, extrato × Conta Azul, para cada conta (status conferido, incompleto ou diferença).
// Os totais do comercial são recalculados no painel a cada atualização; aqui ficam as observações, as ações,
// o fechamento validado de cada mês e os saldos das contas (editáveis pela gestão).
import { lerKV, salvarKV } from './tokenStore.js';

const CHAVE = 'divergencias';
let memo = null;

const C = 'conferido', I = 'incompleto';
const mesesFin = ['2026-08', '2026-09', '2026-10', '2026-11'];
const conta = (nome, tipo, vals) => ({
  nome, tipo,
  meses: Object.fromEntries(mesesFin.map((m, i) => {
    const v = vals[i];
    if (v === C) return [m, { status: C, dif: 0 }];
    if (v === I) return [m, { status: I }];
    return [m, { status: 'dif', dif: v }];
  })),
});

// fechamento validado (imagens enviadas pela Morgana em 08/11/2026)
export const SEMENTE = () => ({
  versao: 1,
  comercial: {
    '2026-08': {
      fechamento: { planilha: 194976.36, sistema: 194976.36 },
      obs: 'Vendas conferidas: 139 linhas na planilha e 107 vendas no Conta Azul, mesmo total ao centavo. Na planilha, agosto não tem o código interno da venda preenchido.\nSem pendências.',
      acoes: [],
    },
    '2026-09': {
      fechamento: { planilha: 243717.67, sistema: 245781.51 },
      obs: 'Diferença de R$ 2.063,84 explicada por 2 vendas: Central das Cooperativas / Raíra Sicoob (R$ 1.995,00, no CA em 30/09 e na planilha em 01/10) e Luana – Espaço Desenvolver (R$ 68,84 a mais no CA). As demais 109 vendas batem.',
      acoes: [
        { texto: 'Raíra Sicoob: explicar ao Egberto e pedir autorização para manter a venda contabilizada em setembro (NF já emitida em 01/10), mesmo com a comissão paga em novembro.', resp: 'Tiago', feito: false },
        { texto: 'Luana – Espaço Desenvolver: explicar ao Egberto e pedir autorização para incluir os R$ 68,84 da maquininha no total do pedido de venda.', resp: 'Tiago', feito: false },
      ],
    },
    '2026-10': {
      fechamento: { planilha: 198730.09, sistema: 227499.09 },
      obs: 'Diferença de R$ 28.769,00 (Conta Azul maior) com 4 causas: (1) 2 vendas criadas só para emitir NF repetem vendas já lançadas: BDP Supermercado R$ 23.630,00 (= BDP Run lote 1 de setembro + lote final + staffs) e Maria Edhuarda R$ 4.034,00 (= FEJEA AL de setembro); (2) 3 vendas estão só no CA, R$ 1.960,00; (3) 7 vendas com valor diferente, R$ 1.140,00 a mais no CA; (4) Raíra Sicoob, R$ 1.995,00, está em setembro no CA (ver ação 1 de setembro). As demais 104 vendas batem, 5 delas divididas em duas vendas no CA.',
      acoes: [
        { texto: 'BDP Supermercado e Maria Edhuarda: ajustar no Conta Azul para que os R$ 27.664,00 não sejam contados duas vezes como receita, sem cancelar as NFs já emitidas, e combinar com a Visu que a NF de uma venda já lançada sai da própria venda.', resp: 'Time Seja Expert', feito: false },
        { texto: 'Vendas só no CA (Alberto Salomão R$ 1.000,00 com NF em 26/10, Leão Metais PB R$ 825,00 em 29/10, Eronita R$ 135,00 em 19/10): confirmar se são vendas novas, para incluir na planilha, ou lançamentos a corrigir no CA.', resp: 'Egberto e Milena', feito: false },
        { texto: 'Valores diferentes (planilha × CA): Gabriella – Poseidon 470,00 × 1.755,00; CF Bull 530,00 × 725,00; Alicia – Pilates 780,00 × 825,00; Rezende 600,00 × 300,00; Amilton – Eurotrip 600,00 × 750,00; Eleisandro 900,00 × 720,00; Roberta Assessoria 495,00 × 440,00. Confirmar o valor de cada pedido e corrigir a planilha ou o CA.', resp: 'Milena e Egberto, com correção no CA pelo Time Seja Expert', feito: false },
      ],
    },
    '2026-11': {
      fechamento: { planilha: 29428.16, sistema: 29128.16 },
      obs: 'Posição até 06/11. Diferença de R$ 7.851,60 (planilha maior): 6 vendas de 05 e 06/11 ainda não estão no CA (R$ 7.551,60: Lucas Vieira Nutri, Rony Bala, David – Rise em 3 pedidos, Rafaela GAC Club) e uma linha de R$ 300,00 da Invicta Gráfica (25 sacochilas) está gravada com o código do pedido do PB Júnior (18112026). As demais 20 vendas batem.\nAtualização 08/11: com as 6 vendas lançadas, a diferença caiu para R$ 300,00, que é a linha da Invicta Gráfica (ação 2).',
      acoes: [
        { texto: 'Lançar no Conta Azul as 6 vendas de 05 e 06/11. Concluída em 08/11: as 6 vendas foram lançadas com os mesmos valores e datas da planilha.', resp: 'Time Seja Expert', feito: true },
        { texto: 'Invicta Gráfica: confirmar se as 25 sacochilas (R$ 300,00) são um pedido à parte, corrigir o código na planilha e lançar no CA.', resp: 'Egberto', feito: false },
      ],
    },
  },
  financeiro: {
    contas: [
      conta('Bradesco', 'banco', [C, C, -2003.0, -1982.78]),
      conta('Caixa Espécie', 'caixa', [I, I, I, I]),
      conta('Caixa Acertos (zerado)', 'caixa', [1065371.15, 1065371.15, 1065396.15, 1065396.15]),
      conta('Conta Azul PJ', 'banco', [C, C, C, C]),
      conta('InfinitePay', 'banco', [C, -951.54, 1955.8, 130.8]),
      conta('Itaú', 'banco', [C, C, C, C]),
      conta('Sicoob', 'banco', [C, -73.14, -73.14, -73.14]),
      conta('Sicoob RDC (aplicação)', 'aplicacao', [I, I, I, I]),
      conta('Cartão Bradesco 67414', 'cartao', [C, C, C, C]),
      conta('Cartão Bradesco 70871', 'cartao', [C, C, C, C]),
      conta('Cartão Itaú 5495', 'cartao', [C, C, -0.1, -0.1]),
      conta('Cartão Itaú 9657', 'cartao', [C, C, C, C]),
      conta('Cartão Sicoob 3076', 'cartao', [C, C, C, C]),
    ],
  },
  atualizado_em: '2026-11-08T12:00:00.000Z',
  por: 'Fechamento validado (08/11/2026)',
});

export async function lerDivergencias() {
  if (!memo) memo = (await lerKV(CHAVE).catch(() => null)) || SEMENTE();
  return memo;
}

const txt = (v, max = 4000) => String(v ?? '').replace(/\r/g, '').trim().slice(0, max);
const numDireto = (v) => { if (v === null || v === undefined || v === '') return null; const n = typeof v === 'number' ? v : Number(String(v).trim().replace(/\s/g, '').replace(/\.(?=\d{3}(\D|$))/g, '').replace(',', '.')); return Number.isFinite(n) ? Math.round(n * 100) / 100 : null; };
const mesOk = (m) => /^\d{4}-\d{2}$/.test(String(m || ''));

// b.tipo: comercial | conta | nova_conta | remover_conta | fechamento
export async function salvarDivergencias(b, u) {
  const d = await lerDivergencias();
  const tipo = b?.tipo;
  if (tipo === 'comercial') {
    if (!mesOk(b.mes)) throw new Error('Mês inválido.');
    const atual = d.comercial[b.mes] || {};
    const acoes = (Array.isArray(b.acoes) ? b.acoes : []).map((a) => ({ texto: txt(a.texto, 2000), resp: txt(a.resp, 160), feito: !!a.feito })).filter((a) => a.texto);
    d.comercial[b.mes] = { ...atual, obs: txt(b.obs), acoes };
  } else if (tipo === 'fechamento') {
    if (!mesOk(b.mes)) throw new Error('Mês inválido.');
    const atual = d.comercial[b.mes] || { obs: '', acoes: [] };
    d.comercial[b.mes] = { ...atual, fechamento: { planilha: numDireto(b.planilha), sistema: numDireto(b.sistema), em: new Date().toISOString(), por: u?.nome || '' } };
  } else if (tipo === 'conta') {
    if (!mesOk(b.mes)) throw new Error('Mês inválido.');
    const c = d.financeiro.contas.find((x) => x.nome === b.nome);
    if (!c) throw new Error('Conta não encontrada.');
    const extrato = numDireto(b.extrato), sistema = numDireto(b.sistema);
    let status = ['conferido', 'incompleto', 'dif', ''].includes(b.status) ? b.status : '';
    let dif = numDireto(b.dif);
    if (extrato !== null && sistema !== null && status !== 'incompleto') { dif = Math.round((extrato - sistema) * 100) / 100; status = Math.abs(dif) < 0.005 ? 'conferido' : 'dif'; }
    if (status === 'conferido') dif = 0;
    c.meses[b.mes] = { status, dif: status === 'dif' ? dif : status === 'conferido' ? 0 : null, extrato, sistema, obs: txt(b.obs), em: new Date().toISOString(), por: u?.nome || '' };
  } else if (tipo === 'nova_conta') {
    const nome = txt(b.nome, 80);
    if (!nome) throw new Error('Informe o nome da conta.');
    if (d.financeiro.contas.some((x) => x.nome.toLowerCase() === nome.toLowerCase())) throw new Error('Já existe uma conta com esse nome.');
    d.financeiro.contas.push({ nome, tipo: ['banco', 'cartao', 'caixa', 'aplicacao'].includes(b.tipo_conta) ? b.tipo_conta : 'banco', meses: {} });
  } else if (tipo === 'remover_conta') {
    d.financeiro.contas = d.financeiro.contas.filter((x) => x.nome !== b.nome);
  } else throw new Error('Nada para salvar.');
  d.atualizado_em = new Date().toISOString(); d.por = u?.nome || '';
  memo = d;
  await salvarKV(CHAVE, d);
  return d;
}
