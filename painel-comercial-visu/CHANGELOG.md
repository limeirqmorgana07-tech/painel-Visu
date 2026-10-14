# Histórico de versões — Painel de Gestão Visu

O mesmo histórico aparece no painel, na página **Controle → Versões**, e a versão no ar aparece no rodapé.

## v14 — 14/10/2026 · Painel mais estável
Arquivo: `painel-visu-v14-estavel.zip`
- Um erro em segundo plano (Conta Azul ou banco fora do ar) não derruba mais o painel inteiro.
- Se o banco de dados não responder, o painel continua no ar e tenta de novo a cada minuto.
- Aceita a DATABASE_URL copiada do Neon do jeito que ela vier (com psql e aspas).
- Endereço /saude/banco para conferir se o banco está conectado.

## v13 — 14/10/2026 · Assinatura mais discreta
Arquivo: `painel-visu-v13-assinatura.zip`
- "Desenvolvido por Seja Expert" virou uma linha pequena no pé do menu, com a versão ao lado, no estilo do FluxIA.

## v12 — 14/10/2026 · Assinatura Seja Expert no menu
Arquivo: `painel-visu-v12-assinatura.zip`
- Rodapé do menu lateral com "Desenvolvido por", a marca Seja Expert, "Gestão Financeira e BPO" e a versão do painel.
- A menção à Seja Expert saiu do topo do menu e do rodapé das páginas.

## v11 — 14/10/2026 · Correções de usuários e menu
Arquivo: `painel-visu-v11-correcoes.zip`
- Tiago Sobral (ADM, tiago.sobral@sejaexpertgestao.com) passa a fazer parte dos perfis iniciais, no lugar de "Gestor Seja Expert".
- E-mail da Morgana corrigido para @sejaexpertgestao.com.
- Menu lateral abre os módulos quando nenhum está aberto; rodapé do menu não fica mais cortado.
- Aviso mais claro sobre a falta do banco de dados (DATABASE_URL).

## v10 — 13/10/2026 · Menu lateral e permissões por perfil
Arquivo: `painel-visu-v10-menu-lateral.zip`
- Menu lateral no padrão do Sistema de Gestão: módulos Gestão, Comercial, Financeiro, Controle e Administração, cada painel na sua página.
- Perfis ADM, Diretor, Comercial e Financeiro. Em Permissões, o ADM tira páginas de uma pessoa específica; o servidor bloqueia os dados também.
- "Ver o painel como" no menu (ADM) para conferir o que cada perfil ou pessoa enxerga.

## v9 — 13/10/2026 · Senha temporária
Arquivo: `painel-visu-v9-senha-temporaria.zip`
- Na página Usuários, o botão "Senha temporária" gera uma senha (ex.: Visu-K7QM-4XPA) que vale 7 dias.
- A pessoa entra com e-mail e senha temporária e o painel obriga a criar a própria senha antes de mostrar os dados.
- Mensagem pronta para WhatsApp ou e-mail com endereço, login e senha. Botão "Trocar senha" no topo para todos os usuários.

## v8 — 13/10/2026 · Detalhamento ao clicar nos valores
Arquivo: `painel-visu-v8-detalhamento.zip`
- Clicar em um valor abre a lista que forma aquele total: pedidos, itens, clientes, lançamentos ou parcelas em aberto.
- Vale para os indicadores, vendedores, rankings de produto, tecido, cor e cliente, curva ABC, DRE, despesas por categoria e centro de custo, fornecedores, contas a receber e a pagar, caixa e pontos de atenção.
- A lista tem busca, ordenação por coluna e exportação para CSV (abre no Excel).

## v7 — 11/10/2026 · Usuários com perfis Diretor e ADM
Arquivo: `painel-gestao-visu-v7.zip`
- Login por e-mail e senha, com perfis Diretor (dashboards) e ADM (dashboards, usuários e conexão com a Conta Azul).
- Quatro perfis criados: dois diretores e dois ADM (Morgana e gestor).
- Página Usuários: gera o link pessoal de cada pessoa, com mensagem pronta para WhatsApp ou e-mail. A pessoa cria a própria senha no primeiro acesso.

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
