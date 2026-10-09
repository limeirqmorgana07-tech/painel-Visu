// Configuração lida das variáveis de ambiente (no Render: Environment → Environment Variables)
const env = process.env;

export const config = {
  porta: Number(env.PORT || 3000),
  urlPublica: (env.URL_PUBLICA?.trim() || `http://localhost:${env.PORT || 3000}`).replace(/\/$/, ''),

  // Credenciais do aplicativo criado no Portal do Desenvolvedor da Conta Azul
  clientId: (env.CONTA_AZUL_CLIENT_ID || '').trim(),
  clientSecret: (env.CONTA_AZUL_CLIENT_SECRET || '').trim(),

  // Endereços da API v2 (podem ser trocados por variável de ambiente se a Conta Azul mudar)
  urlLogin: env.CONTA_AZUL_URL_LOGIN || 'https://login.contaazul.com/#/oauth/authorize',
  urlToken: env.CONTA_AZUL_URL_TOKEN || 'https://api-v2.contaazul.com/oauth/token',
  urlApi: (env.CONTA_AZUL_URL_API || 'https://api-v2.contaazul.com').replace(/\/$/, ''),
  escopo: env.CONTA_AZUL_ESCOPO || 'openid profile aws.cognito.signin.user.admin',

  // Acesso ao painel
  senhaPainel: env.PAINEL_SENHA || '',
  segredoSessao: env.SESSION_SECRET || 'troque-este-segredo',

  // Banco opcional para guardar o token (recomendado no Render). Sem ele, usa arquivo local.
  databaseUrl: env.DATABASE_URL || '',
  arquivoToken: env.ARQUIVO_TOKEN || './dados/token.json',

  // Regras do painel
  metaMensal: Number(env.META_MENSAL || 0),
  // Ponto de equilíbrio apurado na DRE (reunião de 06/10/2026: R$ 176 mil). Atualizar quando a estrutura de custos mudar.
  pontoEquilibrio: Number(env.PONTO_EQUILIBRIO ?? 176000),
  // Comissão sobre faturamento: começa a pagar a partir de R$ 15 mil vendidos no mês e chega a 5% a partir de R$ 50 mil
  comissaoInicio: Number(env.COMISSAO_INICIO || 15000),
  comissaoTeto: Number(env.COMISSAO_TETO || 50000),
  cacheSegundos: Number(env.CACHE_SEGUNDOS || 300),
  mesesHistorico: Number(env.MESES_HISTORICO || 12),
  maxVendasComItens: Number(env.MAX_VENDAS_COM_ITENS || 2500),
  intervaloMs: Number(env.INTERVALO_ENTRE_CHAMADAS_MS || 1250), // ~48 chamadas/min (limite da API: 50/min)

  demo: env.DEMO === '1',
};

export const redirectUri = () => `${config.urlPublica}/callback`;
