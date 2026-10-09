# Histórico de versões — Painel de Gestão Visu

O mesmo histórico aparece no painel, na página **Controle → Versões**, e a versão no ar aparece no rodapé.

## v6 — 08/10/2026 · Painel gerencial em 4 dashboards
Arquivo: `painel-gestao-visu-v6.zip`
- 13 abas viram 4 dashboards: Visão geral, Comercial, Financeiro e Controle.
- Visão geral: mês em andamento contra o ponto de equilíbrio (com projeção pelo ritmo), cascata do faturamento ao resultado, quadro de indicadores com 6 meses de tendência.
- Financeiro: margem de contribuição e ponto de equilíbrio recalculados todo mês pela DRE da Conta Azul, composição das despesas (fixas × variáveis), liquidez de 30 dias e dias de caixa.
- Aviso quando os meses não têm despesas lançadas, para não comparar resultado incompleto.

## v5 — 08/10/2026 · Histórico de versões
Arquivo: `painel-gestao-visu-v5.zip`
- Página "Versões" com o que mudou em cada entrega e a versão no rodapé.
- Este arquivo CHANGELOG.md.

## v4 — 08/10/2026 · Dashboards gerenciais (relatórios da Conta Azul)
Arquivo: `painel-gestao-visu-v4.zip`
- Resumo executivo com pontos de atenção automáticos e a vitrine do catálogo.
- Financeiro: DRE por competência e por caixa, fluxo de caixa com projeção de 13 semanas, contas a receber e inadimplência por idade, contas a pagar por categoria, centro de custo e fornecedor.
- Comercial: curva ABC de produtos com margem, clientes inativos, margem por vendedor.
- Alta de despesa passa a aparecer em vermelho.

## v3 — 08/10/2026 · Painel de gestão comercial e financeiro
Arquivo: `painel-gestao-visu-v3.zip`
- Todos os pontos do e-mail do Tiago (R1 a R4, C1 a C8 e regras de negócio).
- Nome do vendedor lido da Conta Azul.
- Página Planilha × sistema para explicar a diferença do total do mês.
- Produtos do catálogo flutuando na página inicial.
- Aviso vermelho quando a Conta Azul está desconectada.

## v2 — 08/10/2026 · Especificação do Painel de Vendas e nova identidade visual
Arquivo: `painel-comercial-visu-v2.zip`
- Indicadores da especificação: pedidos, ticket médio, novas × recompra, mix de produtos.
- Leitura da planilha de vendas e página Qualidade dos dados.
- Identidade visual do catálogo e do site da Visu.

## v1 — 08/10/2026 · Primeira versão: painel comercial
Arquivos: `painel-comercial-visu.zip` + `atualizacao-painel-visu.zip`
- Painel de vendas com login e conexão à Conta Azul pela API.
- Publicação no GitHub e no Render.
- Atualização: correção do link de autorização expirado e do endereço do token.

---
**Como registrar uma nova versão:** acrescente a entrada no topo deste arquivo e no início da lista `VERSOES` em `public/painel.html`, e troque `VERSAO` e o `version` do `package.json`.
