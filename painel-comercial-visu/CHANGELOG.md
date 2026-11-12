# Histórico de versões — Painel de Gestão Visu

O mesmo histórico aparece no painel, na página **Controle → Versões**, e a versão no ar aparece no rodapé.

## v96 — 12/11/2026 — Permissões por pessoa exatas
- Permissões por pessoa valem exatamente como marcadas: antes, uma página marcada na pessoa sumia se não estivesse no perfil dela (por isso a Planilha de vendas não aparecia para os diretores). Agora qualquer página pode ser marcada; as que estão fora do padrão do perfil aparecem como extra.
- Ao mudar as páginas de um perfil (ex.: Diretor), a mudança vale também para quem tem páginas escolhidas uma a uma.
- Ao subir esta versão, cada pessoa mantém o que já via, e os diretores passam a ver a Planilha de vendas quando o perfil Diretor a tem.

## v95 — 11/11/2026 — Treinamento atualizado
- Vídeo de treinamento atualizado (5 minutos): campos obrigatórios, condição personalizada (entrada, complementar e pagamento final), comprovante de pagamento complementar com valor e data, pedido aprovado e Confirmado na Conta Azul e ficha do pedido (🔍).
- Passo a passo escrito do Treinamento atualizado com as mesmas mudanças.

## v94 — 11/11/2026 — Gráfico do histórico de acessos
- Acessos ao painel: novo gráfico Histórico de acessos, com os acessos por dia (barras) e as pessoas diferentes que entraram (linha). Em Hoje, mostra por hora.
- Passe o mouse em cada dia para ver o total, os logins e quem acessou. Segue os filtros de período e de pessoa.

## v93 — 11/11/2026 — Pagamento complementar pelo comprovante e ajuste do 0044112026
- Pedido 0044112026 ajustado sozinho ao subir a versão: pagamento de entrada de R$ 1.100 (na data da 1ª parcela lançada) e pagamento final com o restante no prazo de entrega. O erro some e ele vai para a Conta Azul no próximo envio (ou no Enviar agora).
- Comprovante com valor e data: ao anexar um comprovante de pagamento novo (ex.: pagamento complementar), o vendedor informa o valor e a data. O painel abate do saldo do pedido na hora (Falta receber com ⏳) e o pagamento aparece para o financeiro.
- Contas a receber → Analítico → 8. Pagamentos informados pelos vendedores: lista o que aguarda baixa na Conta Azul; depois de dar a baixa lá, o financeiro clica em Baixa feita.
- A ficha do pedido (🔍) mostra os pagamentos informados e o saldo do pedido.

## v92 — 11/11/2026 — Personalizado: entrada, complementar e pagamento final
- Condição de pagamento Personalizado com nomes: Pagamento de entrada, Pagamento complementar (um ou mais, se houver) e Pagamento final (saldo). O botão + Pagamento complementar entra antes do pagamento final.
- Os mesmos nomes aparecem na célula Parcelas, na ficha do pedido e na descrição de cada parcela enviada à Conta Azul.
- Inclui tudo da v91 (pedidos entram aprovados na Conta Azul) e das versões anteriores.

## v91 — 11/11/2026 — Pedidos entram aprovados na Conta Azul
- Pedidos do painel entram na Conta Azul já APROVADOS (não mais em andamento): eles chegam aprovados pela gestão, que cota e aprova no CRM. Assim contam nos aprovados da Conta Azul e liberam a emissão da NF-e.
- Aprovação no painel continua só para mudança de valor e quantidade depois do prazo de 24 h; acréscimos e ajustes dentro das 24 h seguem direto.
- Versão consolidada: inclui tudo da v86 à v90 (Atualizar, ficha do pedido, selo CA, Ver como exato, Acessos ao painel).

## v90 — 11/11/2026 — Acessos ao painel (só ADM)
- Nova página Acessos ao painel (Administração), só para ADM: quem entrou, quando, de qual dispositivo e quais páginas abriu.
- Mostra quantas pessoas acessaram e quantas entraram hoje, quem mais acessa (acessos, logins, dias com acesso, último acesso, páginas mais abertas e dispositivo), quem nunca entrou, as páginas mais abertas e a lista dos últimos acessos, com filtro por período e pessoa e exportação em Excel, PDF ou CSV.
- A contagem começa a partir desta versão; antes dela só existe o último acesso de cada usuário.

## v89 — 11/11/2026 — Em andamento conta como aprovado e Ver como exato
- Divergência: venda em andamento na Conta Azul deixa de aparecer como Não aprovado no sistema. O pedido já sai aprovado pelo gestor comercial e o painel envia como em andamento; com o valor igual, fica Batendo.
- Ver o painel como uma pessoa (ex.: um diretor) mostra exatamente o que ela vê: as páginas que você liberou para ela, os blocos do perfil e as mesmas funções (lançar, gestão, importar), lidos direto do servidor.
- Ver como Perfil segue a mesma regra do servidor (Aprovações para todos e Usuários e permissões para o diretor).

## v88 — 11/11/2026 — Selo CA ✓ em todos os pedidos do mês
- Selo CA ✓ também nos pedidos que vieram da planilha: ao lado dos ícones de cada pedido do mês, CA ✓ quando a venda com o mesmo número está na Conta Azul (passe o mouse para ver o valor) e CA ? quando não foi encontrada.
- A coluna de ações da Planilha de vendas não corta mais os selos.

## v87 — 11/11/2026 — Ficha do pedido e confirmação imediata na Conta Azul
- Ficha do pedido: o botão 🔍 em cada pedido abre tudo dele numa janela só, com dados do pedido, itens, condição de pagamento com as parcelas exatamente como vão para a Conta Azul, soma das parcelas, situação na Conta Azul, recebimentos, comprovantes e histórico.
- Quando as parcelas personalizadas não fecham com o total do pedido, a ficha mostra em vermelho a diferença e como corrigir.
- Conta Azul: o pedido passa a Confirmado na CA assim que a Conta Azul devolve o número da venda criada no envio; não fica mais esperando a próxima leitura.
- Depois do Enviar agora, o painel relê as vendas da Conta Azul sozinho.

## v86 — 11/11/2026 — Botão Atualizar funcionando
- Botão Atualizar (no alto do painel) corrigido: agora busca de novo as vendas, os pedidos, o financeiro, as contas a receber e o extrato, e redesenha a página em que você está, sem precisar do F5.
- Enquanto atualiza, o botão mostra Atualizando… e, no fim, avisa a hora da atualização (ou o motivo, se algo falhar).

## v85 — 11/11/2026 — Hora do registro e confirmação na Conta Azul
- Planilha de vendas com duas colunas novas no fim: Registrado em (dia e hora em que o pedido foi lançado no painel, e por quem, ao passar o mouse) e Conta Azul (situação do pedido na Conta Azul).
- Situações na Conta Azul: Confirmado na CA (o painel achou a venda com o mesmo número), Enviado · confirmando, Aguardando envio (mostra o próximo horário: 09:30, 14:00 ou 17:30), Erro no envio (com o motivo) e Envio desligado.
- Novo quadro Na Conta Azul: quantos pedidos do painel já estão confirmados na Conta Azul, quantos aguardam envio e quantos deram erro.

## v84 — 11/11/2026 — Campos obrigatórios no pedido de venda
- Pedido de venda com campos obrigatórios: o vendedor (e qualquer perfil) só salva o pedido com data, cliente, nome do pedido (Trello), vendedor, tipo de venda, novo ou recompra, segmento, forma de pagamento, parcelas e prazo de entrega preenchidos.
- Cada item exige tipo de produto, material, especificação, cor, quantidade e valor/und.
- Os campos que faltam ficam marcados em vermelho e a mensagem diz exatamente o que preencher, tanto na linha da planilha quanto no formulário.
- Ao alterar um pedido, nenhum campo obrigatório pode ser apagado. Pedidos lançados pelo painel precisam estar completos para salvar uma alteração; pagamentos e premiação continuam podendo ser atualizados pela gestão mesmo em pedido antigo incompleto.

## v83 — 11/11/2026 — Contas a receber na ordem da planilha e nova janela de detalhe
- Contas a receber na mesma ordem da planilha: 1. Posição geral, 2. Vencidos por faixa, 3. A vencer por semana (hoje, resto da semana e semanas até o fim do mês, como na planilha), 4. Maiores saldos e, por último, 5. O que fazer com cada título, com a linha Vencido a cobrar de fato e a explicação das ações.
- Voltaram as informações da Conta Azul em tempo real, em blocos que abrem e fecham: Atraso por idade (com a inadimplência), Maiores atrasos por cliente, Próximos recebimentos (7 e 30 dias) e Receitas por categoria.
- Analítico mais compacto: Títulos em aberto e DNI ocupam menos altura, com letra menor e cabeçalho fixo.
- Nova janela de detalhamento em todo o painel (Comercial, Financeiro e demais páginas): centralizada, no padrão visual do painel, com busca, totais em destaque, situação colorida e linha de total no rodapé.

## v82 — 11/11/2026 — Contas a receber: Sintético e Analítico, com exportação
- Contas a receber reorganizada em uma coluna só, sem quadros lado a lado, com duas visões: Sintético (igual à planilha: posição geral, faixas de atraso, o que fazer, a vencer por semana e maiores saldos) e Analítico (títulos em aberto e recebimentos sem cliente identificado — DNI).
- Clique em qualquer linha do Sintético (ou nos quadros do topo) para ver os títulos daquele grupo com as descrições, observações e a descrição da Conta Azul; a lista tem busca, ordenação e exportação.
- Botão Base 10/11 (planilha) para conferir com a planilha do Tiago na mesma data base.
- Exportar relatório (Excel) com as abas Resumo, Títulos em aberto, Maiores saldos e DNI; e Exportar (Excel, PDF ou CSV) em Maiores saldos, Títulos em aberto e DNI.
- A página não usa mais o mês do topo: mostra toda a carteira em aberto. A data base só muda o que está vencido e os dias de atraso.

## v81 — 11/11/2026 — Contas a receber com gestão da cobrança

- Financeiro → Contas a receber: nova Gestão da cobrança, no formato da planilha da Seja Expert (10/11): posição geral (vencidos × a vencer), vencidos por faixa de atraso, a vencer por semana, o que fazer com cada título (ação) e os 15 maiores saldos vencidos por cliente. Filtros por vendedor, cliente e data de referência (recalcula os atrasos).
- Títulos em aberto: lista de todos os títulos da Conta Azul com dias de atraso, venda, parcela, vencimento, valor, recebido, em aberto e vendedor (pelo código do pedido). Ação, observações, decisão na reunião e responsável são editáveis (ADM, diretores e financeiro) e ficam guardados. Já vêm preenchidos com a análise da planilha de 10/11; os títulos novos recebem uma ação sugerida (em cinza). Exportar para Excel.
- Recebimentos sem cliente identificado (DNI): os 95 depósitos e créditos sem conciliação da planilha, com o possível título e a marcação de conciliado.

## v80 — 10/11/2026 — Subtotal com pagamentos, falta receber, planilha e sistema

- Subtotal da Planilha de vendas completo: soma também o 1º, o 2º e o 3º pagamento (como aparecem na grade: o anotado ou, em branco, o recebido na Conta Azul), a linha 1º + 2º pagamento, o Falta receber e as colunas Planilha (pedido), Sistema (Conta Azul) e a diferença entre elas.

## v79 — 10/11/2026 — Anexar comprovantes e notas fiscais em lote

- 📎 Anexar em lote (Planilha de vendas, gestão): selecione vários comprovantes e notas fiscais de uma vez, junto com o manifesto.json, e o painel coloca cada arquivo no pedido certo. Sem manifesto ou sem código do pedido, ele sugere o pedido pelo nome de quem pagou e pelo valor; você confere, ajusta e clica em Anexar. Pedidos que ainda estão só na planilha são trazidos para o painel automaticamente. Arquivo já anexado no mesmo pedido não é enviado de novo.

## v78 — 10/11/2026 — Falta receber, parcelas personalizadas, comprovantes e nota fiscal

- Falta receber: nova coluna na Planilha de vendas (total do pedido − o que já foi baixado na Conta Azul; mostra "quitado" quando está tudo recebido) e card Falta receber com o total em aberto do período.
- Parcelas → Personalizado…: o vendedor informa o valor e a data de cada parcela, e o painel confere se a soma bate com o total do pedido. A venda vai para a Conta Azul com essas parcelas.
- 📎 Comprovantes e nota fiscal: botão no começo da linha de cada pedido. O vendedor anexa o comprovante de pagamento; a gestão anexa a nota fiscal. PDF ou foto até 5 MB (fotos grandes são reduzidas). Os arquivos ficam guardados no painel e tudo fica no Histórico de alterações.
- Nota fiscal da Conta Azul: o painel consulta as notas emitidas das vendas aprovadas dos últimos 75 dias (até 25 por vez, para gastar pouco) e mostra o número, a data e a chave no 📎 do pedido.

## v77 — 10/11/2026 — Lote em qualquer parte do nome vai para a observação

- Lote em qualquer parte do nome do cliente: o painel tira o lote do nome também quando ele vem no começo ou no meio, ou entre colchetes (ex.: "Lote 1: Alpha Run" → Alpha Run; "BOX CTPL - Lote 2 - Itapetim/PE" → BOX CTPL; "[Correria 83 - Lote 2]" → Correria 83; "Cultura Inglesa RUN: LOTE 2 KIDS" → Cultura Inglesa RUN). O lote e o que vem depois dele vão para a coluna Lote / obs. do cliente, e essas linhas saem das Inconsistências. Vale para a planilha do Google e para os pedidos já trazidos para o painel.

## v76 — 10/11/2026 — Explicação dos indicadores mais completa

- Balãozinho dos indicadores mais explicado, em linguagem do comercial: o que é, a conta com um exemplo e como ler o número (Vendas, Clientes, Vendedores e premiação). Na Projeção do mês, o balão traz a conta com os números do mês, o que quer dizer "pelo ritmo de N dias", o que é o PE e os cuidados da projeção.

## v75 — 10/11/2026 — Balãozinho com a explicação dos indicadores

- Balãozinho de explicação: passe o mouse no card (ou toque no ⓘ no celular) para ver como cada indicador é calculado. Vale para os cards de Vendas, Painel executivo, Clientes, Vendedores e premiação, Financeiro, Conferência e Aprovações. Na Projeção do mês, o balão mostra a conta com os números do mês (vendido até hoje ÷ dias × dias do mês) e quanto falta para o ponto de equilíbrio.

## v74 — 10/11/2026 — Lote já tratado sai das Inconsistências

- Inconsistências · Cliente com "lote" no nome: o lote que o painel já tirou do nome e levou para a coluna Lote / obs. do cliente não aparece mais como inconsistência, mesmo que a planilha do Google ainda tenha o nome com o lote. Só fica na lista o cliente que ainda está com o lote no nome no painel.

## v73 — 10/11/2026 — Aprovações na Comercial, aviso no WhatsApp e vídeo todo narrado

- Aprovações (Comercial): página nova para a diretoria com os pedidos de alteração de preço aguardando (Aprovar / recusar), as respondidas nos últimos 30 dias e o número de pendentes no menu. O vendedor vê ali os pedidos dele.
- Aviso no WhatsApp: ADM e diretores cadastram até 5 números em Aprovações. Quando o vendedor envia um pedido de alteração, aparece o botão Avisar no WhatsApp, que abre o WhatsApp dele com a mensagem pronta (pedido, cliente, valor de antes e o novo, motivo e o link para aprovar).
- Inconsistências: a conferência pedido a pedido com a Conta Azul (valor diferente, pedido sem venda no sistema, venda sem pedido na planilha, pagamentos) passa a valer a partir de setembro/2026, quando o código do pedido começou. Agosto fica só com o fechamento pelo total do mês, em Divergências.
- Treinamento: vídeo da Eva com voz em todas as cenas (4 min 16 s), incluindo Parcelas, alteração de preço, aviso no WhatsApp e a página Aprovações.

## v72 — 09/11/2026 — Mesmo pedido numa linha só nas Inconsistências de pagamento

- Inconsistências · Valor recebido diferente do anotado na planilha: o mesmo pedido aparece numa linha só, com o 1º e o 2º pagamento juntos (ex.: Geraldo Costa 0021112026). A conferência continua a mesma.

## v71 — 09/11/2026 — Mês da premiação manual por venda

- Premiação: nova coluna Mês da premiação (manual) na Planilha de vendas, ao lado de Premiação % (manual). A venda com o mês preenchido sai do mês da venda e entra no faturamento e na premiação do mês escolhido, sem mudar a data da venda nem os outros relatórios. Ex.: Raíra Sicoob, venda de 01/10 premiada em setembro (autorização do Egberto); use o Motivo do % diferente para registrar a autorização.

## v70 — 09/11/2026 — Conferência de pagamentos volta como estava

- Inconsistências: Valor recebido diferente do anotado na planilha volta exatamente como estava até a v68 (1º e 2º pagamento comparados com cada parcela da Conta Azul). A mudança da v69 marcava como diferença os pedidos com pagamento anotado na planilha e ainda não baixado na Conta Azul.

## v69 — 09/11/2026 — Pagamentos conferidos pelo total recebido do pedido

- Diretores e Comercial também vendem: no cadastro deles (Usuários e permissões → Editar) há o campo Nome dele na planilha (coluna Vendedor). Com ele preenchido, o + Novo pedido já vem com o nome dele como vendedor, e as vendas e a premiação ficam ligadas ao login.
- Inconsistências · Valor recebido diferente do anotado na planilha: agora compara o total recebido do pedido (1º + 2º pagamento da planilha × tudo o que já entrou na Conta Azul), numa linha só por pedido. Antes comparava parcela por parcela e mostrava duas linhas do mesmo pedido quando a Conta Azul tinha o pagamento dividido em outras baixas (ex.: 696,00 = 382,50 + 313,50).

## v68 — 09/11/2026 — Planilha de vendas com todas as linhas no mesmo padrão

- Planilha de vendas: todas as linhas no mesmo padrão. Os pedidos lidos da planilha (de 04/11 em diante) ficam iguais aos trazidos para o painel: ⊕, 🔒 e 💲 primeiro e a marca planilha depois, e o cadeado também aparece na data, no código e nos valores quando o pedido está fechado.

## v67 — 09/11/2026 — Diretores criam o acesso dos vendedores

- Pedido fechado (mais de 24 h): o vendedor não inclui mais item no mesmo pedido. O ＋ some da linha e o painel recusa; peças a mais entram pelo ⊕ (pedido complementar). A gestão continua podendo incluir.
- Diretores criam e cuidam do acesso dos vendedores: o menu Administração → Usuários e permissões passa a aparecer para o perfil Diretor. O diretor cadastra, edita, gera senha temporária ou link e remove usuários Vendedor, Comercial e Consultor externo. ADMs, diretores e financeiro, e as tabelas do que cada perfil vê, continuam só com o ADM.

## v66 — 09/11/2026 — Pedido da planilha abre mais rápido para alterar

- Alterar ou complementar um pedido da planilha ficou mais rápido: o painel lê a planilha do Google uma vez só (antes eram três leituras seguidas) e aproveita a leitura dos últimos 10 minutos; a tela não espera mais o recálculo dos indicadores, que é feito em seguida.

## v65 — 09/11/2026 — Vídeo do treinamento com parcelas e aprovação de preço

- Cadeado 🔒 também nos pedidos lidos da planilha do Google (de 04/11 em diante estavam sem cadeado) e nos trazidos para o painel: contam as 24 horas pela data da venda.
- Unificar clientes: o que vem depois do nome (ex.: Giba - Clube Cabo Branco (Dental Center) → Dental Center; Lote 2) vai para a coluna Lote / obs. do cliente. As linhas já unificadas recuperam esse texto sozinhas. As vendas continuam separadas: só o nome do cliente fica igual.
- Alteração de preço: o 💲 aparece também nos pedidos lidos da planilha. Em Ver o painel como (perfil Vendedor ou Comercial), a Planilha de vendas fica como o vendedor vê, com cadeado e 💲, para a gestão conferir.
- Vídeo do treinamento atualizado (4 minutos): mostra o campo Parcelas (à vista, 2x ou mais), o pedido de alteração de preço em pedido fechado e a aprovação pela gestão, além do cliente da carteira com recompra automática, o Enter, o cadeado e os pedidos da planilha.

## v64 — 09/11/2026 — Parcelas no pedido e aprovação de alteração de preço

- Campo Parcelas no pedido: 2x (50% + 50%) como padrão, À vista, ou 3x a 12x (parcelas iguais a cada 30 dias). Vale na linha do Novo pedido, no formulário e na célula da Planilha de vendas, e a venda vai para a Conta Azul com essas parcelas.
- Coluna 3º pagamento em diante: soma das parcelas a partir da 3ª, preenchida pela Conta Azul quando baixadas.
- Alteração de preço em pedido fechado (mais de 24 h): o vendedor clica no 💲 (ou na célula do valor com cadeado), informa o novo valor por unidade e o motivo e envia para aprovação. A gestão vê o quadro Alterações de preço aguardando aprovação, aprova ou recusa; aprovado, o valor muda no pedido e tudo fica no Histórico. Se o pedido já estava na Conta Azul, a marca CA ! avisa para corrigir lá.
- Treinamento: passos novos sobre Parcelas e alteração de preço com aprovação.

## v63 — 09/11/2026 — Premiação da Milena volta ao cálculo anterior

- Premiação: o pedido da Cabo Branco (Milena, outubro) estava com Premiação % gravada como 0%, por um erro das versões até a v60 (salvar o campo em branco virava 0%). Por isso a premiação da Milena caiu para R$ 2.987,25. Esses 0% voltam para em branco e o pedido segue a faixa do mês (Milena volta a R$ 3.179,15 em outubro). O % devido é ajustado pela gestão na coluna Premiação % (manual). A correção roda uma vez só e fica no Histórico de alterações.

## v62 — 09/11/2026 — Vídeo do treinamento narrado, cadeado, marca planilha e recompra automática

- Treinamento: o vídeo narrado pela Eva (3 minutos, com voz e legendas) está em Comercial → Treinamento. O navegador não guarda mais a versão antiga do vídeo.
- Pedidos que vieram da planilha aparecem com a marca planilha.
- Pedido fechado (mais de 24 horas) mostra o cadeado 🔒 na linha; complementares (-1, -2…) aparecem com a marca ajuste.
- Novo × recompra: cliente que já comprou antes é marcado como Recompra automaticamente, mesmo nos pedidos da planilha que estavam em branco. O preenchimento também roda quando o painel é publicado.
- Inconsistências: enquanto a planilha estiver em uso, os pedidos de novembro que estão só na planilha não aparecem mais como erro.

## v61 — 09/11/2026 — Correção da Planilha de vendas, premiação por pedido, Enter, cliente da carteira e horários

- Correção: ao alterar um pedido que veio da planilha num mês antes de novembro (ex.: % de premiação da Cabo Branco em outubro), as outras vendas do mês sumiam da Planilha de vendas. Agora só aquele pedido passa a valer pela versão do painel; as demais continuam vindo da planilha. O pedido vem junto com os complementares (-1, -2…).
- Premiação % (manual): botão Salvar ao lado do campo em edição; em branco volta a seguir a faixa do mês (não vira 0%). O % salvo já entra em Vendedores e premiação.
- Lançamento: Enter passa para o próximo campo, como o Tab, na linha do pedido e no formulário.
- Cliente da carteira: ao digitar um cliente que já comprou, o painel marca Recompra e trava o campo. Cliente sem compra anterior mostra os nomes parecidos já cadastrados (Já existe na carteira?) e o + avisa antes de cadastrar um cliente que já existe.
- Botão Preencher novo × recompra (gestão): preenche os campos em branco no painel e envia para a planilha do Google (Novo na 1ª compra, Recompra depois). Roda também nos horários automáticos.
- Pedidos que vieram da planilha não têm mais o ✕ (excluir) enquanto a planilha estiver em uso; o ⏱ mostra o histórico de alterações.
- Divergências: botão Importar fatura do cartão (OFX, CSV ou Excel da fatura).
- Filtros: o período De/Até vale sobre o mês escolhido; botão Limpar filtros; Atualizar agora e Atualizar recarregam a tela sem precisar de F5.
- Horários automáticos: 09:30, 14:00 e 17:30. A Conta Azul é lida por completo uma vez por dia; nas outras atualizações só do mês anterior em diante.

## v60 — 09/11/2026 — Vídeo do treinamento com narração

- Vídeo do treinamento com narração em voz feminina (Camila, português do Brasil), no tempo de cada tela, dentro de Comercial → Treinamento. As legendas acompanham a fala.

## v59 — 09/11/2026 — Alterar e complementar pedidos da planilha e + Ação nas divergências

- Pedidos que vieram da planilha (marca "planilha") agora também têm o ＋ (novo item) e o ⊕ (pedido complementar), e podem ser alterados clicando na célula (dois cliques para confirmar). O pedido passa para o painel com todas as linhas do mesmo código e a versão do painel passa a valer; as correções seguem a regra das 24 horas a partir desse momento. Vale até a planilha ser encerrada.
- Divergências: quando o mês tem diferença, aparece sozinha uma caixa com o valor e as causas (pedidos com valor diferente, vendas só na Conta Azul, pedidos só na planilha e linhas sem código), com o link Ver pedido a pedido.
- Divergências: botão + Ação em cada mês do comercial e em cada mês de cada conta do financeiro, para incluir uma ação com responsável sem abrir a edição; cada ação tem Marcar como concluída. A conta com ação aberta mostra um número laranja no mês.

## v58 — 08/11/2026 — De-para do número da Conta Azul e pedido complementar no envio

- De-para do número da Conta Azul (que não tem os zeros do começo) com o código do painel: 21112026 = 0021112026. O pedido complementar vai para a Conta Azul como venda própria, com o sufixo colado no número (0021112026-1 → 211120261), e volta para o painel como 0021112026-1, sem diferença na conferência.
- Na conciliação do mês, o pedido e os complementares são somados juntos dos dois lados. Nas listas, as vendas só no sistema aparecem com o código no formato do painel.
- Treinamento: vídeo com a Eva (3 minutos) dentro da página Comercial → Treinamento, com legendas: lançar o pedido, cliente novo, vários itens, regra das 24 horas, pedido complementar e Conta Azul.

## v57 — 08/11/2026 — Pedidos do painel viram vendas na Conta Azul

- Pedidos do painel viram vendas na Conta Azul: em Planilha de vendas → De onde os indicadores leem as vendas, o ADM liga o envio. Nos horários (09:30, 12:00, 14:00 e 18:00), no Atualizar agora e no botão Enviar agora, cada pedido lançado no painel vira uma venda em andamento na Conta Azul, com o mesmo número, o tipo de produto como item (se o produto não existir na Conta Azul, é criado), pagamento 50% + 50% (1ª parcela na data da venda, 2ª no prazo de entrega ou 30 dias depois) e a forma de pagamento informada. Cliente que não existe na Conta Azul é cadastrado.
- Na linha do pedido aparece CA ✓ (venda criada), CA ✕ (erro, com o motivo ao passar o mouse) ou CA ! (pedido alterado depois do envio: corrigir na Conta Azul). Pedido que já existia com o mesmo número na Conta Azul não é enviado de novo.
- Pedido complementar (-1, -2…) não vai sozinho: a Conta Azul só aceita número inteiro na venda.

## v56 — 08/11/2026 — Divergências no formato do fechamento, novembro da planilha, botão + e cadastro único

- Conferência → Divergências: tela nova no formato do fechamento validado. Comercial mês a mês (planilha de vendas × Conta Azul, divergência e observações e ações por responsável, com o que já foi concluído em verde) e Financeiro por conta (extrato × Conta Azul, conferido, incompleto ou diferença, com saldos e observações ao abrir cada conta). Os totais do comercial são recalculados a cada atualização; o fechamento validado de 08/11 já vem preenchido. Gestão e financeiro editam observações, ações, saldos e contas; o botão Importar extrato leva à conciliação bancária.
- Planilha × sistema (mês) fica só em Controle (ligação da planilha do Google).
- Pedidos de novembro: enquanto a planilha do Google estiver em uso, as vendas lançadas nela a partir de novembro também entram no painel, sem data final. Na Planilha de vendas → Fonte dos indicadores, o botão Encerrar a planilha transforma essas vendas em pedidos do painel e a planilha deixa de ser lida.
- Botão + ao lado de Cliente, Tipo de produto, Material e Cor no lançamento (linha do pedido e formulário). O cliente novo entra na lista do painel e é cadastrado também na Conta Azul (nome, tipo de pessoa e, se tiver, CNPJ/CPF, e-mail e telefone).
- Cadastro único por cliente: o mesmo cliente escrito de jeitos diferentes vira um nome só em todo o painel e nos pedidos gravados; o lote vai para a coluna Lote / obs. do cliente. Sai da lista de Inconsistências.
- Subtotais: linha de total em todas as tabelas com valores que ainda não tinham (Produtos, Clientes, Vendedores, Pedidos, Contas a receber e outras).
- Botão Enviar pedidos agora renomeado para Atualizar agora: ele lê a Conta Azul e grava os pagamentos na planilha na hora. O painel ainda não cria a venda na Conta Azul (só o cliente novo).
- Treinamento atualizado com o botão +, o ⊕ do pedido complementar, o Atualizar agora e a planilha em uso.

## v55 — 08/11/2026 — Unificar todos os clientes

- Botão "Unificar todos os clientes" em Qualidade dos dados: junta as grafias de cada cliente com o nome sugerido, e o lote continua na coluna de observação.

## v54 — 08/11/2026 — Ligação da planilha de volta e inclusão de cliente novo

- Planilha × sistema (mês) voltou para Controle, com a ligação da planilha do Google.
- Botão "+ Incluir cliente" no lançamento quando o nome não existe na lista.

## v53 — 08/11/2026 — Prazo aberto para os pedidos

- Prazo final da importação e da gravação automática em aberto: vale tudo a partir de janeiro de 2026, sem data limite (antes estava em outubro e depois em dezembro).
- Pedidos de novembro e os lançamentos feitos no painel entram nos horários automáticos e no botão Enviar pedidos agora.

## v52 — 08/11/2026 — Envio sob demanda, filtro de período e divergências em Conferência

- Botão "Enviar pedidos agora" na Planilha de vendas (só gestão): atualiza a Conta Azul e grava os pedidos na planilha na hora, para grandes volumes. Os horários automáticos continuam: 09:30, 12:00, 14:00 e 18:00.
- Divergências por mês movida para o grupo Conferência. Treinamento movido para o grupo Comercial, com aviso de vídeo em breve.
- Filtro de período (De / Até) na Planilha de vendas.
- Aviso de cliente novo ao digitar um nome que ainda não existe no lançamento de pedido.

## v51 — 08/11/2026 — Treinamento no painel

- Novo item Treinamento no menu Controle: passo a passo para lançar pedidos, corrigir nas primeiras 24 horas, acrescentar peças com pedido complementar e entender os horários de atualização.
- Perfis Comercial, Financeiro e Vendedor passam a ver o Treinamento.

## v50 — 08/11/2026 — Subtotais na Planilha de vendas

- Subtotal das linhas visíveis na Planilha de vendas (quantidade e total, com a contagem de linhas).
- Vendedores e premiação: a premiação de cada venda usa o percentual manual quando informado.

## v49 — 08/11/2026 — Corte de novembro, horários de sincronização e premiação por venda

- Pedidos de novembro voltam a entrar: a gravação automática na planilha e a importação tinham o corte fixado em outubro. Agora vão até dezembro.
- Gravação e atualização da Conta Azul em horários fixos (Fortaleza): 09:30, 12:00, 14:00 e 18:00. Entre um horário e outro o painel usa o que já está salvo, para consumir menos a API e o Render.
- Premiação: coluna "Premiação % (manual)" na Planilha de vendas. Uma venda com percentual informado paga esse percentual e o restante do mês segue a faixa, com a coluna "Motivo do % diferente".
- Premiação: os pontos da política a ajustar (margem, redução por venda e faixas intermediárias) estão descritos na página Vendedores e premiação.
- Aba Versões do painel oculta para o perfil Vendedor.

## v48 — 04/11/2026 — Novo pedido em linha, igual à planilha, com vários itens

- + Novo pedido agora abre uma linha em cima da grade, nas mesmas colunas e na mesma ordem da planilha (data, mês, código, cliente, lote, nome do pedido, vendedor… observação), em vez do card. O formulário (card) continua em "Abrir no formulário".
- Pedido com itens diferentes: o botão + Item do mesmo pedido acrescenta outra linha com o mesmo código, já com cliente, data, vendedor e demais dados do pedido; só se preenche o item (tipo de produto, material, especificação, quantidade, cor, valor/und, lote e observação). O total de cada linha e do pedido é calculado na hora, e novo × recompra é sugerido pelo histórico do cliente.

## v47 — 04/11/2026 — Correção da lista vazia e aviso do script antigo

- Corrigido o erro "vazio is not defined", que quebrava Inconsistências (e outras listas) quando um filtro não tinha nenhuma linha.
- Ao ligar a planilha pelo e-mail, o painel avisa na hora se o endereço ainda roda o código antigo do script (lê, mas não grava).

## v46 — 04/11/2026 — Mês a mês clicável e endereço do script

- Planilha × sistema (mês): clicar num mês da tabela Mês a mês abre a conta daquele mês (ponte, motivos e pedidos) no alto da página. O resumo explica o que é "achado pelo código" e "achado pelo cliente e data".
- Gravação na planilha: quando o endereço ligado no painel ainda é o da implantação antiga, a mensagem explica que uma implantação nova muda o endereço e que é preciso colar a URL do App da Web no painel. Ao religar, o painel já mostra a versão do script.

## v45 — 04/11/2026 — Conciliação do mês pedido a pedido e quanto falta receber

- Planilha × sistema (mês) refeito pedido a pedido: o painel casa cada pedido da planilha com a venda da Conta Azul pelo código (cód. interno = número da venda) e, só quando não há código, pelo cliente e a data (até 20 dias). Antes a comparação era por nome de cliente, e nomes escritos de jeitos diferentes viravam "só no sistema" e "sem lançamento" ao mesmo tempo.
- Itens do mesmo pedido (mesmo código, variação de produto, lote ou observação) contam como um pedido só. A conta mostra quantos pedidos batem e quantos foram casados pelo código.
- "Lançadas com data de outro mês" virou "Mesma venda, data de outro mês no sistema": mostra a venda, as duas datas e quantos dias de diferença. O pedido está certo; só muda em qual mês o valor entra. Novo motivo para o caso contrário (venda do mês no sistema que está em outro mês na planilha).
- Cada motivo abre a lista com o pedido da planilha e a venda do sistema lado a lado (código, cliente, datas, dias, valores e como casou).
- Inconsistências: nova coluna Falta receber (recebido × total do pedido, ou "quitado"), também na exportação e no texto de "Pagamento em branco, já baixado".
- "Valor do pedido diferente na Conta Azul" (total da venda) e "Valor recebido diferente do anotado na planilha" (1º/2º pagamento) ficaram com nomes e explicações claros. O de pagamento não aparece mais quando o pedido já está em valor diferente, e em pedido com vários itens vale a soma das linhas ou o valor repetido em cada linha.
- "Mesmo cliente com nomes diferentes" passou a ser "Mesmo cliente escrito de jeitos diferentes": só maiúscula, acento ou pontuação. Complementos do nome (destino, setor, classificação interna) não são mais inconsistência.
- Gravação na planilha: a mensagem "o script na sua conta ainda é o antigo" aparecia para qualquer erro do Google. Agora o painel mostra o erro de verdade, e o script novo (versão 45) devolve o motivo do erro e informa a própria versão, que aparece no quadro de gravação.

## v44 — 04/11/2026 — Gravação na planilha, inconsistências numa base só e campos em branco clicáveis

- Gravação na planilha do Google: religar a planilha desligava sem avisar a gravação automática dos pagamentos (por isso os pagamentos baixados pararam de ir para a planilha). Agora religar mantém a gravação, o horário e o mês-limite, e a gravação vem ligada por padrão.
- Inconsistências mostra o quadro "Gravação na planilha do Google": ligada ou desligada, a última gravação (quantas células, erro ou motivo do adiamento) e os botões Gravar na planilha agora e Gravar mesmo assim. Cada pedido que não foi gravado mostra o motivo (célula com fórmula, já tinha valor, código não encontrado) e a linha.
- Inconsistências usa uma base só: a planilha do Google até outubro e a Planilha de vendas do painel a partir de novembro (sai a escolha Planilha × Planilha de vendas do painel). Novo filtro Tipo de inconsistência e a opção "Batendo com a Conta Azul", que lista os pedidos já certos (mesmo código e mesmo valor, com o que foi recebido).
- "Mesmo cliente e dia com códigos diferentes" saiu: são itens do mesmo pedido. "Mesmo código em pedidos diferentes" virou "Mesmo código para clientes diferentes": linhas do mesmo código e do mesmo cliente (variação de produto, lote ou destino) não aparecem mais.
- Qualidade dos dados: cada campo em branco abre a lista das linhas (com o número da linha na planilha), com pesquisa, filtro por mês e exportação em Excel, PDF ou CSV. ADM, diretoria e financeiro preenchem ali mesmo e o painel grava na planilha do Google, só em célula vazia, conferindo o cliente da linha e respeitando as listas suspensas. Código em branco só é cobrado a partir de setembro/2026.
- Grafias diferentes mostra o valor consolidado que o painel usa. Nome dos vendedores num padrão só (Daniel, não DANIEL ou daniel) em todas as telas e nos pedidos do painel.
- Planilha × sistema (mês): cada motivo encontrado abre as vendas ou linhas por trás do valor. Meses antes de agosto/2026 aparecem como "antes da Conta Azul".
- Nota dos pagamentos na planilha: em pedido com mais de uma linha, a nota diz que o valor é do pedido inteiro. O script novo (copiar de novo pelo painel) é preciso para preencher campos em branco e para ver os motivos do que não foi gravado.

## v43 — 03/11/2026 — Conciliação bancária e Planilha de vendas completa
- `src/extrato.js` e `/api/extrato`: importa OFX/CSV/Excel por conta (sem duplicar) e cruza com as baixas de receber/pagar da Conta Azul (valor exato, ±3 dias).
- Página Financeiro → Conciliação bancária (permissão `extrato`, incluída para Financeiro e Diretor).
- Planilha de vendas mostra os meses da planilha em modo consulta com os balões; pesquisa rápida em Inconsistências; contador de clientes no + Novo pedido.

## v42 — 03/11/2026 — Filtro de período nas Inconsistências
- Período: mês, ano, todos ou de/até pela data da venda.

## v41 — 03/11/2026 — Nota na planilha igual ao balão
- Notas de 1º/2º PAGAMENTO no formato do balão do painel; nota com todas as parcelas em PEDIDO 100% PAGO (script atualizado).

## v40 — 03/11/2026 — Proteção de fórmulas
- Script do Google não escreve em célula com fórmula.

## v39 — 03/11/2026 — Importar só as linhas novas
- Modo `novas` (padrão) na importação: só as linhas da planilha que ainda não estão no painel (chave: código, data, cliente, produto, cor, quantidade, total).

## v38 — 03/11/2026 — Correção da fonte mista
- Planilha × sistema (mês), faturamento em Vendas e lista de clientes reconhecem a fonte `misto` (antes mostravam "a leitura falhou" / "planilha não ligada").

## v37 — 03/11/2026 — Planilha até outubro, sistema a partir de novembro
- Script grava no próprio .xlsx (cópia temporária convertida → preenche → `files.update` no mesmo arquivo), com bloqueio, regra de 15 min sem edição, conferência de alteração durante a gravação e versão anterior marcada para guardar.
- Gravação limitada às vendas até o mês escolhido (padrão out/2026); preenche também FORMA DE PAGAMENTO vazia.
- Fonte `misto`: planilha antes do corte (2026-11) + pedidos do painel a partir dele; `so_planilha` alimenta a inconsistência "Venda a partir de novembro só na planilha".

## v36 — 03/11/2026 — Recebimentos gravados na planilha do Google
- Script do Google com `doPost`: grava valor em 1º/2º PAGAMENTO (com nota: data, banco, forma) e SIM em PEDIDO 100% PAGO, só em células vazias e só em Planilha Google.
- `/api/planilha-script/gravar` (ativar a cada 10 min e gravar agora) e `/api/planilha-script/arquivo` (trocar o ID quando o .xlsx for convertido).
- Inconsistências: novo tipo "Pagamento em branco, já baixado na Conta Azul".

## v35 — 03/11/2026 — Detalhe do pagamento no balão
- Colunas Data 1º/2º pag. e Banco saem da grade; o detalhe (data, banco, forma, situação) fica no balão do 1º/2º pagamento.
- Balão em Pedido 100% pago com todas as parcelas do pedido.
- Data e banco seguem gravados (`data_pag1`, `data_pag2`, `banco_pag`, `pag_ca`) e vão na exportação.

## v34 — 03/11/2026 — Clientes cadastrados, sequência da planilha e pagamentos da Conta Azul
- `/api/pedidos/clientes`: cadastro da Conta Azul + planilha + vendas + painel, com última compra.
- Código automático continua a sequência do mês da planilha ligada e dos números de venda da Conta Azul.
- `preencherPagamentos`: completa pag1/pag2, data_pag1/data_pag2, banco_pag, forma de pagamento e pago_100 com as baixas da Conta Azul (só campos vazios; automático a cada leitura e botão Preencher pagamentos).
- Parcelas ligadas ao pedido pelo número da venda ou, sem ele, por cliente + valor.

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
