// Painel Comercial Visu — servidor (Seja Expert)
import express from 'express';
import crypto from 'node:crypto';
import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { config, redirectUri } from './src/config.js';
import * as ca from './src/contaAzul.js';
import { montarPainel } from './src/painel.js';

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
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Painel Comercial Visu</title>
<link rel="icon" href="/logo.png"><style>
body{margin:0;min-height:100vh;display:grid;place-items:center;font-family:system-ui,-apple-system,"Segoe UI",sans-serif;
background:radial-gradient(120% 120% at 0% 0%,#ff4fb0 0%,#e6007e 45%,#8a0a55 100%);color:#2a0f22}
form{background:#fff;padding:32px 28px;border-radius:18px;width:min(340px,90vw);box-shadow:0 20px 50px rgba(60,0,40,.35);text-align:center}
img{width:84px;height:84px;border-radius:50%;object-fit:cover}h1{font-size:18px;margin:14px 0 4px}p{margin:0 0 18px;color:#7a5b6f;font-size:13px}
input{width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #e8cfe0;border-radius:10px;font:inherit}
button{margin-top:12px;width:100%;padding:11px;border:0;border-radius:10px;background:#e6007e;color:#fff;font:600 15px system-ui;cursor:pointer}
.e{color:#c0153a;font-size:13px;margin-top:10px}</style></head><body>
<form method="post" action="/login"><img src="/logo.png" alt="Visu"><h1>Painel Comercial</h1><p>Acesso restrito</p>
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
app.get('/logo.png', (req, res) => res.sendFile(path.join(raiz, 'public', 'logo.png')));

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

app.get('/api/painel', exigeLogin, async (req, res) => {
  try {
    res.json(await montarPainel({ ano: req.query.ano, mes: req.query.mes, forcar: req.query.forcar === '1' }));
  } catch (e) {
    console.error('[painel]', e);
    res.status(e.naoConectado ? 409 : 502).json({ erro: e.message });
  }
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
