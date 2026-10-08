# Painel Comercial Visu

Painel de vendas da Visu com dados em tempo real da Conta Azul (API v2). Projeto da Seja Expert, no mesmo modelo do Sistema de Gestão Vieira Diniz: código no GitHub, publicação no Render.

Primeiro módulo do sistema de gestão da Visu. Os próximos módulos (financeiro, DRE etc.) entram neste mesmo servidor.

## O que o painel mostra

- **Faturamento do mês** com comparação justa (no mês corrente, compara com os mesmos dias do mês anterior), projeção de fechamento e meta.
- **Indicadores:** número de vendas, ticket médio, clientes atendidos, orçamentos em aberto, conversão e canceladas.
- **Ritmo do mês:** faturamento acumulado dia a dia contra o mês anterior e a linha da meta.
- **Vendedores, produtos e clientes:** rankings com participação.
- **Últimos 12 meses**, com clique para abrir qualquer mês.
- **Situação das vendas:** aprovadas, faturadas, em andamento, orçamentos e canceladas.
- **Contas a receber:** em aberto, atrasado, a vencer em 30 dias, recebido no mês e maiores atrasos.
- **Vendas do mês:** as 25 mais recentes.

Regra de faturamento: entram todas as vendas do mês, **menos orçamentos e canceladas**.

Atualização: os dados ficam guardados por 5 minutos (`CACHE_SEGUNDOS`), e a tela recarrega sozinha a cada 5 minutos. O botão **Atualizar agora** força uma nova leitura.

## Como funciona

```
Navegador ──(senha)──> Servidor no Render ──(OAuth 2.0)──> API v2 Conta Azul
                          │ guarda e renova o token sozinho
                          └─ calcula os indicadores e entrega ao painel
```

A senha do aplicativo da Conta Azul (client secret) e o token ficam **só no servidor**. O painel no navegador nunca os vê.

Enquanto a Conta Azul não estiver conectada, o painel abre em **modo demonstração**, com números fictícios e um aviso amarelo no topo.

---

## Passo a passo de implantação

### 1. Subir o código no GitHub

1. Crie um repositório, por exemplo `painel-comercial-visu`.
2. Use **Add file → Upload files** e envie todo o conteúdo da pasta, **exceto** `node_modules`.

### 2. Criar o serviço no Render

1. No Render, clique em **New → Web Service** e escolha o repositório.
2. Preencha: Build Command `npm install`, Start Command `npm start` e Node 20 ou superior.
3. Depois de criado, anote o endereço, por exemplo `https://painel-comercial-visu.onrender.com`.

### 3. Criar o aplicativo na Conta Azul

1. Entre no [Portal do Desenvolvedor da Conta Azul](https://developers-portal.contaazul.com) e crie um aplicativo.
2. Na **URL de redirecionamento (redirect URI)**, coloque exatamente:
   `https://SEU-ENDERECO.onrender.com/callback`
3. Copie o **Client ID** e o **Client Secret**.

> **Atenção:** a Visu é acessada pelo Conta Azul Mais (BPO). A autorização do passo 5 precisa ser feita com um login que tenha acesso à **empresa Visu** dentro da Conta Azul. Se o login do Mais não aparecer na tela de autorização, confirme com a Conta Azul (integracoes@contaazul.com) qual usuário deve autorizar.

### 4. Variáveis de ambiente no Render (Environment)

| Variável | O que colocar |
|---|---|
| `URL_PUBLICA` | Endereço do Render, sem barra no fim. Exemplo: `https://painel-comercial-visu.onrender.com` |
| `CONTA_AZUL_CLIENT_ID` | Client ID do passo 3 |
| `CONTA_AZUL_CLIENT_SECRET` | Client Secret do passo 3 |
| `PAINEL_SENHA` | Senha que a Visu vai usar para abrir o painel |
| `SESSION_SECRET` | Qualquer texto longo e aleatório |
| `META_MENSAL` | Meta de faturamento do mês, em reais, só números. Exemplo: `180000`. Use `0` se ainda não houver meta. |
| `DATABASE_URL` | Opcional, mas recomendado (veja abaixo) |

Salve as variáveis e faça um **Manual Deploy**.

**Sobre o `DATABASE_URL`:** a Conta Azul troca o "token de renovação" a cada uso, então ele precisa ficar salvo. Sem banco, o token fica num arquivo que o plano gratuito do Render apaga a cada novo deploy ou reinício. Nesse caso, basta clicar em **Conectar Conta Azul** de novo. Para não precisar fazer isso, crie um Postgres no Render (**New → PostgreSQL**) e cole a *Internal Database URL* nessa variável.

### 5. Conectar

1. Abra o endereço do painel e entre com a `PAINEL_SENHA`.
2. No aviso amarelo, clique em **Conectar Conta Azul** e autorize com o login da Visu.
3. O painel volta já com os dados reais, e o selo no topo muda para **Conta Azul ao vivo**.

### 6. Conferência obrigatória na primeira conexão

A documentação pública da API v2 não fixa todos os nomes de campos de vendas. O código aceita as variações mais comuns, mas é preciso conferir uma vez:

1. Com o painel conectado, abra `https://SEU-ENDERECO.onrender.com/api/diagnostico`.
2. Confira se aparecem **vendas**, **contas a receber** e **itens da primeira venda** sem erro.
3. Compare o faturamento do mês no painel com o relatório de vendas da Conta Azul.

Se algum valor vier zerado ou algum nome vier como "Sem cliente" ou "Sem vendedor", copie o resultado do diagnóstico e envie para ajuste. A correção é feita nas funções `normalizarVenda`, `normalizarItem` e `normalizarReceber`, em `src/contaAzul.js`.

---

## Rodar no computador (teste)

```bash
npm install
DEMO=1 PAINEL_SENHA=teste npm start
# abra http://localhost:3000
```

## Estrutura

```
server.js            rotas: login, conectar/callback, /api/painel, /api/diagnostico
src/config.js        variáveis de ambiente
src/contaAzul.js     OAuth, renovação de token, fila de chamadas (até 50/min), leitura e normalização
src/painel.js        cálculo dos indicadores e cache
src/tokenStore.js    onde o token fica guardado (Postgres ou arquivo)
src/demo.js          dados fictícios do modo demonstração
public/painel.html   a tela do painel
public/logo.png      logo da Visu
```

## Endpoints da Conta Azul usados

| Uso | Endpoint |
|---|---|
| Autorização | `https://auth.contaazul.com/login` → `https://auth.contaazul.com/oauth2/token` (token vale 1 hora e é renovado sozinho) |
| Vendas | `GET /v1/venda/busca` (data_inicio, data_fim, paginação) |
| Itens da venda | `GET /v1/venda/{id}/itens`, para o ranking de produtos. O caminho precisa ser confirmado no diagnóstico. |
| Contas a receber | `GET /v1/financeiro/eventos-financeiros/contas-a-receber/buscar` |

Se a Conta Azul mudar algum endereço, ele pode ser trocado pelas variáveis `CONTA_AZUL_URL_LOGIN`, `CONTA_AZUL_URL_TOKEN` e `CONTA_AZUL_URL_API`, sem mexer no código.

## Pendências

- [ ] Ler a transcrição da reunião presencial e ajustar os indicadores ao que a Visu pediu.
- [ ] Definir a meta mensal (e, se a Visu quiser, metas por vendedor).
- [ ] Trocar `public/logo.png` pela logo em alta resolução.
- [ ] Validar os campos com o `/api/diagnostico` na primeira conexão.
