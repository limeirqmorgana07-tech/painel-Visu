// Páginas do painel (menu lateral) e o que cada perfil pode ver.
// O ADM pode restringir ainda mais por usuário, na página Usuários e permissões.
export const MENU = [
  { grupo: 'Gestão', itens: [['painel', 'Painel executivo'], ['indicadores', 'Quadro de indicadores']] },
  { grupo: 'Comercial', itens: [['vendas', 'Vendas'], ['produtos', 'Produtos e mix'], ['clientes', 'Clientes'], ['vendedores', 'Vendedores e comissão'], ['pedidos', 'Pedidos e entregas']] },
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
export const veFinanceiro = (u) => paginasDe(u).some((p) => FIN.includes(p) || p === 'painel' || p === 'indicadores');
export const veVendas = (u) => paginasDe(u).some((p) => COM.includes(p) || ['painel', 'indicadores', 'conciliacao', 'dados'].includes(p));
