# Histórico de versões — Painel de Gestão Visu

O mesmo histórico aparece no painel, na página **Controle → Versões**, e a versão no ar aparece no rodapé.

## v33 — 03/11/2026 — Ligação da planilha pelo e-mail mais fácil
- Script do Google com a função `autorizar` e passo de autorização na janela "Ligar pelo meu e-mail".
- Mensagem de erro específica quando o Google devolve uma página (script não autorizado ou acesso diferente de "Qualquer pessoa").

## v32 — 03/11/2026 — Planilha de vendas, inconsistências num lugar só e perfil Vendedor
- **Planilha de vendas** (Comercial, antes "Pedidos de venda"): mesma grade com as colunas da planilha, visível mesmo vazia.
- **Inconsistências** unificadas numa lista só (sistema × planilha, colunas vazias, pagamento/entrega, código, duplicidade, cadastro), com filtros e exportação. A página separada "Sistema × planilha: pedidos" saiu.
- Sem planilha ligada nem base importada, a conferência avisa em vez de listar tudo como "só no sistema".
- **Perfil Vendedor** (campo "nome na planilha"): vê as próprias linhas primeiro, lança no próprio nome e só altera o que é dele.
- **Ligar pelo meu e-mail**: Google Apps Script na conta de quem tem acesso à planilha, com chave gerada pelo painel (`src/planilhaScript.js`, chave `planilha_script` no banco). Não precisa de GOOGLE_CLIENT_ID/SECRET.
- Planilha × sistema (mês) volta ao Controle.

## v31 — 03/11/2026 — Pedidos de venda no painel
Pedido da reunião interna Visu e Vieira Diniz (03/11/2026):
- **Pedidos de venda** (Comercial): registro de vendas com as mesmas colunas da planilha, edição na célula, novo pedido com vários itens e código automático `NNNNMMAAAA`.
- **Pedido complementar**: depois de 24 h (variável `HORAS_EDICAO_PEDIDO`) o vendedor não altera quantidade e valores; o acréscimo vira `código-1`, `código-2`.
- **Importar base** (gestão): planilha conectada ou arquivo .xlsx, por período, mantendo ou substituindo os meses já importados. Linhas a revisar em amarelo; "lote" sai do nome do cliente.
- Colunas **Planilha, Sistema e Divergência**; **1º e 2º pagamento** da Conta Azul pelo código do pedido, com card (data da baixa, banco, forma).
- **Conciliação de pedidos**: painel (ou planilha) × Conta Azul pedido a pedido.
- **Histórico de alterações** (gestão): usuário, horário, antes → depois. Tabelas `pedidos_venda` e `pedidos_log` no Postgres (criadas sozinhas).
- **Revisão de cadastro de clientes** com unificação de grafias.
- **Premiação oculta** para Comercial e Consultor (bloco `vendedores.premiacao`).
- **Fonte dos indicadores** escolhida pelo ADM: planilha conectada ou pedidos do painel.
- **Grupo Conferência** no menu: Sistema × planilha (pedidos e mês), **Inconsistências** (14 verificações, com o dever de casa por vendedor) e Histórico de alterações.
- **Vendas seguem a planilha**: a Conta Azul aparece só como conferência no faturamento. Pedidos importados contam como a base tratada (cliente + data).
- Código que vem como número da planilha volta para 10 dígitos; sem Conta Azul conectada a conferência não usa dados de demonstração.
- **Balão flutuante** no 1º/2º pagamento.
- **Exportar em Excel, PDF e CSV** em todas as listas (detalhamentos, pedidos, conciliação, histórico). As bibliotecas (`xlsx`, `jspdf`, `jspdf-autotable`) são servidas pelo próprio painel em `/vendor/`.

## v30 · 28/10/2026
- Blocos da Gestão por perfil (BLOCOS em src/paginas.js, POST /api/blocos, chave perfis_blocos); veFinanceiro considera blocos financeiros liberados; /api/eu devolve blocos, blocos_def, blocos_perfis (ADM).

## v29 · 28/10/2026
- FAIXAS_PADRAO = Política de Premiação por Performance 2026 (17 faixas, 15.000 + 2.187,50·k, 1% + 0,25·k). Faixas salvas antes no painel continuam valendo até o ADM clicar em "Voltar ao padrão".
- Bônus semanal (R$ 75 por semana seg–sex com ≥ R$ 25 mil), 5º dia útil, modal da política e rota /politica-premiacao.pdf (com login).

## v28 · 28/10/2026
- Logo novo (public/logo-visu.png branco, logo-visu-azul.png azul, logo.png ícone); rota /logo-visu-azul.png; login no azul #00348C.
- Temas azul, branco (troca para o logo azul), degrade, oceano; marcados como "nova marca" no seletor.

## v27 · 28/10/2026
- Perfil consultor (Consultor externo): padrão = páginas comerciais; campos empresa e valido_ate no usuário; acessoVencido() bloqueia login e sessão após a data.
- Vendedores e comissão: cartões de resumo (comissão a pagar, liberados, mais perto da próxima faixa, maior comissão).
- desenhar(): erro de um quadro vira aviso no topo (#erroPagina) com a mensagem e a versão.
- POST /api/comissao renova o cache de vendas.

## v26 · 27/10/2026
- Comissão: % liberado e valor por vendedor, apuração mensal (6 meses) e faixas configuráveis (GET/POST /api/comissao, chave comissao_faixas; regras.comissao_faixas no /api/vendas).

## v25 · 23/10/2026 (planilha tratada, cópia de 13/10)
- lerXlsx: BASE TRATADA como fonte (Cliente padronizado, Cliente (como lançado), Novo x Recompra, Pedido (cliente + data), Mapeamento, Possível lançamento duplicado?), unida linha a linha à BASE DE DADOS para pagamento, prazo, especificação e frete.
- tratarClientes: sem BASE TRATADA, aplica DE-PARA CLIENTES + CLIENTES ("Cliente anterior a 2026?") na base crua; novo = 1ª data do cliente na base. Conferido com a planilha: set/2026 = 31,2% novos, 39 clientes novos, 104 pedidos, 407 clientes.
- Abas RESULTADO, DE-PARA e CLIENTES nunca são escolhidas como base de vendas.
- Qualidade dos dados: resumo do tratamento, nomes fora do DE-PARA e linhas de possível duplicidade.

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
