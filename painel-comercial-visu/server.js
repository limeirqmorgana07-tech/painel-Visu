// Painel Comercial Visu — servidor (Seja Expert)
import express from 'express';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { config, redirectUri } from './src/config.js';
import * as ca from './src/contaAzul.js';
import { dadosDeVendas } from './src/vendas.js';
import { dadosFinanceiros } from './src/financeiro.js';
import { planilhaConfigurada } from './src/planilha.js';

const raiz = path.dirname(fileURLToPath(import.meta.url));
const app = express();
app.set('trust proxy', 1);
app.use(express.urlencoded({ extended: false }));

// ---------- sessão simples por cookie assinado ----------
const COOKIE = 'visu_sessao';
const assinar = (v) => crypto.createHmac('sha256', config.segredoSessao).update(v).digest('hex');
function lerCookie(req) {
  const m = (req.headers.cookie || '').match(new RegExp(`${COOKIE}=([^;]+)`));
  if (!m) return false;
  const [exp, sig] = decodeURIComponent(m[1]).split('.');
  const esperado = assinar(exp || '');
  return !!sig && sig.length === esperado.length &&
    crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(esperado)) && Number(exp) > Date.now();
}
function exigeLogin(req, res, next) {
  if (!config.senhaPainel || lerCookie(req)) return next();
  if (req.path.startsWith('/api/')) return res.status(401).json({ erro: 'login necessário' });
  res.redirect('/login');
}

const paginaLogin = (erro = '') => `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Painel de Gestão Visu</title>
<link rel="icon" href="/logo.png"><style>
body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
background:radial-gradient(120% 140% at 100% 0%,#2F2963 0%,#241E48 60%);color:#241E48}
form{background:#fff;padding:32px 28px;border-radius:18px;width:min(340px,90vw);box-shadow:0 20px 50px rgba(60,0,40,.35);text-align:center}
img{width:170px;height:auto;display:block;margin:0 auto;background:#241E48;padding:14px 18px;border-radius:12px}h1{font-size:18px;margin:14px 0 4px}p{margin:0 0 18px;color:#8A86A0;font-size:13px}
input{width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #CFCCDD;border-radius:10px;font:inherit}
button{margin-top:12px;width:100%;padding:11px;border:0;border-radius:10px;background:#E8780C;color:#fff;font:600 15px system-ui;cursor:pointer}
.e{color:#c0153a;font-size:13px;margin-top:10px}</style></head><body>
<form method="post" action="/login"><img src="/logo-visu.png" alt="Visu Design"><h1>Painel de Gestão</h1><p>Acesso restrito</p>
<input type="password" name="senha" placeholder="Senha" autofocus required><button>Entrar</button>
${erro ? `<div class="e">${erro}</div>` : ''}</form></body></html>`;

app.get('/login', (req, res) => res.send(paginaLogin()));
app.post('/login', (req, res) => {
  const ok = config.senhaPainel && crypto.timingSafeEqual(
    crypto.createHash('sha256').update(String(req.body.senha || '')).digest(),
    crypto.createHash('sha256').update(config.senhaPainel).digest()
  );
  if (!ok) return res.status(401).send(paginaLogin('Senha incorreta.'));
  const exp = String(Date.now() + 12 * 3600e3);
  res.setHeader('Set-Cookie', `${COOKIE}=${encodeURIComponent(exp + '.' + assinar(exp))}; Path=/; HttpOnly; SameSite=Lax; Max-Age=43200${req.secure ? '; Secure' : ''}`);
  res.redirect('/');
});
app.get('/sair', (req, res) => {
  res.setHeader('Set-Cookie', `${COOKIE}=; Path=/; Max-Age=0`);
  res.redirect('/login');
});

app.get('/saude', (req, res) => res.json({ ok: true }));
app.get(['/logo.png', '/logo-visu.png'], (req, res) => res.sendFile(path.join(raiz, 'public', req.path.slice(1))));
app.use('/vitrine', express.static(path.join(raiz, 'public', 'vitrine'), { maxAge: '7d' }));

// ---------- conexão com a Conta Azul ----------
app.get('/conectar', exigeLogin, (req, res) => {
  if (!config.clientId || !config.clientSecret) {
    return res.status(500).send('Faltam CONTA_AZUL_CLIENT_ID e CONTA_AZUL_CLIENT_SECRET nas variáveis de ambiente.');
  }
  res.redirect(ca.urlDeAutorizacao());
});

app.get('/callback', exigeLogin, async (req, res) => {
  try {
    if (req.query.error) throw new Error(String(req.query.error_description || req.query.error));
    await ca.trocarCodigo(String(req.query.code || ''), String(req.query.state || ''));
    res.redirect('/?conectado=1');
  } catch (e) {
    res.status(400).send(`<p>Não foi possível conectar à Conta Azul.</p><pre>${String(e.message).replace(/</g, '&lt;')}</pre><p><a href="/">Voltar</a></p>`);
  }
});

app.post('/desconectar', exigeLogin, async (req, res) => {
  await ca.desconectar();
  res.redirect('/');
});

// ---------- API do painel ----------
app.get('/api/status', exigeLogin, async (req, res) => {
  res.json({ ...(await ca.statusConexao()), demo: config.demo, redirect_uri: redirectUri(), credenciais_ok: !!(config.clientId && config.clientSecret) });
});

// Base de vendas (linhas da planilha já padronizadas). Os indicadores são calculados no navegador,
// para os filtros responderem na hora.
app.get('/api/vendas', exigeLogin, async (req, res) => {
  try {
    res.json(await dadosDeVendas(req.query.forcar === '1'));
  } catch (e) {
    console.error('[vendas]', e);
    res.status(502).json({ erro: e.message });
  }
});

// Gestão financeira (DRE, caixa, contas a receber/pagar, saldos) pela API da Conta Azul
app.get('/api/financeiro', exigeLogin, async (req, res) => {
  try { res.json(await dadosFinanceiros(req.query.forcar === '1')); }
  catch (e) { console.error('[financeiro]', e); res.status(502).json({ erro: e.message }); }
});

// Mapeamento de colunas e inconsistências da planilha, sem as linhas
app.get('/api/planilha', exigeLogin, async (req, res) => {
  try {
    const d = await dadosDeVendas(req.query.forcar === '1');
    res.json({ fonte: d.fonte, planilha_configurada: planilhaConfigurada(), linhas: d.linhas.length, qualidade: d.qualidade });
  } catch (e) { res.status(502).json({ erro: e.message }); }
});

// Mostra a estrutura crua da API para conferir nomes de campos (usar uma vez após conectar)
app.get('/api/diagnostico', exigeLogin, async (req, res) => {
  try { res.json(await ca.amostraBruta()); } catch (e) { res.status(502).json({ erro: e.message }); }
});

// Página do painel (o arquivo é um fragmento; aqui recebe o cabeçalho HTML completo)
const cabecalho = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><link rel="icon" href="/logo.png"></head><body>';
app.get(['/', '/index.html'], exigeLogin, async (req, res) => {
  const corpo = await fs.readFile(path.join(raiz, 'public', 'painel.html'), 'utf8');
  res.type('html').send(cabecalho + corpo + '</body></html>');
});

app.listen(config.porta, () => {
  console.log(`Painel Comercial Visu em ${config.urlPublica} (porta ${config.porta})`);
  if (!config.senhaPainel) console.warn('ATENÇÃO: PAINEL_SENHA não definida — o painel está aberto.');
  console.log(`URL de redirecionamento para cadastrar na Conta Azul: ${redirectUri()}`);
});
