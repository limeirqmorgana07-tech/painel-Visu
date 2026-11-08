// Páginas do painel (menu lateral) e o que cada perfil pode ver.
// O ADM pode restringir ainda mais por usuário, na página Usuários e permissões.
export const MENU = [
  { grupo: 'Gestão', itens: [['painel', 'Painel executivo'], ['indicadores', 'Quadro de indicadores']] },
  { grupo: 'Comercial', itens: [['registro', 'Planilha de vendas'], ['vendas', 'Vendas'], ['produtos', 'Produtos e mix'], ['clientes', 'Clientes'], ['vendedores', 'Vendedores e premiação'], ['pedidos', 'Pedidos e entregas'], ['treinamento', 'Treinamento']] },
  // reunião de 03/11/2026: conferência sistema × planilha num grupo próprio (a planilha é a referência das vendas)
  { grupo: 'Conferência', itens: [['inconsistencias', 'Inconsistências'], ['conciliacao', 'Divergências por mês'], ['historico', 'Histórico de alterações']] },
  { grupo: 'Financeiro', itens: [['dre', 'DRE gerencial'], ['equilibrio', 'Margem e ponto de equilíbrio'], ['caixa', 'Fluxo de caixa'], ['receber', 'Contas a receber'], ['pagar', 'Contas a pagar'], ['extrato', 'Conciliação bancária']] },
  { grupo: 'Controle', itens: [['dados', 'Qualidade dos dados'], ['versoes', 'Versões do painel'], ] },
  { grupo: 'Administração', itens: [['usuarios', 'Usuários e permissões']] },
];
export const TODAS = MENU.flatMap((g) => g.itens.map((i) => i[0]));
const COM = ['vendas', 'produtos', 'clientes', 'vendedores', 'pedidos'];
const FIN = ['dre', 'equilibrio', 'caixa', 'receber', 'pagar', 'extrato'];
const PADRAO_BASE = {
  adm: TODAS,
  diretor: TODAS.filter((p) => p !== 'usuarios'),
  // reunião de 03/11/2026: vendedores lançam os pedidos no painel e veem a conciliação; o histórico fica com a gestão
  comercial: ['registro', ...COM, 'inconsistencias', 'conciliacao', 'versoes', 'treinamento'],
  financeiro: ['painel', 'indicadores', 'registro', ...FIN, 'inconsistencias', 'historico', 'conciliacao', 'dados', 'versoes', 'treinamento'],
  // consultor externo liberado pela diretoria: só o módulo de vendas (em homologação); o ADM pode ampliar
  consultor: [...COM],
  // perfil Vendedor (v32): lança e revisa as próprias vendas na Planilha de vendas e vê as inconsistências dele
  vendedor: ['registro', ...COM, 'inconsistencias', 'treinamento'],
};
// O ADM pode mudar o que cada perfil vê (vale para todas as pessoas daquele perfil). Guardado na chave perfis_paginas.
let personalizado = {};
const LIBERAVEIS = TODAS.filter((p) => p !== 'usuarios');
const NOVAS_V31 = ['registro', 'inconsistencias', 'historico'];
const NOVAS_V43 = ['extrato'];
export function definirPerfis(o) {
  personalizado = {};
  // listas salvas antes da v31 não conheciam os 3 menus novos: entram conforme o padrão do perfil
  const antiga = o && !o._v31, antes43 = o && !o._v43;
  for (const [k, v] of Object.entries(o || {})) if (k !== 'adm' && PADRAO_BASE[k] && Array.isArray(v)) personalizado[k] = [...new Set([...v, ...(antiga ? NOVAS_V31.filter((p) => PADRAO_BASE[k].includes(p) && !v.includes(p)) : []), ...(antes43 ? NOVAS_V43.filter((p) => PADRAO_BASE[k].includes(p)) : [])])].filter((p) => LIBERAVEIS.includes(p));
}
export const perfisPersonalizados = () => ({ ...personalizado, _v31: true, _v43: true });
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
  // premiação é informação pessoal: por padrão os vendedores não veem (reunião de 03/11/2026)
  { id: 'vendedores.premiacao', pag: 'vendedores', nome: 'Vendedores: premiação, bônus e apuração (valores de cada vendedor)', fin: false },
];
const TODOS_BLOCOS = BLOCOS.map((b) => b.id), SO_COMERCIAL = BLOCOS.filter((b) => !b.fin && b.id !== 'vendedores.premiacao').map((b) => b.id);
const BLOCOS_PADRAO = { diretor: TODOS_BLOCOS, financeiro: TODOS_BLOCOS, comercial: SO_COMERCIAL, consultor: SO_COMERCIAL, vendedor: SO_COMERCIAL };
let blocosPers = {};
export function definirBlocos(o) {
  blocosPers = {};
  // listas salvas antes da v31 não conheciam o bloco de premiação: diretor e financeiro continuam vendo
  const antiga = o && !o._v31;
  for (const [k, v] of Object.entries(o || {})) if (BLOCOS_PADRAO[k] && Array.isArray(v)) blocosPers[k] = [...v.filter((b) => TODOS_BLOCOS.includes(b)), ...(antiga && ['diretor', 'financeiro'].includes(k) && !v.includes('vendedores.premiacao') ? ['vendedores.premiacao'] : [])];
}
export const blocosPersonalizados = () => ({ ...blocosPers, _v31: true });
export const blocosDe = (perfil) => (perfil === 'adm' ? TODOS_BLOCOS : blocosPers[perfil] || BLOCOS_PADRAO[perfil] || []);
export const blocosPadrao = () => ({ ...BLOCOS_PADRAO });
// financeiro liberado: tem página financeira, ou tem Painel/Quadro com algum bloco financeiro ligado
export const veFinanceiro = (u) => { const pg = paginasDe(u); if (pg.some((p) => FIN.includes(p))) return true; const bl = blocosDe(u?.perfil); return BLOCOS.some((b) => b.fin && pg.includes(b.pag) && bl.includes(b.id)); };
export const veVendas = (u) => paginasDe(u).some((p) => COM.includes(p) || ['painel', 'indicadores', 'conciliacao', 'dados', 'registro', 'conferencia', 'inconsistencias'].includes(p));
export const vePedidos = (u) => paginasDe(u).some((p) => ['registro', 'conferencia', 'inconsistencias', 'historico'].includes(p));
export const veHistorico = (u) => paginasDe(u).includes('historico');
