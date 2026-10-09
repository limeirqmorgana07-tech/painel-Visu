# Painel de Gestão Visu (comercial e financeiro)

Painel de vendas da Visu Indústria Têxtil, desenvolvido pela Seja Expert. Segue a **Especificação do Painel de Vendas** (Tiago Sobral, 08/10/2026), escrita a partir da reunião presencial de 06/10/2026 com o Egberto.

Código no GitHub, publicação no Render (a hospedagem definitiva será decidida com a FluxIA). O painel é complementar ao painel financeiro e à Conta Azul, que segue como sistema transacional.

## Páginas

| Página | Conteúdo | Fonte |
|---|---|---|
| **Visão geral** | Vitrine com os produtos do catálogo e as peças vendidas, faturamento, pedidos (R1), ticket médio (R2), novas vendas x recompra (R3) e evolução de 12 meses com o ponto de equilíbrio (C1). | Planilha ou Conta Azul |
| **Produtos** | Mix por material + cor, tipo de produto, material e cor, em peças ou R$ (R4); ticket médio por tecido (R2). | Planilha ou itens das vendas na Conta Azul |
| **Clientes** *(a validar)* | Curva ABC e top 10 (C3), faixas de valor e maior pedido (C5), segmento (C6). | Planilha ou Conta Azul |
| **Vendedores** *(a validar)* | Faturamento, pedidos, ticket, vendas para clientes novos e régua da comissão (C7, C8). | Planilha ou Conta Azul (vendedor da venda) |
| **Pedidos e entregas** | Ciclo do pedido: quitados, com sinal e sem pagamento (C4). Entregas das próximas 3 semanas. | Planilha |
| **Financeiro** | Receita, despesas, resultado e ponto de equilíbrio; DRE gerencial por competência; regime de caixa; contas a receber e a pagar em aberto; saldos bancários. | Conta Azul |
| **Planilha × sistema** | Explica por que o total do mês difere entre a planilha do comercial e a Conta Azul: pedidos não lançados, vendas em andamento, data de outro mês, diferenças de valor. | Planilha + Conta Azul |
| **Qualidade dos dados** | Colunas reconhecidas, campos em branco, clientes com mais de um nome e grafias diferentes. | Planilha |

**Filtros em todas as páginas:** período (mês, ano até o mês, últimos 12 meses), mês, vendedor, tipo de venda (B2B/B2C), novo ou recompra, tipo de produto, material e cor.

### Regras de cálculo
- **Pedido:** cada código distinto em "Cód. interno" (ou "Nome do pedido (Trello)"). Sem código, as linhas do mesmo cliente no mesmo dia contam como um pedido.
- **Ticket médio:** faturamento ÷ número de pedidos. Por tecido: faturamento do tecido ÷ pedidos que levaram esse tecido.
- **Novo x recompra:** pela coluna "Cliente novo ou recompra?", preenchida pelos vendedores. Pedidos sem a marcação aparecem como "Sem classificação".
- **Mês em andamento:** é comparado com os mesmos dias do mês anterior.
- **Comissão:** sobre o faturamento (data e valor da venda), nunca sobre o recebimento. Começa em 1% a partir de R$ 15 mil no mês e chega a 5% a partir de R$ 50 mil, sem teto. A tabela intermediária ainda será confirmada com a Visu.
- **Cadastro do cliente:** "Yelloran lote 1" e "Yelloran - Lote 2" contam como "Yelloran". Diferenças de maiúsculas, acentos e espaços também são unificadas.
- **Grafias:** "Poliamida", "poliamida " e "POLIAMIDA" contam como um só material. O painel exibe a grafia mais usada. O mesmo vale para tipo de produto, cor e vendedor.

## Fonte dos dados

```
Planilha "Rotina de vendas_Gestão faturamento CLOUD" ──┐
                                                       ├─> Servidor ──(senha)──> Painel no navegador
Conta Azul (API v2, reserva e recebimentos) ───────────┘
```

1. **Planilha de vendas (principal).** Tem tecido, cor e novo x recompra, que a Conta Azul não tem.
2. **Conta Azul (reserva).** Se a planilha não estiver ligada, o painel lê as vendas da Conta Azul, mas sem o mix de produto e sem novo x recompra.
3. **Demonstração.** Sem nenhuma das duas, mostra dados fictícios com os produtos e tecidos do catálogo.

### Como ligar a planilha (escolha uma forma)

**A. Conta de serviço do Google (recomendado: a planilha continua privada)**
1. No [Google Cloud Console](https://console.cloud.google.com), crie um projeto e ative a **Google Sheets API**.
2. Em **IAM → Contas de serviço**, crie uma conta e gere uma chave **JSON**.
3. Na planilha, clique em **Compartilhar** e adicione o e-mail da conta de serviço (termina em `iam.gserviceaccount.com`) como **Leitor**.
4. No Render, crie as variáveis:
   - `GOOGLE_SERVICE_ACCOUNT_JSON`: o conteúdo inteiro do arquivo JSON
   - `PLANILHA_ID`: o código que fica entre `/d/` e `/edit` no link da planilha
   - `PLANILHA_ABA`: o nome da aba de vendas, por exemplo `Vendas 2026`

**B. Link CSV publicado (mais rápido, mas o link fica público)**
1. Na planilha: **Arquivo → Compartilhar → Publicar na Web**. Escolha a aba de vendas e o formato **CSV**.
2. No Render, crie `PLANILHA_CSV_URL` com o link gerado.

Quem tiver o link B consegue ver os dados. Use essa forma só para testes.

**Nomes das colunas.** O painel procura as colunas pelos nomes da seção 5 da especificação, sem diferenciar maiúsculas e acentos, e aceita alguns apelidos. Se alguma coluna tiver outro nome, há duas saídas: renomear o cabeçalho na planilha ou usar a variável `COLUNAS_JSON`, por exemplo `{"cliente":"Nome do cliente","material":"Tecido"}`. A página **Qualidade dos dados** mostra o que foi reconhecido.

## Variáveis de ambiente (Render → Environment)

| Variável | O que colocar |
|---|---|
| `URL_PUBLICA` | Endereço do painel, sem barra no fim |
| `PAINEL_SENHA` | Senha de acesso ao painel |
| `SESSION_SECRET` | Texto longo e aleatório (botão Generate) |
| `GOOGLE_SERVICE_ACCOUNT_JSON`, `PLANILHA_ID`, `PLANILHA_ABA` | Planilha pela forma A |
| `PLANILHA_CSV_URL` | Planilha pela forma B |
| `COLUNAS_JSON` | Opcional: nomes de coluna diferentes do padrão |
| `CONTA_AZUL_CLIENT_ID`, `CONTA_AZUL_CLIENT_SECRET` | Aplicação de **produção** do Portal do Desenvolvedor da Conta Azul |
| `CONTA_AZUL_URL_LOGIN` | `https://login.contaazul.com/#/oauth/authorize` (já é o padrão) |
| `CONTA_AZUL_URL_TOKEN` | `https://api-v2.contaazul.com/oauth/token` (já é o padrão) |
| `PONTO_EQUILIBRIO` | Padrão `176000` (DRE de agosto/2026). Atualizar quando vier do painel financeiro. |
| `META_MENSAL` | Meta de vendas do mês, se a Visu tiver (C2). `0` = sem meta. |
| `COMISSAO_INICIO` / `COMISSAO_TETO` | Padrão `15000` e `50000` |
| `DATABASE_URL` | **Recomendado:** Postgres para guardar a conexão da Conta Azul e o cache de itens entre reinícios |
| `FONTE_VENDAS` | `auto` (padrão: planilha quando ligada, senão Conta Azul), `planilha` ou `conta_azul` |
| `CACHE_SEGUNDOS` | Padrão `300`. A tela também se atualiza sozinha a cada 5 minutos. |

## Conta Azul

**O que é lido pela API v2:**
- **Vendas:** endpoint `/v1/venda/busca`. Só entram como vendidas as vendas **Aprovadas** e **Faturadas**. "Esperando aprovação", em andamento, orçamento e cancelada ficam de fora e aparecem na conciliação. O mês é o da **data da venda**.
- **Vendedor:** a listagem de vendas não traz o vendedor. O painel lê `/v1/venda/vendedores` e associa as vendas de cada um.
- **Produtos:** endpoint `/v1/venda/{id}/itens`. Tipo, material e cor saem do nome do produto cadastrado, pelos termos do catálogo. Os termos podem ser ajustados com `PRODUTOS_TERMOS_JSON`. Os itens são buscados aos poucos, por causa do limite de 50 chamadas por minuto, e ficam guardados.
- **Financeiro:** contas a receber e a pagar (competência, pagamento e vencimento), estrutura da DRE (`/v1/financeiro/categorias-dre`) e saldo das contas financeiras.

### Manter a conexão depois de reiniciar (importante)
No plano gratuito do Render, os arquivos do servidor são apagados a cada deploy ou reinício. A conexão com a Conta Azul se perde junto, e o painel volta para os dados de demonstração. Escolha uma destas soluções:
1. **Banco Postgres gratuito no Neon** (neon.tech). Crie um projeto, copie a *connection string* e cole em `DATABASE_URL` no Render. O token e o cache de itens passam a ficar no banco.
2. **Render Starter + disco.** Mude o serviço para o plano Starter, adicione um **Disk** montado em `/var/data` e crie `ARQUIVO_TOKEN=/var/data/token.json`.

Depois disso, conecte a Conta Azul uma última vez.


- A aplicação precisa ser de **Produção** no Portal do Desenvolvedor. A de "Desenvolvimento" só funciona com a conta teste.
- URL de redirecionamento: `https://SEU-ENDERECO/callback`.
- Para conectar, clique em **Conectar Conta Azul** (rota `/conectar`) e autorize com um login que tenha acesso à empresa Visu.
- Para conferir os campos que chegam da API, use a rota `/api/diagnostico`.

## Rodar no computador

```bash
npm install
DEMO=1 PAINEL_SENHA=teste npm start        # dados de demonstração
PLANILHA_CSV_URL=... PAINEL_SENHA=teste npm start
# abra http://localhost:3000
```

## Estrutura

```
server.js            login, conexão Conta Azul, /api/vendas, /api/planilha, /api/diagnostico
src/planilha.js      leitura da planilha (CSV ou conta de serviço), mapeamento de colunas, conversões
src/vendas.js        escolha da fonte, padronização de grafias, relatório de qualidade, cache
src/contaAzul.js     OAuth da Conta Azul, renovação de token, leitura de vendas
src/tokenStore.js    onde o token fica guardado (Postgres ou arquivo)
src/financeiro.js    DRE, caixa, contas em aberto e saldos (Conta Azul)
src/produtos.js      tipo, material e cor a partir do nome do produto
src/demo.js          dados fictícios (planilha, sistema e financeiro)
public/vitrine/      camisetas e fotos recortadas do catálogo para a vitrine
src/config.js        variáveis de ambiente
public/painel.html   a tela do painel (os indicadores são calculados no navegador, para os filtros responderem na hora)
public/logo-visu.png logo do catálogo
```

## Identidade visual

Baseada no catálogo da Visu Design e no painel financeiro v1:
- **Cores:** azul-noite `#241E48`, laranja `#EA780C`, verde-água `#5ABAB4` e o fio em degradê da logo (verde-água → azul → magenta → vermelho → laranja).
- **Tipografia:** Outfit e Plus Jakarta Sans. O catálogo usa a Lufga, que não está disponível no Google Fonts.
- **Gráficos:** azul `#3A48A8` para recompra e laranja `#D96A05` para novos, uma combinação validada para daltonismo nos temas claro e escuro.

## Pendências (seção 7 da especificação)

- [ ] Ligar a planilha real e revisar a página **Qualidade dos dados** com o Tiago.
- [ ] Visu: meta formal de vendas (C2) e valor mensal.
- [ ] Visu: tabela completa de comissão entre 1% e 5%, e se quer ver a comissão no painel (C8).
- [ ] Visu: análise por segmento (C6) e quais grupos.
- [ ] Visu: existe dado de margem por pedido? Ele é necessário para o alerta de vendas abaixo de 40%.
- [ ] Visu: ajustes na planilha (cadastro único, coluna de frete, listas suspensas).
- [ ] Opcional: página de entregas da semana, a partir de "Prazo de entrega".
