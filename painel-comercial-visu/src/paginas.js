// Páginas do painel (menu lateral) e o que cada perfil pode ver.
// O ADM pode restringir ainda mais por usuário, na página Usuários e permissões.
export const MENU = [
  { grupo: 'Gestão', itens: [['painel', 'Painel executivo'], ['indicadores', 'Quadro de indicadores']] },
  { grupo: 'Comercial', itens: [['vendas', 'Vendas'], ['produtos', 'Produtos e mix'], ['clientes', 'Clientes'], ['vendedores', 'Vendedores e premiação'], ['pedidos', 'Pedidos e entregas']] },
  { grupo: 'Financeiro', itens: [['dre', 'DRE gerencial'], ['equilibrio', 'Margem e ponto de equilíbrio'], ['caixa', 'Fluxo de caixa'], ['receber', 'Contas a receber'], ['pagar', 'Contas a pagar']] },
  { grupo: 'Controle', itens: [['conciliacao', 'Planilha × sistema'], ['dados', 'Qualidade dos dados'], ['versoes', 'Versões do painel']] },
  { grupo: 'Administração', itens: [['usuarios', 'Usuários e permissões']] },
];
export const TODAS = MENU.flatMap((g) => g.itens.map((i) => i[0]));
const COM = ['vendas', 'produtos', 'clientes', 'vendedores', 'pedidos'];
const FIN = ['dre', 'equilibrio', 'caixa', 'receber', 'pagar'];
const PADRAO_BASE = {
  adm: TODAS,
  diretor: TODAS.filter((p) => p !== 'usuarios'),
  comercial: [...COM, 'conciliacao', 'versoes'],
  financeiro: ['painel', 'indicadores', ...FIN, 'conciliacao', 'dados', 'versoes'],
  // consultor externo liberado pela diretoria: só o módulo de vendas (em homologação); o ADM pode ampliar
  consultor: [...COM],
};
// O ADM pode mudar o que cada perfil vê (vale para todas as pessoas daquele perfil). Guardado na chave perfis_paginas.
let personalizado = {};
const LIBERAVEIS = TODAS.filter((p) => p !== 'usuarios');
export function definirPerfis(o) {
  personalizado = {};
  for (const [k, v] of Object.entries(o || {})) if (k !== 'adm' && PADRAO_BASE[k] && Array.isArray(v)) personalizado[k] = v.filter((p) => LIBERAVEIS.includes(p));
}
export const perfisPersonalizados = () => ({ ...personalizado });
export const padraoDe = (perfil) => (perfil === 'adm' ? TODAS : personalizado[perfil]?.length ? personalizado[perfil] : PADRAO_BASE[perfil] || []);
export const PADRAO = new Proxy({}, { get: (_, k) => padraoDe(k), ownKeys: () => Object.keys(PADRAO_BASE), getOwnPropertyDescriptor: () => ({ enumerable: true, configurable: true }) });
export const padroesOriginais = () => ({ ...PADRAO_BASE });

// páginas liberadas para o usuário: o padrão do perfil, recortado pela escolha do ADM (se houver)
export function paginasDe(u) {
  if (!u) return [];
  const base = padraoDe(u.perfil);
  if (u.perfil === 'adm' || !Array.isArray(u.paginas)) return base;
  const r = base.filter((p) => u.paginas.includes(p));
  return r.length ? r : base.slice(0, 1);
}
// Blocos das páginas de Gestão (Painel executivo e Quadro de indicadores): o ADM escolhe o que cada perfil enxerga.
export const BLOCOS = [
  { id: 'painel.vitrine', pag: 'painel', nome: 'Vitrine: o que mais saiu da fábrica', fin: false },
  { id: 'painel.vendas', pag: 'painel', nome: 'Indicadores de vendas (vendas, pedidos e ticket, clientes novos, peças)', fin: false },
  { id: 'painel.financeiro', pag: 'painel', nome: 'Indicadores financeiros (resultado, saldo em caixa, caixa em 4 semanas, inadimplência)', fin: true },
  { id: 'painel.equilibrio', pag: 'painel', nome: 'Mês em andamento contra o ponto de equilíbrio', fin: true },
  { id: 'painel.cascata', pag: 'painel', nome: 'Do faturamento ao resultado', fin: true },
  { id: 'painel.grafico', pag: 'painel', nome: 'Vendas e resultado nos últimos 12 meses', fin: true },
  { id: 'painel.alertas', pag: 'painel', nome: 'Pontos de atenção', fin: true },
  { id: 'indicadores.comercial', pag: 'indicadores', nome: 'Quadro: indicadores comerciais', fin: false },
  { id: 'indicadores.financeiro', pag: 'indicadores', nome: 'Quadro: financeiro (competência)', fin: true },
  { id: 'indicadores.caixa', pag: 'indicadores', nome: 'Quadro: caixa', fin: true },
];
const TODOS_BLOCOS = BLOCOS.map((b) => b.id), SO_COMERCIAL = BLOCOS.filter((b) => !b.fin).map((b) => b.id);
const BLOCOS_PADRAO = { diretor: TODOS_BLOCOS, financeiro: TODOS_BLOCOS, comercial: SO_COMERCIAL, consultor: SO_COMERCIAL };
let blocosPers = {};
export function definirBlocos(o) { blocosPers = {}; for (const [k, v] of Object.entries(o || {})) if (BLOCOS_PADRAO[k] && Array.isArray(v)) blocosPers[k] = v.filter((b) => TODOS_BLOCOS.includes(b)); }
export const blocosPersonalizados = () => ({ ...blocosPers });
export const blocosDe = (perfil) => (perfil === 'adm' ? TODOS_BLOCOS : blocosPers[perfil] || BLOCOS_PADRAO[perfil] || []);
export const blocosPadrao = () => ({ ...BLOCOS_PADRAO });
// financeiro liberado: tem página financeira, ou tem Painel/Quadro com algum bloco financeiro ligado
export const veFinanceiro = (u) => { const pg = paginasDe(u); if (pg.some((p) => FIN.includes(p))) return true; const bl = blocosDe(u?.perfil); return BLOCOS.some((b) => b.fin && pg.includes(b.pag) && bl.includes(b.id)); };
export const veVendas = (u) => paginasDe(u).some((p) => COM.includes(p) || ['painel', 'indicadores', 'conciliacao', 'dados'].includes(p));
