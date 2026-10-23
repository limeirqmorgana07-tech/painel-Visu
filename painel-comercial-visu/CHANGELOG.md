# Histórico de versões — Painel de Gestão Visu

O mesmo histórico aparece no painel, na página **Controle → Versões**, e a versão no ar aparece no rodapé.

## v24 · 23/10/2026 (revisão do Tiago, bloco Comercial)
- Planilha: prioriza a aba BASE TRATADA; aplica a aba DE-PARA CLIENTES (col. A → col. B); colunas com prioridade (Cliente padronizado > Cliente; Novo x Recompra > marcação do vendedor; Tecido > Material). nr_fonte e de_para no /api/vendas.
- Faturamento do mês ≥ DETALHE_CA_DESDE (padrão 2026-08) vem da Conta Azul quando a planilha está ligada; o detalhe continua da planilha.
- Conta Azul sozinha: meses antes de DETALHE_CA_DESDE viram "vendas consolidadas" (cs:1), fora de pedidos, ticket, clientes, novo × recompra e clientes parados; recompra só quando o cliente já comprou no período detalhado.
- Matriz tecido × cor e ticket por tecido com linhas/colunas "não identificado"; cor Sublimada no leitor de produtos.
- Não vendedores padrão (uma vez): Tiago - Financeiro, Escritório BPO, Morgana Limeira, Anderson Alves, Visu. Comparação de nomes sem acento/maiúsculas.

## v23 · 19/10/2026
- Permissões por perfil editáveis pelo ADM (POST /api/perfis, chave perfis_paginas); paginasDe usa o padrão personalizado, então menu e bloqueio de dados no servidor seguem a mesma regra.
- Ver o painel como: recarrega a lista de usuários ao trocar, para refletir permissões recém-salvas.

## v22 · 15/10/2026
- Logo do menu recolhe/abre o menu (modo só ícones com submenu ao passar o mouse).
- Formato do menu no Visual: lateral, só ícones, no topo (data-menu; salvo junto com o tema e no padrão do ADM).
- Temas Pop, Vidro e Preto & laranja.

## v21 · 15/10/2026
- /api/usuarios devolve banco_status; o aviso em Usuários separa "sem DATABASE_URL" de "DATABASE_URL com erro" e mostra o erro.
- Foco do menu lateral na cor do tema.

## v20 · 15/10/2026
- Conectar Google (OAuth, só leitura do Drive): a planilha de vendas é baixada direto da conta que tem acesso, a cada atualização. Rotas /google/conectar, /google/callback, /google/desconectar e /api/google; token na chave google_token. Novas variáveis GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET. Dependência xlsx para ler o arquivo.

## v19 · 15/10/2026
- Botão "Visual": seis temas com as cores do logo (Clássico, Cores da Visu, Pôr do sol, Turquesa, Fio Visu e Noite), e espaçamento Confortável/Compacto. A escolha fica no navegador de cada pessoa; o ADM define o padrão de todos (POST /api/visual, chave visual_padrao).

## v18 · 15/10/2026
- "Abrir planilha" abre o Google Planilhas na conta do usuário logado (parâmetro authuser), ou na conta da variável PLANILHA_CONTA (padrão: morgana.limeira@sejaexpertgestao.com).

## v17 — 14/10/2026 · Clientes, contas a pagar e produtos mais gerenciais
Arquivo: `painel-visu-v17.zip`
- Clientes redesenhado: indicadores da carteira, 10 maiores com barra e variação, concentração A/B/C, faixas de valor em colunas e clientes parados em tabela compacta.
- Contas a pagar em tabelas compactas, com mês atual, mês anterior e variação por categoria.
- Produtos e mix: clicar num tipo destaca a evolução dele mês a mês; novo filtro Produto; vendas ainda sem itens carregados ficam fora do mix.
- Nomes padronizados (BONÉ → Boné, EGBERTO → Egberto), rótulos de valor no gráfico de vendas, botão Filtrar no período personalizado e link da planilha em Planilha × sistema.

## v16 — 14/10/2026 · Sem margem bruta por produto
Arquivo: `painel-visu-v16.zip`
- Margem bruta retirada de produtos, vendedores, pedidos, painel executivo e quadro de indicadores, porque o custo dos produtos na Conta Azul ainda não tem o refinamento necessário.
- No lugar: preço médio por peça, peças por pedido e peças vendidas.
- Margem de contribuição e ponto de equilíbrio continuam no Financeiro, calculados pela DRE.

## v15 — 14/10/2026 · Produtos gerencial, período personalizado e vendedores ativos
Arquivo: `painel-visu-v15.zip`
- Produtos e mix redesenhado: indicadores do mix, participação por tipo com variação, evolução do mix em 6 meses, matriz tecido × cor e curva ABC em gráfico.
- Margem bruta calculada só sobre os itens com custo cadastrado na Conta Azul, com o percentual de cobertura.
- Filtro "Período personalizado" (de/até) nas páginas comerciais.
- Vendedores: o ADM marca quem é ou não é vendedor; os inativos saem da lista e da régua de comissão.

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
